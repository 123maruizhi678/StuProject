"""隔离的 SQLite 测试库；不写入本机 MySQL。"""
from datetime import date
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.api.common.auth import router
from app.core.common.response import register_exception_handlers
from app.database import Base, get_db
from app.models.common import UserAccount, customer_profile, employee, org_department, student_profile
from app.services.common.auth_service import hash_password, create_access_token


class AuthCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password("test-password-123")

    def setUp(self):
        self.secret_patch = patch("app.config.settings.AUTH_SECRET_KEY", "unit-test-secret-not-a-real-key-123456789-123456789-123456789-123456789")
        self.secret_patch.start()
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.execute(insert(org_department).values(department_id=10, department_code="D10", department_name="测试部门"))
            roles = {20:["employee"], 21:["manager"], 22:["admin"], 23:["teacher"],
                     24:["academic"], 25:["analyst"], 26:["reviewer"], 27:["consultant"]}
            for key, value in roles.items():
                db.execute(insert(employee).values(employee_id=key, employee_no="E"+str(key),
                    full_name="测试员工", department_id=10, login_provider="local",
                    login_subject="test-"+str(key), role_codes=value, joined_date=date(2026,1,1)))
            db.execute(insert(student_profile).values(student_id=30, student_no="S30", full_name="测试学生",
                                                     department_id=10, status="active"))
            db.execute(insert(customer_profile).values(customer_id=40, customer_no="C40", full_name="测试客户",
                                                      department_id=10, source_channel="test"))
            accounts = [
                UserAccount(user_id=1, username="admin", identity_type="admin", password_hash=self.password_hash),
                UserAccount(user_id=2, username="student", identity_type="student", student_id=30, password_hash=self.password_hash),
                UserAccount(user_id=3, username="customer", identity_type="customer", customer_id=40, password_hash=self.password_hash),
            ]
            accounts += [UserAccount(user_id=key+100, username="employee"+str(key), identity_type="employee",
                                     employee_id=key, password_hash=self.password_hash) for key in roles]
            db.add_all(accounts)
            db.commit()
        self.app = FastAPI()
        register_exception_handlers(self.app)
        self.app.include_router(router, prefix="/api/v1")
        engine = self.engine
        def test_db():
            with Session(engine) as db:
                yield db
        self.app.dependency_overrides[get_db] = test_db
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        self.secret_patch.stop()

    def headers(self, user_id=1):
        with Session(self.engine) as db:
            token, _ = create_access_token(db.get(UserAccount, user_id))
        return {"Authorization":"Bearer "+token}
