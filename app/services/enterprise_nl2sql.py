"""复用现有 Dify question → sql 契约，限定到经过授权的学生/成绩派生表。"""
from decimal import Decimal
import json

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, text
from sqlglot import exp, parse, parse_one
from sqlglot.errors import SqlglotError

from app.config import settings
from app.core.dify import call_nl2sql
from app.models.enterprise_student import StudentProfile as S, StudentScore as C
from app.services.enterprise_student import error, score_scope, student_scope, utcnow

SCHEMA = {
    "authorized_students": ["student_id", "student_no", "full_name", "department_id", "status", "is_archived", "version"],
    "authorized_scores": ["score_id", "student_id", "student_no", "full_name", "course_code", "term_code",
                          "assessment_code", "attempt_no", "score_value", "max_score", "status", "version"],
}
ALLOWED = {getattr(exp, name) for name in (
    "Select", "From", "Table", "TableAlias", "Identifier", "Column", "Literal", "Where", "And", "Or", "Not",
    "Paren", "EQ", "NEQ", "GT", "GTE", "LT", "LTE", "Like", "Is", "Null", "Boolean", "In", "Between",
    "Order", "Ordered", "Limit", "Group", "Having", "Alias", "Count", "Sum", "Avg", "Min", "Max", "Distinct",
    "Add", "Sub", "Mul", "Div", "Neg", "Star")}


def validate_query(sql):
    if not isinstance(sql, str) or len(sql) > 12000:
        error(400, "模型 SQL 为空或过长")
    try:
        expressions = parse(sql, read="mysql")
    except SqlglotError:
        error(400, "模型 SQL 无法解析")
    if len(expressions) != 1 or not isinstance(expressions[0], exp.Select):
        error(400, "只允许单条 SELECT")
    query = expressions[0]
    tables = list(query.find_all(exp.Table))
    if len(tables) != 1 or tables[0].name not in SCHEMA or tables[0].db or tables[0].catalog:
        error(400, "只能查询单个授权学生或成绩数据集")
    table = tables[0]
    if any(v for k, v in table.args.items() if k not in {"this", "alias"}):
        error(400, "不支持该表引用方式")
    if any(v for k, v in query.args.items() if k not in {
        "expressions", "from_", "where", "order", "limit", "group", "having", "distinct"}):
        error(400, "不支持子查询、连接、写入、锁定或其他查询扩展")
    aliases = {n.alias for n in query.expressions if isinstance(n, exp.Alias)}
    for node in query.walk():
        if type(node) not in ALLOWED or node.comments:
            error(400, "SQL 含未允许的语法、函数或注释")
        if isinstance(node, exp.Star) and not isinstance(node.parent, exp.Count):
            error(400, "请明确选择字段，禁止 SELECT *")
        if isinstance(node, exp.Column):
            allowed_alias = node.name in aliases and isinstance(node.parent, exp.Ordered)
            if len(node.parts) > 2 or (node.table and node.table != table.alias_or_name):
                error(400, "SQL 字段限定符不合法")
            if node.name not in SCHEMA[table.name] and not allowed_alias:
                error(400, "SQL 引用了未授权字段")
    limit = query.args.get("limit")
    if limit:
        value = limit.expression
        if not isinstance(value, exp.Literal) or value.is_string or not value.this.isdigit() or int(value.this) < 1:
            error(400, "LIMIT 必须为正整数")
        query.limit(min(int(value.this), 200), copy=False)
    else:
        query.limit(200, copy=False)
    return query


def authorized_statement(actor, table_name):
    if table_name == "authorized_students":
        return select(S.student_id, S.student_no, S.full_name, S.department_id, S.status, S.is_archived,
                      S.row_version.label("version")).where(student_scope(actor), S.is_archived.is_(False))
    return select(C.score_id, C.student_id, S.student_no, S.full_name, C.course_code, C.term_code,
        C.assessment_code, C.attempt_no, C.score_value, C.max_score, C.status, C.row_version.label("version")).join(
        S, S.student_id == C.student_id).where(score_scope(actor), S.is_archived.is_(False))


def execute_query(db, actor, sql):
    query = validate_query(sql)
    table = next(query.find_all(exp.Table))
    statement = authorized_statement(actor, table.name)
    # 只将后端自身生成的角色/关系范围写入派生表，不接受模型提供权限条件。
    scoped = parse_one(str(statement.compile(compile_kwargs={"literal_binds": True})), read="mysql")
    dialect = "mysql" if db.bind.dialect.name == "mysql" else "sqlite"
    params = {}
    for literal in list(query.find_all(exp.Literal)):
        if isinstance(literal.parent, exp.Limit):
            continue
        key = f"nlq_{len(params)}"
        value = literal.this if literal.is_string else Decimal(literal.this)
        if dialect == "sqlite" and isinstance(value, Decimal):
            value = int(value) if value == value.to_integral_value() else float(value)
        params[key] = value
        literal.replace(exp.Placeholder(this=key))
    table.replace(exp.Subquery(this=scoped, alias=exp.TableAlias(this=exp.to_identifier(table.alias_or_name))))
    safe_sql = query.sql(dialect=dialect)
    if dialect == "mysql":
        safe_sql = safe_sql.replace("SELECT ", "SELECT /*+ MAX_EXECUTION_TIME(3000) */ ", 1)
    try:
        with db.bind.connect() as connection:
            if dialect == "mysql":
                connection.exec_driver_sql("START TRANSACTION READ ONLY")
            result = connection.execute(text(safe_sql), params)
            columns = list(result.keys())
            rows = []
            for mapping in result.mappings().fetchmany(200):
                row = dict(mapping)
                for name, value in row.items():
                    if name.endswith("_id") and value is not None:
                        row[name] = str(value)
                    elif isinstance(value, Decimal):
                        row[name] = str(value)
                rows.append(row)
            connection.rollback()
    except Exception:
        error(502, "授权查询执行失败，请使用固定查询接口或调整问题")
    return {"columns": columns, "rows": rows, "row_count": len(rows), "limit": 200,
            "data_time": utcnow().isoformat(timespec="seconds") + "Z"}


async def query_student_scores(db, actor, question):
    schema = dict(SCHEMA)
    if "academic" not in actor.role_codes:
        schema.pop("authorized_scores")
    prompt = json.dumps({"question": question, "allowed_schema": schema,
        "rules": "仅生成 MySQL 单表只读 SELECT，显式字段，LIMIT <= 200；不支持的问题返回 UNSUPPORTED。禁止连接、子查询、注释、外部标识与写入。"}, ensure_ascii=False)
    try:
        sql = await call_nl2sql(prompt, user=f"enterprise-employee-{actor.employee_id}",
            api_base=settings.STUDENT_SCORE_DIFY_BASE, api_key=settings.STUDENT_SCORE_DIFY_KEY)
    except Exception:
        error(503, "学生成绩 Dify 工作流未配置或调用失败")
    return await run_in_threadpool(execute_query, db, actor, sql)
