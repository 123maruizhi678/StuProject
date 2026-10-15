"""学生助手五张专属表与一张公共请假表的初始化工具。

用法：python scripts/init_student_tables.py --dry-run  # 只显示SQL，不连接数据库
      python scripts/init_student_tables.py --check    # 只检查企业主表/现有结构
      python scripts/init_student_tables.py --apply    # 只创建缺失且符合预期的学生表

连接参数复用项目根目录 .env 和 app.database.engine，不在脚本硬编码账号。
只增加五张学生专属表与公共请假表；不会修改已有表、删除数据；已有结构不一致时先停止并提示迁移。
"""

import argparse
import logging
from pathlib import Path
import re
import sys

# 使“python scripts/...”从任意当前目录执行时仍能找到项目 app 包。
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import BigInteger, Integer, Numeric, String, Text, inspect, text
from sqlalchemy.dialects.mysql import DATETIME, JSON, dialect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import CreateIndex, CreateTable

from app.database import Base, engine
from scripts.student_sql_paths import enterprise_sql_path
from app.models.student import STUDENT_TABLES
from app.models.student_shared import student_leave_request

# 两张真实企业主表是物理外键的前置依赖，绝不能由本脚本创建简化替身。
REQUIRED_SHARED_KEYS = {"student_profile": "student_id", "employee": "employee_id"}
# 下面的表提供共用业务；不建重复表，缺少时仅提示相应功能暂未就绪。
REUSED_BUSINESS_TABLES = (
    "student_staff_binding",
    "service_ticket",
    "service_ticket_record",
    "business_notification",
    "operation_log",
)
logger = logging.getLogger("student_tables")


class SchemaMismatch(ValueError):
    """初始化不是迁移；结构不一致时用此异常阻止后续 DDL。"""


def normalize_check(expression: str) -> str:
    """忽略MySQL反射增加的括号、反引号、空白和字符串字符集前缀。"""
    return re.sub(r"_utf8mb4|[()\s]", "", expression.lower().replace(chr(96), ""))


def column_type_errors(expected, actual) -> list[str]:
    """按存储含义核对类型，不因MySQL显示宽度等无关细节误判。"""
    errors = []
    if isinstance(expected, BigInteger):
        valid = isinstance(actual, BigInteger) and not getattr(
            actual, "unsigned", False
        )
    elif isinstance(expected, Integer):
        valid = (
            isinstance(actual, Integer)
            and not isinstance(actual, BigInteger)
            and not getattr(actual, "unsigned", False)
        )
    elif isinstance(expected, DATETIME):
        valid = isinstance(actual, DATETIME) and (actual.fsp or 0) == (
            expected.fsp or 0
        )
    elif isinstance(expected, JSON):
        valid = isinstance(actual, JSON)
    elif isinstance(expected, Numeric):
        valid = isinstance(actual, Numeric) and (actual.precision, actual.scale) == (
            expected.precision,
            expected.scale,
        )
    elif isinstance(expected, Text):
        valid = isinstance(actual, Text)
    elif isinstance(expected, String):
        valid = (
            isinstance(actual, String)
            and not isinstance(actual, Text)
            and actual.length == expected.length
        )
    else:
        valid = expected._type_affinity is actual._type_affinity
    if not valid:
        errors.append("存储类型不一致")
    expected_collation = getattr(expected, "collation", None)
    if expected_collation and getattr(actual, "collation", None) != expected_collation:
        errors.append("排序规则不一致")
    return errors


