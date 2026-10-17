"""在本机 Dify 1.11.4 容器内发布统一企业应用；旧应用经验证后可逆停用。"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, "/app/api")
from app_factory import create_app

APP_NAME = "StuProject-企业-统一工作流"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--dsl", type=Path, default=Path("/tmp/stuproject-enterprise/enterprise.yml"))
    parser.add_argument("--archive-legacy", action="store_true")
    parser.add_argument("--verified-workflow-id")
    args = parser.parse_args()
    snapshot = json.loads((args.snapshot_dir / "snapshot.json").read_text(encoding="utf-8"))
    with create_app().app_context():
        from extensions.ext_database import db
        from models.account import Account, Tenant, TenantAccountJoin
        from models.model import App, ApiToken
        from services.app_dsl_service import AppDslService
        from services.workflow_service import WorkflowService

        tenants = db.session.query(Tenant).all()
        if len(tenants) != 1 or tenants[0].id != snapshot["tenant_id"]:
            raise RuntimeError("工作区与快照不匹配")
        tenant = tenants[0]
        owner = db.session.query(TenantAccountJoin).filter_by(tenant_id=tenant.id, role="owner").one_or_none()
        if owner is None:
            raise RuntimeError("缺少工作区所有者")
        account = db.session.get(Account, owner.account_id)
        account.current_tenant = tenant
        original = {a["scene"]: a for a in snapshot["apps"]}
        target = db.session.get(App, original["extract"]["id"])
        if target is None or target.tenant_id != tenant.id or target.name not in (original["extract"]["name"], APP_NAME):
            raise RuntimeError("待合并目标应用与快照不匹配")
        other_state = lambda: sorted((a.id, a.name, a.workflow_id, a.enable_api, a.enable_site)
            for a in db.session.query(App).filter_by(tenant_id=tenant.id).all()
            if a.id not in {item["id"] for item in snapshot["apps"]})
        before = other_state()
        if args.archive_legacy:
            if target.name != APP_NAME or not args.verified_workflow_id or target.workflow_id != args.verified_workflow_id:
                raise RuntimeError("须先核验本次发布版本，才能停用旧入口")
            archived = []
            for scene in ("query", "knowledge", "summary"):
                old = db.session.get(App, original[scene]["id"])
                archived_name = "[已合并归档] " + original[scene]["name"]
                if old is None or old.tenant_id != tenant.id or old.name not in (original[scene]["name"], archived_name):
                    raise RuntimeError("旧应用与快照不匹配")
                old.name = archived_name
                old.description = "已合并至 " + APP_NAME + "；保留旧版本和历史记录，API/站点入口已停用。"
                old.enable_api = False
                old.enable_site = False
                archived.append({"scene": scene, "app_id": old.id, "status": "archived_disabled"})
            db.session.flush()
            if other_state() != before:
                raise RuntimeError("其他应用发生了意外变化")
            db.session.commit()
            print(json.dumps({"unified_app_id": target.id, "archived": archived, "other_apps_unchanged": True}, ensure_ascii=False))
            return

        imported = AppDslService(db.session).import_app(account=account, import_mode="yaml-content",
            yaml_content=args.dsl.read_text(encoding="utf-8"), app_id=target.id, name=APP_NAME)
        if imported.app_id != target.id or imported.status not in ("completed", "completed-with-warnings"):
            raise RuntimeError("统一 DSL 导入失败：" + str(imported.error))
        target = db.session.get(App, imported.app_id)
        published = WorkflowService().publish_workflow(session=db.session, app_model=target, account=account,
            marked_name="enterprise-unified-v1", marked_comment="合并 extract/query/knowledge/summary；保留业务契约")
        db.session.flush()
        target.workflow_id = published.id
        target.enable_api = True
        target.enable_site = True
        token = db.session.query(ApiToken).filter_by(app_id=target.id, type="app").first()
        if token is None:
            token = ApiToken(app_id=target.id, tenant_id=tenant.id, type="app", token=ApiToken.generate_api_key("app-", 32))
            db.session.add(token)
        db.session.flush()
        if other_state() != before:
            raise RuntimeError("其他应用发生了意外变化")
        db.session.commit()
        result = {"config": {"ENTERPRISE_DIFY_API_BASE": "http://127.0.0.1/v1", "ENTERPRISE_DIFY_API_KEY": token.token, "ENTERPRISE_DIFY_CONTRACT_VERSION": "enterprise-v1"},
                  "app": {"name": APP_NAME, "app_id": target.id, "workflow_id": published.id, "status": "published"}}
        Path("/tmp/stuproject-enterprise-unified.runtime.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"app": result["app"], "other_apps_unchanged": True, "secrets_written_to_runtime_file": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
