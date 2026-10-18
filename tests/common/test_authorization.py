"""依赖鉴权真实接入；不接受客户端自报角色作为授权依据。"""
import unittest
from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.core.common.authorization import access_for, public_access, require_permission
from app.database import get_db
from app.models.common import UserAccount
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
