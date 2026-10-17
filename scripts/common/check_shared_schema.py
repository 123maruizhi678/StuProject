"""只读核对公共表；显式参数可应用唯一账号审计增量，不建业务表。"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import inspect
from app.database import Base, engine
from app.models import common


def check_schema(*, apply_account_audit=False):
    inspector = inspect(engine)
    if apply_account_audit:
        existing = {c["name"] for c in inspector.get_columns("operation_log")}
        if "actor_account_id" not in existing:
            sql = (Path(__file__).resolve().parents[1] / "sql/common/20261017_account_audit_actor.sql").read_text(encoding="utf-8")
            with engine.begin() as conn:
                conn.exec_driver_sql(sql)
            inspector = inspect(engine)
            print("已应用公共账号操作者审计增量")
    errors = []
    for name in common.__all__:
        item = getattr(common, name)
        table = item.__table__ if name == "UserAccount" else item
        if not inspector.has_table(table.name):
            errors.append(table.name + ": 表缺失")
            continue
        actual = {c["name"]: c for c in inspector.get_columns(table.name)}
        for column in table.c:
            if column.name not in actual:
                errors.append(table.name + "." + column.name + ": 字段缺失")
            elif column.nullable != actual[column.name]["nullable"]:
                errors.append(table.name + "." + column.name + ": 可空性不一致")
        actual_fk = {(tuple(f["constrained_columns"]), f["referred_table"], tuple(f["referred_columns"]))
                     for f in inspector.get_foreign_keys(table.name)}
        for constraint in table.foreign_key_constraints:
            expected = (tuple(c.name for c in constraint.columns),
                        constraint.elements[0].column.table.name,
                        tuple(e.column.name for e in constraint.elements))
            if expected not in actual_fk:
                errors.append(table.name + ": 关联外键缺失 " + str(expected))
    if errors:
        raise RuntimeError("\n".join(errors))
    print("公共账号、组织、员工、客户、学生及账号审计结构核对通过")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-account-audit", action="store_true")
    args = parser.parse_args()
    try:
        check_schema(apply_account_audit=args.apply_account_audit)
    except Exception as exc:
        # 不打印连接凭据、SQL 参数或原始数据库异常。
        print("结构核对失败：" + (str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__), file=sys.stderr)
        raise SystemExit(1)
