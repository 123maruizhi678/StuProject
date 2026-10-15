"""隔离测试。默认SQLite；设置STUDENT_TEST_MYSQL_URL后同时验证真实MySQL约束。"""

import os
import re
from datetime import date, timedelta
from pathlib import Path
import pytest
from sqlalchemy import create_engine, event, insert, delete, text
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
from app.config import settings
from app.core.student_auth import sign_token
from app.models import student_shared as shared
from app.models.student_types import utcnow
from app.models.student import STUDENT_TABLES


@pytest.fixture(scope="session", params=["sqlite", "mysql"])
def test_engine(request):
    if request.param == "mysql":
        url = os.environ.get("STUDENT_TEST_MYSQL_URL")
        if not url:
            pytest.skip("未配置隔离MySQL测试库")
        engine = create_engine(url, pool_pre_ping=True)
        if not engine.url.database or not re.fullmatch(
            r"student_test_[a-z0-9_]+", engine.url.database
        ):
            raise RuntimeError("测试仅允许student_test_前缀的独立数据库")
        sql = (
            Path(__file__).resolve().parents[1]
            / "scripts/sql/企业智能助手/企业智能助手_建表.sql"
        ).read_text(encoding="utf-8")
        blocks = re.findall(
            r"CREATE TABLE(?: IF NOT EXISTS)?\s+\x60?\w+\x60?\s*\([\s\S]*?\n\) ENGINE[^;]*;",
            sql,
            re.I,
        )
        with engine.begin() as conn:
            for statement in blocks:
                conn.exec_driver_sql(statement)
            conn.exec_driver_sql(
                "ALTER TABLE student_profile ADD COLUMN crm_student_id VARCHAR(128) COLLATE utf8mb4_bin NULL UNIQUE"
            )
            conn.exec_driver_sql(
                "INSERT INTO org_department(department_code,department_name) VALUES ('TEST','测试部门')"
            )
    else:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )

        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        shared.shared_metadata.create_all(engine)
    Base.metadata.create_all(engine, tables=list(STUDENT_TABLES))
    yield engine
    engine.dispose()


@pytest.fixture
def sessions(test_engine):
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    # 只清理测试库中的学生功能数据。正式数据库从不由测试访问。
    with factory() as db:
        for table in reversed(list(Base.metadata.sorted_tables)):
            db.execute(delete(table))
        for name in (
            "business_notification",
            "service_ticket_record",
            "operation_log",
            "service_ticket",
            "student_leave_request",
            "student_staff_binding",
            "student_profile",
            "employee",
        ):
            db.execute(delete(getattr(shared, name)))
        for employee_id in (1, 2, 3):
            db.execute(
                insert(shared.employee).values(
                    employee_id=employee_id,
                    employee_no=f"E{employee_id}",
                    full_name="测试老师",
                    department_id=1,
                    login_provider="test",
                    login_subject=f"teacher{employee_id}",
                    role_codes=["teacher"],
                    status="active",
                    joined_date=date(2026, 1, 1),
                )
            )
        for student_id in (1, 2):
            db.execute(
                insert(shared.student_profile).values(
                    student_id=student_id,
                    student_no=f"S{student_id}",
                    full_name="测试学生",
                    department_id=1,
                    status="active",
                    external_student_id=f"external-{student_id}",
                    crm_student_id=f"crm-{student_id}",
                    is_archived=False,
                )
            )
            db.execute(
                insert(shared.student_staff_binding).values(
                    student_id=student_id,
                    employee_id=student_id,
                    relation_type="class_teacher",
                    is_primary=True,
                    status="active",
                    valid_from=utcnow() - timedelta(days=1),
                )
            )
        db.commit()
    yield factory


@pytest.fixture
def db(sessions):
    with sessions() as session:
        yield session


@pytest.fixture(autouse=True)
def config(monkeypatch):
    monkeypatch.setattr(settings, "STUDENT_AUTH_SECRET", "test-only-secret-" * 4)
    monkeypatch.setattr(settings, "STUDENT_FALLBACK_EMPLOYEE_ID", None)


@pytest.fixture
def client(sessions):
    from fastapi.testclient import TestClient

    def database_override():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def student_headers():
    return lambda student_id=1, key="request-0001": {
        "Authorization": "Bearer "
        + sign_token({"actor_type": "student", "actor_id": student_id}),
        "Idempotency-Key": key,
    }
