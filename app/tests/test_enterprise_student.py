"""隔离数据库接口测试；不读取或改动真实数据库的业务记录。"""
from datetime import timedelta
from decimal import Decimal
import asyncio
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.response import BusinessException
from app.database import get_db
from app.main import app
from app.models.enterprise_student import Employee, OperationLog, StudentProfile, StudentScore, StudentStaffBinding
from app.models.user_account import UserAccount
from app.services import enterprise_nl2sql as nl
from app.services.auth_service import create_access_token, hash_password
from app.services.enterprise_student import utcnow

PREFIX = "/api/v1/enterprise"


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_SECRET_KEY", "isolated-test-secret-with-more-than-32-bytes")
    monkeypatch.setattr(settings, "ENTERPRISE_SCORE_AUTHORITY", "local")
    monkeypatch.setattr(settings, "ENTERPRISE_STUDENT_MAINTAINER_IDS", [])
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    tables = [m.__table__ for m in (Employee, StudentProfile, StudentStaffBinding, StudentScore, OperationLog)]
    for table in tables:
        table.create(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE user_account (user_id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, identity_type TEXT, employee_id INTEGER, customer_id INTEGER, student_id INTEGER, created_at DATETIME, updated_at DATETIME)")
    db = Session(engine, expire_on_commit=False)
    now = utcnow()
    db.add_all([Employee(employee_id=i, full_name=f"Test employee {i}", department_id=1,
        role_codes=roles, status=status) for i, roles, status in [
            (1, ["academic"], "active"), (2, ["teacher"], "active"), (3, ["academic"], "disabled"),
            (4, ["admin"], "active"), (5, ["academic"], "active")]])
    db.add_all([StudentProfile(student_id=i, student_no=f"S{i}", full_name=f"Student {i}", department_id=1,
        status="active", is_archived=(i == 5), external_student_id=f"EXTERNAL-{i}", crm_student_id=f"CRM-{i}") for i in range(1, 6)])
    db.add_all([StudentStaffBinding(binding_id=i, student_id=sid, employee_id=eid, relation_type=kind,
        course_scope_code=course, valid_from=start, valid_to=end, status="active")
        for i, sid, eid, kind, course, start, end in [
            (1, 1, 1, "score_editor", "EIT-ENGLISH", now - timedelta(days=1), None),
            (2, 2, 1, "score_editor", None, now - timedelta(days=1), None),
            (3, 3, 1, "score_editor", "EIT-ENGLISH", now - timedelta(days=2), now - timedelta(days=1)),
            (4, 4, 1, "score_editor", "EIT-ENGLISH", now + timedelta(days=1), None),
            (5, 1, 2, "class_teacher", None, now - timedelta(days=1), None),
            (6, 5, 1, "score_editor", "EIT-ENGLISH", now - timedelta(days=1), None)]])
    db.add_all([StudentScore(score_id=i, student_id=sid, course_code=course, term_code="T1", assessment_code="EXAM",
        attempt_no=1, score_value=80, max_score=100, employee_id=1, status="valid") for i, sid, course in [
            (1, 1, "EIT-ENGLISH"), (2, 1, "EIT-MATH"), (3, 2, "EIT-ENGLISH"), (4, 3, "EIT-ENGLISH")]])
    db.commit()
    password_hash = hash_password("test-login-password")
    db.execute(text("INSERT INTO user_account (user_id,username,password_hash,identity_type,employee_id) VALUES (1,'academic',:hash,'employee',1)"), {"hash": password_hash})
    db.commit()
    def database():
        yield db
    app.dependency_overrides[get_db] = database
    def headers(employee_id=1):
        # 其他账号用于验证 employee 状态与角色检查，不绕过认证依赖。
        account = db.get(UserAccount, employee_id)
        if account is None:
            db.execute(text("INSERT INTO user_account (user_id,username,password_hash,identity_type,employee_id) VALUES (:id,:name,:hash,'employee',:id)"),
                {"id": employee_id, "name": f"employee-{employee_id}", "hash": password_hash})
            db.commit()
            account = db.get(UserAccount, employee_id)
        token, _ = create_access_token(account)
        return {"Authorization": f"Bearer {token}"}
    with TestClient(app) as client:
        yield client, db, headers
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def payload(**changes):
    return {"student_id": 1, "course_code": "EIT-ENGLISH", "term_code": "T2", "assessment_code": "EXAM",
            "attempt_no": 1, "score_value": "85.25", "max_score": "100.00", **changes}


def test_authentication_and_employee_state(setup):
    client, _, headers = setup
    assert client.get(PREFIX + "/students").json()["code"] == 401
    for employee_id in (3, 4):
        assert client.get(PREFIX + "/students", headers=headers(employee_id)).json()["code"] == 403
    result = client.post("/api/v1/auth/login", json={"username": "academic", "password": "test-login-password"}).json()
    assert result["code"] == 0 and result["data"]["access_token"]


def test_student_filters_authorization_and_privacy(setup):
    client, _, headers = setup
    result = client.get(PREFIX + "/students", headers=headers()).json()["data"]
    assert {s["student_id"] for s in result["items"]} == {"1", "2"}
    assert all("external_student_id" not in s and "crm_student_id" not in s for s in result["items"])
    assert client.get(PREFIX + "/students?student_no=S1&department_id=1&keyword=Student&status=active&page_size=1", headers=headers()).json()["data"]["total"] == 1
    assert client.get(PREFIX + "/students?is_archived=true", headers=headers()).json()["data"]["items"][0]["student_id"] == "5"
    assert client.get(PREFIX + "/students/3", headers=headers()).json()["code"] == 404
    detail = client.get(PREFIX + "/students/1", headers=headers()).json()["data"]
    assert [b["employee_id"] for b in detail["staff_bindings"]] == ["1"]
    assert "mental" not in str(detail)


def test_score_course_scope_and_teacher_denial(setup):
    client, _, headers = setup
    assert client.get(PREFIX + "/scores", headers=headers(2)).json()["code"] == 403
    result = client.get(PREFIX + "/scores", headers=headers()).json()["data"]
    assert [s["score_id"] for s in result["items"]] == ["1"]
    assert result["items"][0]["course_name"] == "测试英语"
    for score_id in (2, 3, 4):
        assert client.get(PREFIX + f"/scores/{score_id}", headers=headers()).json()["code"] == 404


def test_create_replay_and_key_conflict(setup):
    client, db, headers = setup
    h = {**headers(), "Idempotency-Key": "create-1"}
    first = client.post(PREFIX + "/scores", json=payload(), headers=h).json()
    assert first["code"] == 0
    assert client.post(PREFIX + "/scores", json=payload(), headers=h).json() == first
    assert client.post(PREFIX + "/scores", json=payload(score_value="84.00"), headers=h).json()["code"] == 409
    assert db.scalar(select(func.count()).select_from(OperationLog)) == 1


def test_patch_audit_version_and_void_unique_key(setup):
    client, db, headers = setup
    h = headers()
    first = client.patch(PREFIX + "/scores/1", headers={**h,"Idempotency-Key":"correct-1"},
        json={"score_value":"90.00","expected_version":1,"change_reason":"核对原始试卷"}).json()
    assert first["code"] == 0 and first["data"]["version"] == 2
    stale = client.patch(PREFIX + "/scores/1", headers={**h,"Idempotency-Key":"correct-stale"},
        json={"max_score":"120.00","expected_version":1,"change_reason":"迟到请求"}).json()
    assert stale["code"] == 409
    detail = client.get(PREFIX + "/scores/1", headers=h).json()["data"]
    assert Decimal(detail["history"][0]["before"]["score_value"]) == 80
    assert Decimal(detail["history"][0]["after"]["score_value"]) == 90
    assert len(detail["history"]) == 1
    void = {"expected_version":2,"change_reason":"错误对象，保留记录"}
    assert client.post(PREFIX + "/scores/1/void", json=void, headers={**h,"Idempotency-Key":"void-1"}).json()["code"] == 0
    assert client.post(PREFIX + "/scores", json=payload(term_code="T1"), headers={**h,"Idempotency-Key":"duplicate-void"}).json()["code"] == 409
    assert client.get(PREFIX + "/scores?status=void", headers=h).json()["data"]["total"] == 1
    assert db.scalar(select(func.count()).select_from(OperationLog)) == 2


@pytest.mark.parametrize("changes", [{"max_score":0}, {"score_value":101}, {"score_value":-1}, {"attempt_no":0},
    {"attempt_no":True}, {"score_value":"NaN"}, {"score_value":"1.001"}, {"employee_id":999}])
def test_invalid_creates(setup, changes):
    client, _, headers = setup
    assert client.post(PREFIX + "/scores", json=payload(**changes), headers={**headers(),"Idempotency-Key":"invalid"}).json()["code"] == 400


def test_write_permissions_catalog_readonly_and_business_key(setup, monkeypatch):
    client, _, headers = setup
    h={**headers(),"Idempotency-Key":"invalid"}
    for changes in ({"course_code":"EIT-MATH"},{"student_id":2}):
        assert client.post(PREFIX + "/scores", json=payload(**changes), headers=h).json()["code"] == 403
    assert client.post(PREFIX + "/scores", json=payload(student_id=5), headers=h).json()["code"] == 409
    assert client.patch(PREFIX + "/scores/1", json={"student_id":2,"score_value":99,"expected_version":1,"change_reason":"搬移"}, headers=h).json()["code"] == 400
    assert client.patch(PREFIX + "/scores/1", json={"max_score":50,"expected_version":1,"change_reason":"满分小于得分"}, headers=h).json()["code"] == 400
    monkeypatch.setattr(settings,"ENTERPRISE_SCORE_AUTHORITY","external_readonly")
    assert client.post(PREFIX + "/scores", json=payload(), headers=h).json()["code"] == 403
    assert client.get(PREFIX + "/scores", headers=headers()).json()["code"] == 0


@pytest.mark.parametrize("sql", [
    "DELETE FROM student_score", "SELECT score_id FROM student_score", "SELECT * FROM authorized_students",
    "SELECT crm_student_id FROM authorized_students", "SELECT SLEEP(30) FROM authorized_students",
    "SELECT LOAD_FILE('/etc/passwd') FROM authorized_students", "SELECT student_id FROM authorized_students FOR UPDATE",
    "SELECT student_id FROM authorized_students; SELECT 1", "SELECT student_id FROM authorized_students UNION SELECT 1",
    "SELECT student_id FROM authorized_students WHERE EXISTS(SELECT 1)", "SELECT student_id FROM db.authorized_students",
    "SELECT student_id INTO OUTFILE '/tmp/x' FROM authorized_students", "SELECT student_id FROM authorized_students -- hi",
    "SELECT student_id FROM authorized_students LIMIT -1", "SELECT @x FROM authorized_students",
    "SELECT student_id FROM authorized_students JOIN authorized_scores USING(student_id)",
])
def test_nl2sql_rejects_unsafe_shapes(sql):
    with pytest.raises(BusinessException):
        nl.validate_query(sql)


def test_nl2sql_forces_row_scope_even_with_tautology(setup):
    _, db, _ = setup
    actor=db.get(Employee,1)
    result=nl.execute_query(db,actor,"SELECT score_id, score_value FROM authorized_scores WHERE 1=1 OR student_id=999 LIMIT 999")
    assert [row["score_id"] for row in result["rows"]] == ["1"]
    assert nl.validate_query("SELECT COUNT(*) AS total FROM authorized_students").args["limit"].expression.this == "200"


def test_nl2sql_endpoint_model_contract_and_teacher_scope(setup, monkeypatch):
    client, _, headers=setup
    async def fake_model(question, user, **kwargs):
        assert kwargs["api_base"] == settings.STUDENT_SCORE_DIFY_BASE
        assert "allowed_schema" in question
        return "SELECT student_no, full_name FROM authorized_students ORDER BY student_id"
    monkeypatch.setattr(nl,"call_nl2sql",fake_model)
    result=client.post(PREFIX+"/student-scores/nl-query",json={"question":"查学生"},headers=headers()).json()
    assert result["code"] == 0 and len(result["data"]["rows"]) == 2
    async def wrong_model(*args,**kwargs):
        return "SELECT score_id FROM authorized_scores"
    monkeypatch.setattr(nl,"call_nl2sql",wrong_model)
    assert client.post(PREFIX+"/student-scores/nl-query",json={"question":"查成绩"},headers=headers(2)).json()["code"] == 403


def test_dify_failure_is_sanitized(setup, monkeypatch):
    client, _, headers=setup
    async def broken(*args, **kwargs):
        raise RuntimeError("secret credentials")
    monkeypatch.setattr(nl,"call_nl2sql",broken)
    result=client.post(PREFIX+"/student-scores/nl-query",json={"question":"查学生"},headers=headers()).json()
    assert result["code"] == 503 and "secret" not in str(result)


@pytest.mark.parametrize("status,output,valid", [("succeeded","SELECT student_id FROM authorized_students",True),
    ("failed","SELECT 1",False),("succeeded",None,False),("succeeded",123,False)])
def test_dify_http_workflow_contract(monkeypatch,status,output,valid):
    from app.core import dify
    factory=httpx.AsyncClient
    def handler(request):
        assert request.url.path == "/v1/workflows/run"
        assert request.headers["Authorization"] == "Bearer isolated-test-key"
        body=json.loads(request.content)
        assert body == {"inputs":{"question":"synthetic question"},"response_mode":"blocking","user":"test-user"}
        return httpx.Response(200,json={"data":{"status":status,"outputs":{"sql":output}}})
    monkeypatch.setattr(dify.httpx,"AsyncClient",lambda **kwargs:factory(transport=httpx.MockTransport(handler),**kwargs))
    call=dify.call_nl2sql("synthetic question",user="test-user",api_base="http://localhost/v1",api_key="isolated-test-key")
    if valid:
        assert asyncio.run(call)==output
    else:
        with pytest.raises(ValueError):
            asyncio.run(call)
