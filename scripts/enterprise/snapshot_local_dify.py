"""在本地 Dify API 容器中备份企业应用；输出仅包含非密钥元数据。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/app/api")
from app_factory import create_app

NAMES = {
    "extract": "StuProject-企业-extract",
    "query": "StuProject-企业-query",
    "knowledge": "StuProject-企业-knowledge",
    "summary": "StuProject-企业-summary",
}


def main():
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/stuproject-enterprise-snapshot")
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / "snapshot.json").exists():
        raise RuntimeError("备份目录已有快照，拒绝覆盖")
    with create_app().app_context():
        from extensions.ext_database import db
        from models.account import Tenant
        from models.model import App
        from services.app_dsl_service import AppDslService

        tenants = db.session.query(Tenant).all()
        if len(tenants) != 1:
            raise RuntimeError("需要唯一的本地工作区")
        apps = db.session.query(App).filter_by(tenant_id=tenants[0].id).all()
        result = {"tenant_id": tenants[0].id, "all_app_ids": [a.id for a in apps], "apps": []}
        for scene, name in NAMES.items():
            matches = [a for a in apps if a.name == name]
            if len(matches) != 1:
                raise RuntimeError(f"须找到唯一原应用：{name}")
            app = matches[0]
            if app.mode != "workflow" or not app.workflow_id:
                raise RuntimeError(f"原应用未发布 Workflow：{name}")
            (folder / f"{scene}.published.yml").write_text(
                AppDslService.export_dsl(app, include_secret=True, workflow_id=app.workflow_id), encoding="utf-8")
            (folder / f"{scene}.draft.yml").write_text(
                AppDslService.export_dsl(app, include_secret=True), encoding="utf-8")
            result["apps"].append({"scene": scene, "id": app.id, "name": app.name,
                "workflow_id": app.workflow_id, "enable_api": app.enable_api, "enable_site": app.enable_site})
        (folder / "snapshot.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"backed_up_apps": result["apps"], "secrets_printed": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
