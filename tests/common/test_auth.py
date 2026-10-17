"""真实公共路由 + 虚构账号：密码、JWT、身份回查与迁移后的仓储。"""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.common import UserAccount
from app.repositories.common.account_repository import AccountRepository
from tests.common.support import TEST_PASSWORD, TEST_SECRET, make_engine, seed_people


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.engine = make_engine()
        with Session(self.engine) as db:
            seed_people(db, accounts=True)
        self.original_overrides = app.dependency_overrides.copy()

        def database():
            with Session(self.engine) as db:
                yield db

        app.dependency_overrides[get_db] = database
        self.secret = patch.object(settings, "AUTH_SECRET_KEY", TEST_SECRET)
        self.secret.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.original_overrides)
        self.secret.stop()
        self.engine.dispose()

    def login(self, username="fake-admin", password=TEST_PASSWORD):
        return self.client.post("/api/v1/auth/login", json={"username": username, "password": password})

    def test_successful_login_and_actual_linked_identity(self):
        for username, identity, expected_id in (("fake-admin", "admin", 101), ("fake-employee", "employee", 102), ("fake-student", "student", 103), ("fake-customer", "customer", 104)):
            with self.subTest(identity=identity):
                result = self.login(username)
                self.assertEqual(result.status_code, 200)
                data = result.json()["data"]
                self.assertEqual(data["token_type"], "bearer")
                self.assertGreater(data["expires_in"], 0)
                result = self.client.get("/api/v1/auth/me/access", headers={"Authorization": "Bearer " + data["access_token"]})
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()["data"]["identity_type"], identity)
                self.assertEqual(result.json()["data"]["user_id"], expected_id)
                self.assertNotIn("password_hash", result.text)

    def test_wrong_password_and_unknown_user_return_same_failure(self):
        wrong = self.login(password="fake-wrong-password")
        unknown = self.login(username="fake-missing")
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(wrong.json(), unknown.json())
        self.assertEqual(wrong.headers["www-authenticate"], "Bearer")

    def test_missing_bad_expired_and_wrong_signature_tokens(self):
        now = datetime.now(timezone.utc)
        expired = jwt.encode({"sub": "101", "exp": now - timedelta(minutes=1)}, TEST_SECRET, algorithm="HS256")
        wrong = jwt.encode({"sub": "101", "exp": now + timedelta(minutes=1)}, TEST_SECRET + "wrong", algorithm="HS256")
        for token in (None, "malformed", expired, wrong):
            headers = {"Authorization": "Bearer " + token} if token else {}
            with self.subTest(token_type="missing" if token is None else "invalid"):
                result = self.client.get("/api/v1/auth/me/access", headers=headers)
                self.assertEqual(result.status_code, 401)

    def test_valid_token_cannot_authenticate_deleted_account(self):
        token = self.login().json()["data"]["access_token"]
        with Session(self.engine) as db:
            db.execute(delete(UserAccount).where(UserAccount.user_id == 101))
            db.commit()
        result = self.client.get("/api/v1/auth/me/access", headers={"Authorization": "Bearer " + token})
        self.assertEqual(result.status_code, 401)

    def test_client_identity_cannot_override_account(self):
        result = self.client.post("/api/v1/auth/login", json={"username": "fake-student", "password": TEST_PASSWORD, "identity_type": "admin", "permissions": ["report.read"]})
        token = result.json()["data"]["access_token"]
        access = self.client.get("/api/v1/auth/me/access", headers={"Authorization": "Bearer " + token}).json()["data"]
        self.assertEqual(access["identity_type"], "student")
        self.assertNotIn("report.read", access["permissions"])

    def test_report_uses_common_identity_and_business_envelope(self):
        result = self.client.get("/api/v1/report/configs")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["code"], 401)
        token = self.login("fake-student").json()["data"]["access_token"]
        result = self.client.get("/api/v1/report/configs", headers={"Authorization": "Bearer " + token})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["code"], 403)

    def test_public_frontend_and_local_assets_are_available(self):
        for path in ("/", "/login", "/account", "/static/js/common/api.js", "/static/css/common/style.css"):
            with self.subTest(path=path):
                result = self.client.get(path)
                self.assertEqual(result.status_code, 200)
        self.assertIn("text/html", self.client.get("/").headers["content-type"])
        self.assertEqual(self.client.get("/health").json()["code"], 0)

    def test_account_repository_refreshes_identity(self):
        with Session(self.engine) as db, Session(self.engine) as other:
            repository = AccountRepository(db)
            self.assertEqual(repository.get_by_id(101).identity_type, "admin")
            # 避免学生关联唯一约束与原测试学生账号冲突。
            other.execute(delete(UserAccount).where(UserAccount.user_id == 103))
            account = other.get(UserAccount, 101)
            account.identity_type, account.student_id = "student", 1
            other.commit()
            self.assertEqual(repository.get_by_id(101).identity_type, "student")
