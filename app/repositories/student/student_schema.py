"""只读检查共享表及外键，不创建、修复或删除企业表。"""
from sqlalchemy import Boolean, DateTime, Date, Numeric, LargeBinary, Integer, JSON, String, inspect
from sqlalchemy.exc import SQLAlchemyError

from app.models import common as shared


class StudentSchemaError(Exception):
    status = 503

    def __init__(self, issues):
        self.issues = issues
        self.message = "学生模块依赖的数据库结构不兼容，请运行 scripts/student/check_student_shared_schema.py 核验"
        super().__init__(self.message)


FEATURE_TABLES = {
    "leave": ("student_profile", "employee", "student_staff_binding", "student_admin_service",
              "business_notification", "operation_log"),
    "ticket": ("org_department", "student_profile", "service_ticket", "service_ticket_record", "operation_log"),
}
WRITE_TABLES = {"student_admin_service", "business_notification", "operation_log",
                "service_ticket", "service_ticket_record"}


def _family(type_):
    if isinstance(type_, Boolean):
        return "integer"  # MySQL BOOLEAN 反射为 TINYINT。
    for cls, name in ((Integer, "integer"), (DateTime, "datetime"), (Date, "date"), (Numeric, "numeric"), (LargeBinary, "binary"), (JSON, "json"), (String, "string")):
        if isinstance(type_, cls):
            return name
    return type(type_).__name__.lower()


def check_student_schema(connection, feature):
    inspector = inspect(connection)
    existing = set(inspector.get_table_names())
    issues, tables, target_cache = [], {}, {}
    for name in FEATURE_TABLES[feature]:
        if name not in existing:
            issues.append(f"missing_table:{name}")
            continue
        expected = shared.metadata.tables[name]
        columns = {c["name"]: c for c in inspector.get_columns(name)}
        tables[name] = {"columns": {n: str(c["type"]) for n, c in columns.items()},
                        "foreign_keys": inspector.get_foreign_keys(name)}
        for col in expected.columns:
            observed = columns.get(col.name)
            if observed is None:
                issues.append(f"missing_column:{name}.{col.name}")
            elif _family(col.type) != _family(observed["type"]):
                issues.append(f"column_type:{name}.{col.name}")
            elif (name in WRITE_TABLES and col.nullable and not observed.get("nullable", True)):
                issues.append(f"unexpected_not_null:{name}.{col.name}")
            elif (name in WRITE_TABLES and isinstance(col.type, String) and col.type.length
                  and getattr(observed["type"], "length", None)
                  and observed["type"].length < col.type.length):
                issues.append(f"column_too_short:{name}.{col.name}")
        pk = set(inspector.get_pk_constraint(name).get("constrained_columns") or [])
        if pk != {c.name for c in expected.primary_key}:
            issues.append(f"primary_key:{name}")
        unique_sets = {frozenset(c.get("column_names") or []) for c in inspector.get_unique_constraints(name)}
        unique_sets.update(frozenset(c.get("column_names") or []) for c in inspector.get_indexes(name) if c.get("unique"))
        for constraint in expected.constraints:
            if constraint.__class__.__name__ == "UniqueConstraint":
                if frozenset(c.name for c in constraint.columns) not in unique_sets:
                    issues.append(f"unique_key:{name}." + ",".join(c.name for c in constraint.columns))
        observed_fks = tables[name]["foreign_keys"]
        for fk in expected.foreign_keys:
            target = fk.column
            if not any(f.get("constrained_columns") == [fk.parent.name]
                       and f.get("referred_table") == target.table.name
                       and f.get("referred_columns") == [target.name]
                       for f in observed_fks):
                issues.append(f"missing_foreign_key:{name}.{fk.parent.name}->{target.table.name}.{target.name}")
        # 实际表中额外的 FK 也核验引用目标，包含 employee/部门/客户等依赖。
        for fk in observed_fks:
            target = fk["referred_table"]
            target_schema = fk.get("referred_schema")
            marker = (target_schema, target)
            if marker not in target_cache:
                target_cache[marker] = ({c["name"] for c in inspector.get_columns(target, schema=target_schema)}
                                        if inspector.has_table(target, schema=target_schema) else None)
            target_columns = target_cache[marker]
            if target_columns is None:
                issues.append(f"missing_fk_target:{name}->{target}")
                continue
            if not set(fk["referred_columns"]).issubset(target_columns):
                issues.append(f"missing_fk_target_column:{name}->{target}")
        if name in WRITE_TABLES:
            for c in columns.values():
                if (c["name"] not in expected.c and not c.get("nullable", True)
                        and c.get("default") is None and not c.get("autoincrement")
                        and not c.get("computed")):
                    issues.append(f"unhandled_required_column:{name}.{c['name']}")
    return {"feature": feature, "compatible": not issues, "issues": issues, "tables": tables,
            "notes": ["检查使用字段、主键、幂等唯一键和声明外键；不替代完整迁移审查。",
                      "student_admin_service.reviewer_id 为正式员工外键，实际审批人仍由审计保存。",
                      "通知/操作日志的 entity_id 是多态逻辑关联，不能统一指向一张表。"]}


def require_student_schema(db, feature):
    try:
        result = check_student_schema(db.connection(), feature)
    except SQLAlchemyError:
        raise StudentSchemaError(["schema_inspection_unavailable"]) from None
    if not result["compatible"]:
        raise StudentSchemaError(result["issues"])
