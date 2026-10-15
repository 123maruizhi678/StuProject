"""S01业务HTTP验证；公共入口身份只在测试中注入，不实现JWT。"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, insert, select, update
from sqlalchemy.orm import sessionmaker
import httpx
import json
from app.api.student_leave import create_router
from app.clients.student_leave_dify import StudentLeaveDifyClient
from app.config import StudentLeaveDifySettings
from app.models import student_leave as t

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
    live_sessions = []
    def get_db():
        with sessions() as db:
            live_sessions.append(db)
            try:
                yield db
            finally:
                live_sessions.remove(db)
    workflow_requests = []
    def upstream(request):
        workflow_requests.append(json.loads(request.content))
        assert request.url.path == "/v1/workflows/run"
        assert request.headers["Authorization"] == "Bearer test-only-workflow-key"
        assert all(not db.in_transaction() for db in live_sessions)
        return httpx.Response(200, json={
            "workflow_run_id": "mock-run-001", "data": {"status": "succeeded", "outputs": {
                "result": json.dumps({"summary": "学生因身体不适申请请假。", "review_points": ["请老师人工核实请假安排。"]}, ensure_ascii=False)
            }}
        })
    config = StudentLeaveDifySettings(_env_file=None, STUDENT_DIFY_LEAVE_BASE="http://dify-test.local/v1", STUDENT_DIFY_LEAVE_VERSION="student-leave-v1", STUDENT_DIFY_LEAVE_KEY="test-only-workflow-key")
    workflow = StudentLeaveDifyClient(config, httpx.MockTransport(upstream))
    def get_workflow():
        return workflow
    app = FastAPI()
    app.include_router(create_router(current_account, get_db, get_workflow), prefix="/api/v1")
    with TestClient(app, raise_server_exceptions=False) as client:
        yield SimpleNamespace(engine=engine, sessions=sessions, actor=actor, client=client,
                              app=app, account_dependency=current_account, workflow=workflow, workflow_requests=workflow_requests)
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
                           assignment_pending=False, notification_queued=True,
                           ai_analysis={"summary": "学生因身体不适申请请假。", "review_points": ["请老师人工核实请假安排。"],
                                        "workflow_run_id": "mock-run-001", "analysis_version": "student-leave-v1"})
    with unit.sessions() as db:
        row = db.execute(select(t.student_admin_service)).mappings().one()
        assert row["student_id"] == 7 and row["apply_type"] == "leave"
        assert row["edu_related_data"] == dict(leave_type="sick", ai_analysis=receipt["ai_analysis"])
        assert row["leave_start_at"] == datetime(2026,10,20,1)
        notice = db.execute(select(t.business_notification)).mappings().one()
        assert notice["employee_id"] == 11 and notice["delivery_status"] == "pending"
        assert body()["leave_content"] not in notice["content"]
        audit = db.execute(select(t.operation_log)).mappings().one()
        assert audit["operation_status"] == "succeeded" and audit["result_reference"] == receipt

def test_replay_without_duplicate_writes(unit):
    assert post(unit).json() == post(unit).json()
    assert [count(unit,x) for x in (t.student_admin_service,t.business_notification,t.operation_log)] == [1,1,1]
    assert len(unit.workflow_requests) == 1
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


@pytest.mark.parametrize("response", [
    {"data": {"status": "failed", "outputs": {"result": {"summary": "x", "review_points": []}}}},
    {"data": {"status": "succeeded", "outputs": {"result": "not json"}}},
    {"workflow_run_id": "run", "data": {"status": "succeeded", "outputs": {"result": {"summary": "x", "review_points": [], "approval_status": "approved"}}}},
    {"workflow_run_id": "run", "data": {"status": "succeeded", "outputs": {"result": {"summary": "", "review_points": []}}}},
    {"data": {"status": "succeeded", "outputs": {"result": {"summary": "x", "review_points": []}}}},
])
def test_bad_workflow_result_never_writes(unit, response):
    unit.workflow.transport = httpx.MockTransport(lambda request: httpx.Response(200,json=response))
    reply=post(unit)
    assert reply.status_code == 502
    assert [count(unit,x) for x in (t.student_admin_service,t.business_notification,t.operation_log)] == [0,0,0]


def test_missing_workflow_configuration_cannot_silently_skip_ai(unit):
    unit.workflow.config = StudentLeaveDifySettings(_env_file=None, STUDENT_DIFY_LEAVE_BASE="http://dify-test.local/v1", STUDENT_DIFY_LEAVE_VERSION="student-leave-v1",STUDENT_DIFY_LEAVE_KEY="")
    reply=post(unit)
    assert reply.status_code == 503 and count(unit,t.student_admin_service) == 0


@pytest.mark.parametrize("failure", ["timeout","network","http"])
def test_upstream_failure_is_redacted_and_no_writes(unit,failure):
    def fail(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("private upstream details",request=request)
        if failure == "network":
            raise httpx.ConnectError("private upstream details",request=request)
        return httpx.Response(401,json={"error":"test-only-workflow-key private upstream details"})
    unit.workflow.transport=httpx.MockTransport(fail)
    reply=post(unit)
    assert reply.status_code == (502 if failure=="http" else 503)
    assert "private upstream" not in reply.text and "test-only-workflow-key" not in reply.text
    assert count(unit,t.student_admin_service) == count(unit,t.operation_log) == 0


def test_untrusted_request_and_identity_do_not_reach_dify(unit):
    assert post(unit,body() | {"student_id":8}).status_code == 422
    unit.actor.identity_type="employee"
    assert post(unit).status_code == 403
    assert unit.workflow_requests == []


def test_dify_receives_only_contract_inputs_not_login_token(unit):
    assert post(unit).status_code == 200
    request=unit.workflow_requests[0]
    assert request == {"inputs":body(),"response_mode":"blocking","user":"student-7"}
    assert "student_id" not in request["inputs"] and "authorization" not in request["inputs"]


def test_disable_student_during_ai_call_prevents_write(unit):
    original=unit.workflow.analyze_leave
    def analyze(student_id,payload):
        result=original(student_id,payload)
        with unit.sessions.begin() as db:
            db.execute(update(t.student_profile).where(t.student_profile.c.student_id==7).values(is_archived=True))
        return result
    unit.workflow.analyze_leave=analyze
    assert post(unit).status_code == 403
    assert count(unit,t.student_admin_service) == count(unit,t.operation_log) == 0


def test_replay_succeeds_even_if_dify_later_unavailable(unit):
    first=post(unit)
    unit.workflow.config=StudentLeaveDifySettings(_env_file=None, STUDENT_DIFY_LEAVE_BASE="http://dify-test.local/v1", STUDENT_DIFY_LEAVE_VERSION="student-leave-v1",STUDENT_DIFY_LEAVE_KEY="")
    assert post(unit).json() == first.json() and len(unit.workflow_requests) == 1


def test_legacy_receipt_remains_replayable_without_inventing_analysis(unit):
    first=post(unit).json()
    legacy=first["data"].copy()
    del legacy["ai_analysis"]
    with unit.sessions.begin() as db:
        db.execute(update(t.operation_log).values(result_reference=legacy))
    replay=post(unit)
    assert replay.status_code==200 and replay.json()["data"]["ai_analysis"] is None
    assert len(unit.workflow_requests)==1


def test_workflow_dsl_has_reachable_llm_and_matching_input_output_contract():
    from pathlib import Path
    import yaml
    root=Path(__file__).resolve().parents[2]
    dsl=yaml.safe_load((root/"dify/student_leave/student_leave_submit.yml").read_text(encoding="utf-8"))
    assert dsl["kind"]=="app" and dsl["app"]["mode"]=="workflow"
    graph=dsl["workflow"]["graph"]
    nodes={n["id"]:n["data"] for n in graph["nodes"]}
    kinds={n["type"]:identifier for identifier,n in nodes.items()}
    assert set(kinds)=={"start","llm","end"}
    assert {(e["source"],e["target"]) for e in graph["edges"]} == {
        (kinds["start"],kinds["llm"]),(kinds["llm"],kinds["end"])}
    assert {v["variable"] for v in nodes[kinds["start"]]["variables"]}==set(body())
    assert nodes[kinds["end"]]["outputs"]==[{"variable":"result","value_selector":[kinds["llm"],"text"]}]
    prompts="\n".join(p["text"] for p in nodes[kinds["llm"]]["prompt_template"])
    for field in body():
        assert "{{#"+kinds["start"]+"."+field+"#}}" in prompts



def test_student_mapping_change_during_workflow_prevents_old_owner_write(unit):
    original=unit.workflow.analyze_leave
    def analyze(student_id,payload):
        result=original(student_id,payload)
        unit.actor.student_id=8
        return result
    unit.workflow.analyze_leave=analyze
    assert post(unit).status_code==403
    assert count(unit,t.student_admin_service)==count(unit,t.operation_log)==0
