"""目录迁移的回归验证：导入、共享表、静态资源和报告脚本；无真实外部调用。"""
import importlib
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

class LayoutContracts(unittest.TestCase):
    def test_shared_tables_have_one_metadata(self):
        from app.database import Base
        from app.models import common
        for name in common.__all__:
            item = getattr(common, name)
            table = item.__table__ if name == "UserAccount" else item
            self.assertIs(table.metadata, Base.metadata)
            self.assertIs(Base.metadata.tables[table.name], table)

    def test_available_business_modules_import(self):
        for name in [
            "app.api.common.auth", "app.api.agent.agent", "app.api.report.report",
            "app.services.student.student_leave_service",
            "app.repositories.student.student_leave_repository",
            "app.clients.agent.dify_client", "app.clients.report.report_dify",
        ]:
            self.assertIsNotNone(importlib.import_module(name))

    def test_canonical_shared_columns_match_existing_sql(self):
        import sqlglot
        from sqlglot import exp
        from app.models import common
        sql = (ROOT / "scripts/sql/all.sql").read_text(encoding="utf-8-sig")
        for name in ("org_department", "customer_profile", "student_score", "service_ticket", "service_ticket_record"):
            ddl = re.search(r"CREATE TABLE `?" + name + r"`?\s*\(.*?;", sql, re.S).group()
            parsed = sqlglot.parse_one(ddl, read="mysql")
            expected = [column.name for column in parsed.this.expressions if isinstance(column, exp.ColumnDef)]
            # 36表文件为原始基线；企业增量单独登记，不能把合法新增列视为缺失基线。
            actual=list(getattr(common,name).columns.keys())
            self.assertEqual([column for column in actual if column in expected],expected,name)
            extras=set(actual)-set(expected)
            self.assertEqual(extras,{'sla_snapshot'} if name=='service_ticket_record' else set(),name)

    def test_application_openapi_has_unique_operations(self):
        from app.main import app, MIGRATION_PENDING_MODULES
        schema = app.openapi()
        operations = [(path, method) for path, methods in schema["paths"].items()
                      for method in methods if method in {"get", "post", "put", "patch", "delete"}]
        self.assertEqual(len(operations), len(set(operations)))
        self.assertIn("/api/v1/auth/login", schema["paths"])
        self.assertIn("/api/v1/report/generate", schema["paths"])
        self.assertNotIn("/api/v1/agent/chat", schema["paths"])
        self.assertIn("student_leave", MIGRATION_PENDING_MODULES)

    def test_frontend_local_resources_exist(self):
        html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
        assets = re.findall(r'(?:src|href)="(/static/[^"?]+)', html)
        self.assertEqual(len(assets), 5)
        for asset in assets:
            self.assertTrue((ROOT / "frontend" / asset.removeprefix("/static/")).is_file(), asset)

    def test_relocated_report_script_dry_run(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/report/init_report_tables.py"), "--dry-run"],
                                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("CREATE TABLE"), 3)

    def test_shared_projection_preserves_leave_transaction_and_replay(self):
        from datetime import datetime, timedelta, timezone
        from types import SimpleNamespace
        from sqlalchemy import create_engine, func, insert, select
        from sqlalchemy.orm import Session
        from app.models import common as t
        from app.schemas.student.student_leave import LeaveAnalysis, LeaveInput
        from app.services.student.student_leave_service import LeaveError, StudentLeaveService

        engine = create_engine("sqlite://")
        tables = [t.student_profile, t.employee, t.student_staff_binding,
                  t.student_admin_service, t.business_notification, t.operation_log]
        t.student_profile.metadata.create_all(engine, tables=tables)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with Session(engine) as db:
            db.execute(insert(t.student_profile).values(student_id=1, status="active", is_archived=False))
            db.execute(insert(t.employee).values(employee_id=10, status="active", role_codes=["teacher"]))
            db.execute(insert(t.student_staff_binding).values(
                binding_id=1, student_id=1, employee_id=10, relation_type="class_teacher",
                is_primary=True, status="active", valid_from=now-timedelta(days=1)))
            db.commit()

            class Workflow:
                calls = 0
                def analyze_leave(self, student_id, payload):
                    self.calls += 1
                    return LeaveAnalysis(summary="测试请假摘要", review_points=["核实请假时间"],
                                         workflow_run_id="fake-run", analysis_version="test-v1")

            workflow = Workflow()
            service = StudentLeaveService(db, workflow)
            account = SimpleNamespace(identity_type="student", student_id=1)
            start = datetime.now(timezone.utc)+timedelta(days=1)
            payload = LeaveInput(leave_content="迁移回归测试", leave_type="personal",
                                 leave_start_at=start, leave_end_at=start+timedelta(hours=1))
            receipt = service.submit(account, "test-layout-request", payload)
            replay = service.submit(account, "test-layout-request", payload)
            self.assertEqual(receipt, replay)
            self.assertEqual(workflow.calls, 1)
            self.assertEqual(receipt["reviewer_id"], 10)
            for table in (t.student_admin_service, t.operation_log, t.business_notification):
                self.assertEqual(db.scalar(select(func.count()).select_from(table)), 1)
            changed = payload.model_copy(update={"leave_content": "不同参数"})
            with self.assertRaises(LeaveError) as caught:
                service.submit(account, "test-layout-request", changed)
            self.assertEqual(caught.exception.status, 409)
            self.assertEqual(workflow.calls, 1)
        engine.dispose()

    def test_existing_http_endpoints_without_external_dependencies(self):
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as client:
            self.assertEqual(client.get("/").status_code, 200)
            response = client.get("/api/v1/auth/public-access")
            self.assertEqual(response.status_code, 200)

if __name__ == "__main__":
    unittest.main()