def existing_table_errors(inspector, table) -> list[str]:
    """已有同名表只有通过核对才允许跳过，防止旧10表草案混进新版本。"""
    errors = []
    actual_columns = {c["name"]: c for c in inspector.get_columns(table.name)}
    expected_names = set(table.columns.keys())
    if set(actual_columns) != expected_names:
        missing = sorted(expected_names - set(actual_columns))
        extra = sorted(set(actual_columns) - expected_names)
        errors.append(f"{table.name} 字段不一致：缺少{missing}，多出{extra}")
    for column in table.columns:
        actual = actual_columns.get(column.name)
        if actual is None:
            continue
        for reason in column_type_errors(
            column.type.dialect_impl(inspector.bind.dialect), actual["type"]
        ):
            errors.append(f"{table.name}.{column.name} {reason}")
        if bool(actual["nullable"]) != column.nullable:
            errors.append(f"{table.name}.{column.name} 可空约束不一致")
        if column.autoincrement is True and not actual.get("autoincrement", False):
            errors.append(f"{table.name}.{column.name} 缺少自增")
        expected_default = (
            str(column.server_default.arg.compile(dialect=inspector.bind.dialect))
            if column.server_default
            else None
        )
        actual_default = actual.get("default")

        def normalized_default(value):
            if value is None:
                return None
            normalized = re.sub(r"\s+", " ", str(value).strip()).lower().strip("'")
            if normalized in (
                "current_timestamp",
                "current_timestamp()",
                "now()",
                "(now())",
            ):
                return "current_timestamp"
            return normalized.replace("now(6)", "current_timestamp(6)")

        if normalized_default(expected_default) != normalized_default(actual_default):
            errors.append(f"{table.name}.{column.name} 默认值不一致")
    expected_pk = [c.name for c in table.primary_key.columns]
    if inspector.get_pk_constraint(table.name)["constrained_columns"] != expected_pk:
        errors.append(f"{table.name} 主键不一致")
    # 外键核对来源列、目标表及目标列，而非只核对约束名字。
    expected_fks = {
        (
            tuple(e.parent.name for e in fk.elements),
            fk.referred_table.name,
            tuple(e.column.name for e in fk.elements),
        )
        for fk in table.foreign_key_constraints
    }
    actual_fks = {
        (
            tuple(fk["constrained_columns"]),
            fk["referred_table"],
            tuple(fk["referred_columns"]),
        )
        for fk in inspector.get_foreign_keys(table.name)
    }
    if actual_fks != expected_fks:
        errors.append(f"{table.name} 外键不一致，必须关联真实企业学生/员工主键")
    indexes = inspector.get_indexes(table.name)
    actual_unique = {tuple(x["column_names"]) for x in indexes if x.get("unique")}
    actual_unique.update(
        tuple(x["column_names"]) for x in inspector.get_unique_constraints(table.name)
    )
    from sqlalchemy import CheckConstraint, UniqueConstraint

    expected_unique = {
        tuple(c.name for c in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    if not expected_unique.issubset(actual_unique):
        errors.append(f"{table.name} 缺少业务唯一键")
    actual_indexes = {tuple(x["column_names"]) for x in indexes}
    for index in table.indexes:
        if tuple(c.name for c in index.columns) not in actual_indexes:
            errors.append(f"{table.name} 缺少索引 {index.name}")
    actual_checks = {
        x["name"]: normalize_check(x["sqltext"])
        for x in inspector.get_check_constraints(table.name)
    }
    for constraint in table.constraints:
        if isinstance(constraint, CheckConstraint):
            if actual_checks.get(constraint.name) != normalize_check(
                str(constraint.sqltext)
            ):
                errors.append(f"{table.name} CHECK不一致：{constraint.name}")
    if (
        inspector.get_table_options(table.name).get("mysql_engine", "").lower()
        != "innodb"
    ):
        errors.append(f"{table.name} 必须使用InnoDB")
    return errors


def public_leave_sql():
    source = enterprise_sql_path().read_text(encoding="utf-8")
    blocks = re.findall(r"CREATE TABLE[^;]+;", source, re.I)
    for block in blocks:
        if re.match(
            r"CREATE TABLE(?: IF NOT EXISTS)?\s+`?student_leave_request`?\s*\(",
            block,
            re.I,
        ):
            return block
    raise SchemaMismatch("企业公共请假表DDL缺失，停止初始化")


def public_leave_errors(inspector):
    # 公共表以企业DDL为准；只核对本模块依赖的字段和约束，允许其他模块增加字段。
    table = student_leave_request
    actual = {c["name"]: c for c in inspector.get_columns(table.name)}
    errors = []
    for col in table.columns:
        found = actual.get(col.name)
        if not found:
            errors.append(f"公共请假表缺少字段 {col.name}")
        elif (
            column_type_errors(
                col.type.dialect_impl(inspector.bind.dialect), found["type"]
            )
            or bool(found["nullable"]) != col.nullable
        ):
            errors.append(f"公共请假表字段不兼容 {col.name}")
    if inspector.get_pk_constraint(table.name)["constrained_columns"] != [
        "leave_request_id"
    ]:
        errors.append("公共请假表主键不兼容")
    uniques = {
        tuple(x["column_names"])
        for x in inspector.get_indexes(table.name)
        if x.get("unique")
    }
    if ("request_no",) not in uniques:
        errors.append("公共请假表缺少申请编号唯一键")
    fks = {
        (
            tuple(x["constrained_columns"]),
            x["referred_table"],
            tuple(x["referred_columns"]),
        )
        for x in inspector.get_foreign_keys(table.name)
    }
    for name, target, pk in (
        ("student_id", "student_profile", "student_id"),
        ("approver_employee_id", "employee", "employee_id"),
        ("decision_employee_id", "employee", "employee_id"),
    ):
        if ((name,), target, (pk,)) not in fks:
            errors.append(f"公共请假表缺少外键 {name}")
    checks = {
        normalize_check(x["sqltext"])
        for x in inspector.get_check_constraints(table.name)
    }
    for line in public_leave_sql().splitlines():
        match = re.search(r"CHECK \((.*)\),?\s*$", line)
        if match and normalize_check(match[1]) not in checks:
            errors.append("公共请假表缺少约束 " + line.strip().split("CHECK")[0])
    if (
        inspector.get_table_options(table.name).get("mysql_engine", "").lower()
        != "innodb"
    ):
        errors.append("公共请假表必须使用InnoDB")
    return errors


def inspect_plan(connection):
    """只读预检：一次检查完所有已有表，不一致就在任何建表前停止。"""
    inspector = inspect(connection)
    version = str(connection.scalar(text("SELECT VERSION()")))
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    if (
        "mariadb" in version.lower()
        or not match
        or tuple(map(int, match.groups())) < (8, 0, 16)
    ):
        raise SchemaMismatch("本版本要求MySQL 8.0.16及以上；请核对实际数据库版本。")
    names = set(inspector.get_table_names())
    errors = []
    for table_name, key_name in REQUIRED_SHARED_KEYS.items():
        if table_name not in names:
            errors.append(f"缺少企业主表 {table_name}，先由企业模块初始化")
            continue
        columns = {c["name"]: c for c in inspector.get_columns(table_name)}
        actual = columns.get(key_name)
        if (
            not actual
            or column_type_errors(BigInteger(), actual["type"])
            or actual.get("nullable")
        ):
            errors.append(f"{table_name}.{key_name} 必须是非空、有符号BIGINT")
        if inspector.get_pk_constraint(table_name)["constrained_columns"] != [key_name]:
            errors.append(f"{table_name} 的主键必须为 {key_name}")
        if (
            inspector.get_table_options(table_name).get("mysql_engine", "").lower()
            != "innodb"
        ):
            errors.append(f"企业主表 {table_name} 必须使用InnoDB")
    existing = [t for t in STUDENT_TABLES if t.name in names]
    missing = [t for t in STUDENT_TABLES if t.name not in names]
    for table in existing:
        errors.extend(existing_table_errors(inspector, table))
    if "student_leave_request" in names:
        errors.extend(public_leave_errors(inspector))
        existing.append(student_leave_request)
    else:
        missing.append(student_leave_request)
    if errors:
        raise SchemaMismatch("\n".join(errors))
    warnings = [name for name in REUSED_BUSINESS_TABLES if name not in names]
    return version, existing, missing, warnings


def dry_run() -> None:
    """DDL由ORM生成，列名、注释、主外键和索引不手写两份。"""
    mysql = dialect()
    print("-- 仅预览，不连接数据库；企业student_profile、employee须先存在。")
    print("-- 公共请假表，与企业模块共用同一张表。")
    print(public_leave_sql())
    for table in STUDENT_TABLES:
        print(str(CreateTable(table).compile(dialect=mysql)).strip() + ";\n")
        for index in sorted(table.indexes, key=lambda item: item.name):
            print(str(CreateIndex(index).compile(dialect=mysql)) + ";")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="学生助手：五张专属表与公共请假表")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--dry-run", action="store_true", help="仅打印SQL（默认），不连接数据库"
    )
    modes.add_argument(
        "--check", action="store_true", help="连接数据库，只检查结构，不创建任何表"
    )
    modes.add_argument(
        "--apply",
        action="store_true",
        help="预检通过后，只创建缺失的五张专属表与公共请假表",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if not args.check and not args.apply:
            dry_run()
            return 0
        logger.info(
            "目标：%s:%s / %s", engine.url.host, engine.url.port, engine.url.database
        )
        with engine.connect() as connection:
            connection.execute(text("SET SESSION time_zone = '+00:00'"))
            version, existing, missing, warnings = inspect_plan(connection)
            logger.info(
                "MySQL %s；已有学生表%d张，待建%d张",
                version,
                len(existing),
                len(missing),
            )
            for name in warnings:
                logger.warning("共用业务表尚未就绪：%s；本脚本不会代建", name)
            if args.check:
                logger.info("预检通过，未执行建表。")
                return 0
            # 显式指定五张表；不会误建企业表或顺带创建其他组员的模型。
            # checkfirst不升级旧字段，前面的预检已检查旧表是否真的匹配。
            connection.commit()
            if student_leave_request in missing:
                connection.exec_driver_sql(public_leave_sql())
                connection.commit()
            Base.metadata.create_all(
                bind=connection, tables=list(STUDENT_TABLES), checkfirst=True
            )
            connection.commit()
            inspector = inspect(connection)
            errors = [
                error
                for table in STUDENT_TABLES
                for error in existing_table_errors(inspector, table)
            ]
            errors.extend(public_leave_errors(inspector))
            if errors:
                raise SchemaMismatch("\n".join(errors))
            logger.info("已核对公共请假表：student_leave_request")
            for table in STUDENT_TABLES:
                logger.info("已核对：%s", table.name)
            logger.info(
                "完成：新建%d张，原有%d张保持不变。", len(missing), len(existing)
            )
        return 0
    except SchemaMismatch as exc:
        logger.error("结构预检/核对失败：\n%s\n请使用独立迁移，不删除旧表后重跑。", exc)
        return 2
    except SQLAlchemyError as exc:
        # 不把密码、完整连接串或完整异常输出到终端。
        original_args = getattr(getattr(exc, "orig", None), "args", ())
        errno = original_args[0] if original_args else None
        logger.error(
            "数据库连接或DDL失败（驱动码=%s）；请检查MySQL服务、.env和权限。", errno
        )
        logger.error("MySQL建表不保证整体回滚；重跑前核对已创建表。本脚本不会删表。")
        return 3
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
