"""完整共享映射的虚构数据；仅创建 SQLite 内存数据库。"""
from datetime import date
from functools import lru_cache

from sqlalchemy import create_engine, event, insert
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import common as t
from app.services.common.auth_service import hash_password

TEST_PASSWORD = "Fictional!2026"
TEST_SECRET = "fictional-common-signing-key-for-tests-only-2026"


@lru_cache(maxsize=1)
def password_hash():
    return hash_password(TEST_PASSWORD)


def make_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    tables = [t.UserAccount.__table__ if name == "UserAccount" else getattr(t, name) for name in t.__all__]
    Base.metadata.create_all(engine, tables=tables)
    return engine


def seed_people(db: Session, *, accounts=False):
    db.execute(insert(t.org_department).values(department_id=7, department_code="FAKE-D07", department_name="虚构测试部门"))
    db.execute(insert(t.employee).values(employee_id=10, employee_no="FAKE-E10", full_name="虚构测试教师", department_id=7,
               login_provider="test", login_subject="fake-employee-10", role_codes=["teacher"], joined_date=date(2026, 1, 1)))
    db.execute(insert(t.customer_profile).values(customer_id=20, customer_no="FAKE-C20", full_name="虚构测试客户", source_channel="test", department_id=7))
    db.execute(insert(t.student_profile).values(student_id=1, student_no="FAKE-S01", full_name="虚构测试学生", department_id=7, status="active"))
    if accounts:
        for user_id, username, identity_type, link in (
            (101, "fake-admin", "admin", {}),
            (102, "fake-employee", "employee", {"employee_id": 10}),
            (103, "fake-student", "student", {"student_id": 1}),
            (104, "fake-customer", "customer", {"customer_id": 20}),
        ):
            db.add(t.UserAccount(user_id=user_id, username=username, password_hash=password_hash(), identity_type=identity_type, **link))
    db.commit()
