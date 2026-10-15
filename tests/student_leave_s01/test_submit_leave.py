"""S01业务HTTP验证；公共入口身份只在测试中注入，不实现JWT。"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, insert, select, update
from sqlalchemy.orm import sessionmaker
from app.student_leave.api import create_router
from app.student_leave import tables as t

@pytest.fixture
def unit(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 's01.sqlite'}")
    t.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with sessions.begin() as db:
        db.execute(insert(t.student_profile), [
            dict(student_id=7, status="active", is_archived=False),
            dict(student_id=8, status="active", is_archived=False)])
        db.execute(insert(t.employee), [
            dict(employee_id=11, status="active", role_codes=["teacher"]),
            dict(employee_id=12, status="active", role_codes=["advisor"]),
            dict(employee_id=13, status="disabled", role_codes=["teacher"])])
        db.execute(insert(t.student_staff_binding), [
            dict(binding_id=n, student_id=7, employee_id=staff, relation_type="class_teacher",
                 is_primary=n != 3, status="active", valid_from=now-timedelta(days=1), valid_to=None)
            for n, staff in [(1,12),(2,13),(3,11)]])
    actor = SimpleNamespace(identity_type="student", user_id=907, student_id=7)
    def current_account():
        return actor
    def get_db():
        with sessions() as db:
            yield db
    app = FastAPI()
    app.include_router(create_router(current_account, get_db), prefix="/api/v1")
    with TestClient(app, raise_server_exceptions=False) as client:
        yield SimpleNamespace(engine=engine, sessions=sessions, actor=actor, client=client,
                              app=app, account_dependency=current_account)
    engine.dispose()

def body():
    return dict(leave_content="因身体不适申请请假", leave_type="sick",
                leave_start_at="2026-10-20T09:00:00+08:00", leave_end_at="2026-10-20T18:00:00+08:00")
def post(unit, payload=None, key="s01-test-001"):
    return unit.client.post("/api/v1/student/leave", json=payload or body(), headers={"Idempotency-Key":key})
def count(unit, table):
    with unit.sessions() as db:
        return db.scalar(select(func.count()).select_from(table))

def test_submit_owner_teacher_notification_and_audit(unit):
    response = post(unit)
    assert response.status_code == 200
    receipt = response.json()["data"]
    assert receipt == dict(apply_id=1, approval_status="pending", reviewer_id=11, row_version=1,
                           assignment_pending=False, notification_queued=True)
    with unit.sessions() as db:
        row = db.execute(select(t.student_admin_service)).mappings().one()
        assert row["student_id"] == 7 and row["apply_type"] == "leave"
        assert row["edu_related_data"] == dict(leave_type="sick")
        assert row["leave_start_at"] == datetime(2026,10,20,1)
        notice = db.execute(select(t.business_notification)).mappings().one()
        assert notice["employee_id"] == 11 and notice["delivery_status"] == "pending"
        assert body()["leave_content"] not in notice["content"]
        audit = db.execute(select(t.operation_log)).mappings().one()
        assert audit["operation_status"] == "succeeded" and audit["result_reference"] == receipt

def test_replay_without_duplicate_writes(unit):
    assert post(unit).json() == post(unit).json()
    assert [count(unit,x) for x in (t.student_admin_service,t.business_notification,t.operation_log)] == [1,1,1]
def test_equivalent_timezones(unit):
    first = post(unit)
    equivalent = body() | dict(leave_start_at="2026-10-20T01:00:00Z",leave_end_at="2026-10-20T10:00:00Z")
    assert post(unit,equivalent).json() == first.json()
def test_changed_parameters_conflict(unit):
    post(unit)
    assert post(unit,body() | dict(leave_content="另一份请假")).status_code == 409
    assert count(unit,t.student_admin_service) == 1
def test_key_scoped_to_student(unit):
    assert post(unit).status_code == 200
    unit.actor.student_id = 8
    assert post(unit).status_code == 200 and count(unit,t.student_admin_service) == 2
def test_unassigned_request_is_preserved(unit):
    unit.actor.student_id = 8
    receipt = post(unit).json()["data"]
    assert receipt["assignment_pending"] and receipt["reviewer_id"] is None
    assert not receipt["notification_queued"]
    assert count(unit,t.student_admin_service) == 1 and count(unit,t.business_notification) == 0

@pytest.mark.parametrize("field,value",[("leave_content","  "),("student_id",8),("reviewer_id",999),
    ("approval_status","approved"),("leave_start_at","2026-10-20T09:00:00"),
    ("leave_end_at","2026-10-19T18:00:00+08:00")])
def test_bad_or_forged_payload(unit,field,value):
    assert post(unit,body() | {field:value}).status_code == 422
    assert count(unit,t.student_admin_service) == 0
@pytest.mark.parametrize("key",[None,"bad key","a"*129])
def test_bad_idempotency_key(unit,key):
    headers = {} if key is None else {"Idempotency-Key":key}
    assert unit.client.post("/api/v1/student/leave",json=body(),headers=headers).status_code == 422
    assert count(unit,t.student_admin_service) == 0
def test_wrong_identity(unit):
    unit.actor.identity_type = "employee"
    assert post(unit).status_code == 403 and count(unit,t.student_admin_service) == 0
@pytest.mark.parametrize("change",[dict(is_archived=True),dict(status="disabled")])
def test_disabled_identity_cannot_replay(unit,change):
    assert post(unit).status_code == 200
    with unit.sessions.begin() as db:
        db.execute(update(t.student_profile).where(t.student_profile.c.student_id==7).values(**change))
    assert post(unit).status_code == 403 and count(unit,t.student_admin_service) == 1
def test_expired_binding_not_used(unit):
    with unit.sessions.begin() as db:
        db.execute(update(t.student_staff_binding).where(t.student_staff_binding.c.employee_id==11)
                   .values(valid_to=datetime(2026,1,1)))
    assert post(unit).json()["data"]["assignment_pending"]
def test_public_dependency_can_reject(unit):
    def rejected():
        raise HTTPException(401,"公共入口拒绝的测试身份")
    unit.app.dependency_overrides[unit.account_dependency] = rejected
    assert post(unit).status_code == 401 and count(unit,t.student_admin_service) == 0
def test_transaction_rolls_back_when_notification_fails(unit):
    def fail(conn,cursor,statement,parameters,context,executemany):
        if statement.startswith("INSERT INTO business_notification"):
            raise RuntimeError("test notification failure")
    event.listen(unit.engine,"before_cursor_execute",fail)
    try:
        assert post(unit).status_code == 500
    finally:
        event.remove(unit.engine,"before_cursor_execute",fail)
    assert count(unit,t.student_admin_service) == count(unit,t.operation_log) == 0
    assert post(unit).status_code == 200
def test_openapi(unit):
    schema = unit.client.get("/openapi.json").json()
    assert set(schema["paths"]) == {"/api/v1/student/leave"}
    operation = schema["paths"]["/api/v1/student/leave"]["post"]
    assert any(p["name"]=="Idempotency-Key" and p["required"] for p in operation["parameters"])
    assert "422" in operation["responses"] and "409" in operation["responses"]
