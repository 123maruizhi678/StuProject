"""只读共享表检查：默认读公共.env；--local-instance使用本机学生专用实例。"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import URL, create_engine
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.repositories.student_schema import check_student_schema


def connection_url(local_instance=False):
    if local_instance:
        state = json.loads((ROOT.parent / ".student-local-mysql" / "instance.json").read_text(encoding="utf-8"))
        if Path(state["owner"]).resolve() != ROOT.resolve():
            raise ValueError("专用实例不属于当前项目")
        return URL.create("mysql+pymysql", username="root", password=state["root_password"],
                          host="127.0.0.1", port=int(state["port"]), database="education_agent")
    return URL.create("mysql+pymysql", username=settings.DB_USER, password=settings.DB_PASSWORD,
                      host=settings.DB_HOST, port=settings.DB_PORT, database=settings.DB_NAME)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-instance", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    engine = None
    try:
        url = connection_url(args.local_instance)
        engine = create_engine(url, connect_args={"connect_timeout": 3}, echo=False)
        with engine.connect() as connection:
            results = [check_student_schema(connection, feature) for feature in ("leave", "ticket")]
        report = {"connected": True, "host": url.host, "port": url.port, "database": url.database,
                  "compatible": all(r["compatible"] for r in results), "checks": results}
    except (SQLAlchemyError, ValueError, KeyError, OSError):
        report = {"connected": False, "compatible": False,
                  "message": "数据库连接或本地配置不可用；未修改表或数据，请在本机核验连接信息。"}
    finally:
        if engine is not None:
            engine.dispose()
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "checks"} | {
        "issues": {r["feature"]: r["issues"] for r in report.get("checks", [])}}, ensure_ascii=False))
    return 0 if report["compatible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
