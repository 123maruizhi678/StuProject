"""真实公共路由 + 虚构账号：密码、JWT、身份回查与迁移后的仓储。"""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.common import UserAccount, employee, student_profile, customer_profile, operation_log
from app.core.common.system_admin import admin_actor
from sqlalchemy import select
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
                self.assertEqual(data["identity_type"], identity)
                self.assertEqual(data["user_id"], expected_id)
                self.assertTrue(data["display_name"])
                result = self.client.get("/api/v1/auth/me/access", headers={"Authorization": "Bearer " + data["access_token"]})
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()["data"]["identity_type"], identity)
                self.assertEqual(result.json()["data"]["user_id"], expected_id)
                expected_name = {
                    "admin": "fake-admin", "employee": "虚构测试教师",
                    "student": "虚构测试学生", "customer": "虚构测试客户",
                }[identity]
                self.assertEqual(result.json()["data"]["display_name"], expected_name)
                self.assertEqual(data["display_name"], expected_name)
                self.assertNotIn("password_hash", result.text)

    def test_display_name_uses_current_linked_profile(self):
        token = self.login("fake-employee").json()["data"]["access_token"]
        with Session(self.engine) as db:
            db.execute(update(employee).where(employee.c.employee_id == 10).values(full_name="更新后的姓名"))
            db.commit()
        result = self.client.get(
            "/api/v1/auth/me/access?user_id=104&identity_type=customer",
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["data"]["display_name"], "更新后的姓名")
        self.assertEqual(result.json()["data"]["user_id"], 102)

    def test_public_access_does_not_include_account_name(self):
        result = self.client.get("/api/v1/auth/public-access")
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("display_name", result.json()["data"])

    def test_self_service_name_is_persistent_for_every_identity(self):
        for username in ("fake-admin", "fake-employee", "fake-student", "fake-customer"):
            with self.subTest(username=username):
                login = self.login(username).json()["data"]
                headers = {"Authorization": "Bearer " + login["access_token"]}
                result = self.client.patch("/api/v1/auth/me/profile", headers=headers, json={
                    "full_name": "  新姓名 " + username + "  ", "expected_full_name": login["display_name"],
                })
                self.assertEqual(result.status_code, 200, result.text)
                expected = "新姓名 " + username
                self.assertEqual(result.json()["data"]["display_name"], expected)
                self.assertEqual(self.client.get("/api/v1/auth/me/access", headers=headers).json()["data"]["display_name"], expected)
                self.assertEqual(self.login(username).json()["data"]["display_name"], expected)
                self.assertEqual(self.client.patch("/api/v1/auth/me/profile", headers=headers, json={
                    "full_name": "过时修改", "expected_full_name": login["display_name"],
                }).status_code, 409)
        with Session(self.engine) as db:
            for table, key, object_id, username in ((employee, "employee_id", 10, "fake-employee"),
                (student_profile, "student_id", 1, "fake-student"), (customer_profile, "customer_id", 20, "fake-customer")):
                row = db.execute(select(table).where(table.c[key] == object_id)).mappings().one()
                self.assertEqual(row["full_name"], "新姓名 " + username)
                self.assertEqual(row["row_version"], 2)
            self.assertEqual(admin_actor(db, 101)["full_name"], "新姓名 fake-admin")
            self.assertEqual(len(db.execute(select(operation_log).where(operation_log.c.action_code == "auth.profile.rename")).all()), 4)

    def test_self_service_name_rejects_impersonation_and_invalid_values(self):
        data = self.login("fake-student").json()["data"]
        headers = {"Authorization": "Bearer " + data["access_token"]}
        valid = {"full_name": "本人姓名", "expected_full_name": data["display_name"]}
        self.assertEqual(self.client.patch("/api/v1/auth/me/profile", json=valid).status_code, 401)
        for extra in ({"user_id": 101}, {"identity_type": "admin"}, {"username": "another"}):
            self.assertEqual(self.client.patch("/api/v1/auth/me/profile", headers=headers, json={**valid, **extra}).status_code, 422)
        for name in ("", "   ", "长" * 101, "姓\x00名", "姓名\n分行"):
            self.assertEqual(self.client.patch("/api/v1/auth/me/profile", headers=headers, json={**valid, "full_name": name}).status_code, 422)
        admin = self.login().json()["data"]
        self.assertEqual(admin["display_name"], "fake-admin")

    def test_self_service_name_preserves_external_customer_authority(self):
        data = self.login("fake-customer").json()["data"]
        with Session(self.engine) as db:
            db.execute(update(customer_profile).where(customer_profile.c.customer_id == 20).values(authority_source="crm"))
            db.commit()
        result = self.client.patch("/api/v1/auth/me/profile", headers={"Authorization": "Bearer " + data["access_token"]},
            json={"full_name": "不应覆盖", "expected_full_name": data["display_name"]})
        self.assertEqual(result.status_code, 409)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(customer_profile.c.full_name).where(customer_profile.c.customer_id == 20)), data["display_name"])
            self.assertEqual(len(db.execute(select(operation_log).where(operation_log.c.action_code == "auth.profile.rename")).all()), 0)

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
