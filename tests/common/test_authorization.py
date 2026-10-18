"""依赖鉴权真实接入；不接受客户端自报角色作为授权依据。"""
import unittest
from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import settings
from app.core.common.authorization import access_for, public_access, require_permission
from app.database import get_db
from app.models.common import UserAccount, employee
from app.core.common.navigation import account_access, navigation_for
from app.services.common.auth_service import create_access_token
from tests.common.support import TEST_SECRET, make_engine, seed_people


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.engine = make_engine()
        with Session(self.engine) as db:
            seed_people(db, accounts=True)
        self.secret = patch.object(settings, "AUTH_SECRET_KEY", TEST_SECRET)
        self.secret.start()
        app = FastAPI()

        @app.get("/protected")
        def protected(account=Depends(require_permission("report.read"))):
            return {"user_id": account.user_id}

        def database():
            with Session(self.engine) as db:
                yield db

        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.addCleanup(self.secret.stop)
        self.addCleanup(self.engine.dispose)

    def headers(self, user_id):
        with Session(self.engine) as db:
            token, _ = create_access_token(db.get(UserAccount, user_id))
        return {"Authorization": "Bearer " + token}

    def test_anonymous_is_denied_and_admin_allowed(self):
        self.assertEqual(self.client.get("/protected").status_code, 401)
        self.assertEqual(self.client.get("/protected", headers=self.headers(101)).status_code, 200)

    def test_other_identities_cannot_claim_admin_via_headers_or_query(self):
        for user_id in (102, 103, 104):
            headers = {**self.headers(user_id), "X-Identity-Type": "admin"}
            result = self.client.get("/protected?identity_type=admin", headers=headers)
            self.assertEqual(result.status_code, 403)

    def test_role_change_takes_effect_for_existing_token(self):
        headers = self.headers(101)
        with Session(self.engine) as db:
            # 撤销该身份的所有权限后，原令牌仍必须按当前权限计算。
            policy = {"roles": {"admin": {"permissions": []}}, "pages": {}, "modules": {}}
            with patch("app.core.common.authorization.load_access_control", return_value=policy):
                self.assertEqual(self.client.get("/protected", headers=headers).status_code, 403)

    def test_public_and_student_access_lists(self):
        public = public_access()
        self.assertIn("login", public["pages"])
        self.assertIn("agent", public["pages"])
        self.assertNotIn("report", public["pages"])
        student = access_for("student", 103)
        self.assertIn("student_workspace", student["modules"])
        self.assertNotIn("report_center", student["modules"])

    def test_navigation_matches_each_identity_and_existing_permissions(self):
        expected = {
            101: {"agent_center", "customer_research", "employee_workspace", "report_center", "admin_workspace", "account_center"},
            102: {"agent_center", "employee_workspace", "account_center"},
            103: {"agent_center", "student_workspace", "account_center"},
            104: {"agent_center", "account_center"},
        }
        with Session(self.engine) as db:
            for user_id, modules in expected.items():
                access = account_access(db, db.get(UserAccount, user_id))
                self.assertEqual({item["id"] for item in access["navigation"]["modules"]}, modules)
                self.assertIn("/common/workspace.html", access["navigation"]["routes"])
            student = account_access(db, db.get(UserAccount, 103))
            self.assertNotIn("/enterprise/scores.html", student["navigation"]["routes"])
            self.assertNotIn("/admin/accounts.html", student["navigation"]["routes"])
        public = navigation_for(set(), None)
        self.assertEqual({item["id"] for item in public["modules"]}, {"agent_center"})
        self.assertNotIn("/common/workspace.html", public["routes"])

    def test_employee_role_union_and_revocation_take_effect_without_new_login(self):
        with Session(self.engine) as db:
            account = db.get(UserAccount, 102)
            teacher = account_access(db, account)["navigation"]["routes"]
            self.assertIn("/enterprise/scores.html", teacher)
            self.assertNotIn("/enterprise/customers.html", teacher)
            db.execute(update(employee).where(employee.c.employee_id == 10).values(role_codes=["teacher", "consultant"]))
            db.commit()
            both = account_access(db, account)["navigation"]["routes"]
            self.assertIn("/enterprise/scores.html", both)
            self.assertIn("/enterprise/customers.html", both)
            db.execute(update(employee).where(employee.c.employee_id == 10).values(role_codes=["consultant"]))
            db.commit()
            consultant = account_access(db, account)["navigation"]["routes"]
            self.assertNotIn("/enterprise/scores.html", consultant)
            self.assertIn("/enterprise/customers.html", consultant)

    def test_employee_admin_uses_account_admin_guard_without_new_report_grants(self):
        with Session(self.engine) as db:
            db.execute(update(employee).where(employee.c.employee_id == 10).values(role_codes=["admin"]))
            db.commit()
            access = account_access(db, db.get(UserAccount, 102))
            self.assertIn("/admin/accounts.html", access["navigation"]["routes"])
            self.assertNotIn("report.read", access["permissions"])
            self.assertNotIn("/report/report.html", access["navigation"]["routes"])

    def test_manager_gets_read_only_research_and_report_navigation(self):
        with Session(self.engine) as db:
            db.execute(update(employee).where(employee.c.employee_id == 10).values(role_codes=["manager"]))
            db.commit()
            account = db.get(UserAccount, 102)
            access = account_access(db, account)
            routes = access["navigation"]["routes"]
            for route in ("/customer/customer.html", "/customer/sources.html", "/customer/source-detail.html",
                "/customer/results.html", "/customer/result-detail.html", "/customer/rules.html", "/customer/products.html",
                "/report/report.html", "/report/list.html", "/report/detail.html"):
                self.assertIn(route, routes)
            for route in ("/customer/extract.html", "/report/generate.html", "/report/configs.html"):
                self.assertNotIn(route, routes)
            for permission in ("customer.source.create", "customer.source.parse", "customer.judge.create",
                "customer.rule.manage", "report.generate", "report.config.read", "report.config.write"):
                self.assertNotIn(permission, access["permissions"])
            db.execute(update(employee).where(employee.c.employee_id == 10).values(role_codes=["teacher"]))
            db.commit()
            revoked = account_access(db, account)
            self.assertNotIn("/customer/results.html", revoked["navigation"]["routes"])
            self.assertNotIn("/report/list.html", revoked["navigation"]["routes"])
