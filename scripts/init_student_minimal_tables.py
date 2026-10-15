"""只补建缺少的学生行政表；不覆盖已有表，不运行 all.sql。"""
import argparse
import json
from pathlib import Path

from sqlalchemy import create_engine

from check_student_shared_schema import ROOT, connection_url
from app.repositories.student_schema import check_student_schema


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-instance", action="store_true")
    args = parser.parse_args()
    engine = create_engine(connection_url(args.local_instance), connect_args={"connect_timeout": 3})
    try:
        with engine.begin() as connection:
            before = check_student_schema(connection, "leave")
            allowed = ["missing_table:student_admin_service"]
            if before["issues"] and before["issues"] != allowed:
                print(json.dumps({"created": False, "issues": before["issues"]}, ensure_ascii=False))
                return 1
            if before["issues"] == allowed:
                # FK 目标必须已经存在；检查器已核实学生/员工表使用字段。
                ddl = (ROOT / "scripts/sql/student/20261015_add_student_admin_service.sql").read_text(encoding="utf-8")
                connection.exec_driver_sql(ddl)
            after = check_student_schema(connection, "leave")
            print(json.dumps({"created": before["issues"] == allowed, "compatible": after["compatible"],
                              "issues": after["issues"]}, ensure_ascii=False))
            return 0 if after["compatible"] else 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
