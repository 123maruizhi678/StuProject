"""S05—S08业务与共享约束验证，模型通过HTTP协议替身模拟。"""
from datetime import datetime, timezone
import json

import httpx
import pytest
from sqlalchemy import event, insert, select, update, text

from app.api.student_ticket import create_router
from app.clients.student_ticket_dify import StudentTicketDifyClient
from app.config import StudentTicketSettings
from app.models import student_leave as shared
from app.models import student_ticket as t
from app.repositories.student_schema import check_student_schema


@pytest.fixture
def ticket(unit):
    requests, active = [], []
    config = StudentTicketSettings(_env_file=None, STUDENT_DIFY_TICKET_KEY="test-only-ticket-key",
                                  STUDENT_DIFY_TICKET_BASE="http://ticket-test.local/v1")
    def upstream(request):
        assert all(not db.in_transaction() for db in active)
        assert request.headers["Authorization"] == "Bearer test-only-ticket-key"
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"workflow_run_id":"ticket-mock-001", "data":{
            "status":"succeeded", "outputs":{"result":json.dumps({
                "summary":"学生反馈课程安排变更，希望获得明确说明。", "suggested_category":"teaching"}, ensure_ascii=False)}}})
    workflow = StudentTicketDifyClient(config, httpx.MockTransport(upstream))
    def db_dependency():
        with unit.sessions() as db:
            active.append(db)
            try:
                yield db
            finally:
                active.remove(db)
    unit.app.include_router(create_router(unit.account_dependency, unit.account_dependency,
                                         db_dependency, lambda: workflow), prefix="/api/v1")
    unit.ticket_workflow, unit.ticket_requests = workflow, requests
    return unit


def payload():
    return {"content":"课程安排多次变更，希望老师明确后续安排。", "ticket_type":"complaint", "category_code":"service"}


def submit(ticket, body=None, key="ticket-001"):
    return ticket.client.post("/api/v1/student/complaint", json=body or payload(), headers={"Idempotency-Key":key})


def rows(ticket, table):
    with ticket.sessions() as db:
        return db.execute(select(table)).mappings().all()


def test_summary_does_not_overwrite_original_category_or_assign_staff(ticket):
    response=submit(ticket)
    assert response.status_code==200
    data=response.json()["data"]
    assert data["status"]=="open" and data["ai_status"]=="available"
    assert data["handling_department_id"]==5 and data["category_code"]=="service"
    assert data["ai_analysis"]["suggested_category"]=="teaching"
    row=rows(ticket,t.service_ticket)[0]
    assert row["student_id"]==7 and row["content"]==payload()["content"]
    assert row["employee_id"] is None and row["priority"]=="normal"
    assert row["ai_summary"]==data["ai_analysis"]["summary"]
    assert data["resolution_due_at"]>=data["response_due_at"]
    audit=rows(ticket,shared.operation_log)[0]
    assert audit["result_reference"]==data and audit["operation_status"]=="succeeded"
    assert rows(ticket,t.service_ticket_record)[0]["visibility"]=="student_visible"
    assert ticket.ticket_requests==[{"inputs":payload(),"response_mode":"blocking","user":"student-7"}]


def test_idempotent_replay_and_different_payload_conflict(ticket):
    first=submit(ticket)
    assert submit(ticket).json()==first.json()
    assert len(ticket.ticket_requests)==1 and len(rows(ticket,t.service_ticket))==1
    assert submit(ticket,payload()|{"content":"不同问题"}).status_code==409


@pytest.mark.parametrize("kind",["missing_key","timeout","http","bad_json","injected_fields","unknown_category","failed"])
def test_ai_failure_preserves_ticket_and_reports_unavailable(ticket,kind):
    def failure(request):
        if kind=="timeout":
            raise httpx.ReadTimeout("private upstream detail test-only-ticket-key",request=request)
        if kind=="http":
            return httpx.Response(401,text="private upstream detail test-only-ticket-key")
        result={"summary":"摘要", "suggested_category":"other"}
        if kind=="injected_fields": result["employee_id"]=999
        if kind=="unknown_category": result["suggested_category"]="invented"
        return httpx.Response(200,json={"workflow_run_id":"run", "data":{"status":"failed" if kind=="failed" else "succeeded",
            "outputs":{"result":"not json" if kind=="bad_json" else result}}})
    ticket.ticket_workflow.transport=httpx.MockTransport(failure)
    if kind=="missing_key":
        ticket.ticket_workflow.config=StudentTicketSettings(_env_file=None,STUDENT_DIFY_TICKET_KEY="")
    response=submit(ticket)
    assert response.status_code==200
    assert response.json()["data"]["ai_status"]=="unavailable"
    assert response.json()["data"]["ai_analysis"] is None
    assert "private upstream" not in response.text and "test-only-ticket-key" not in response.text
    assert rows(ticket,t.service_ticket)[0]["ai_summary"] is None
    assert rows(ticket,t.service_ticket)[0]["content"]==payload()["content"]


@pytest.mark.parametrize("extra",[{"student_id":8},{"employee_id":11},{"handling_department_id":99},
                                   {"status":"closed"},{"content":"  "},{"ticket_type":"unknown"}])
def test_untrusted_fields_are_rejected_before_ai(ticket,extra):
    assert submit(ticket,payload()|extra).status_code==422
    assert ticket.ticket_requests==[] and rows(ticket,t.service_ticket)==[]


def test_no_other_student_data_and_internal_records(ticket):
    data=submit(ticket).json()["data"]
    ticket_id=data["ticket_id"]
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    with ticket.sessions.begin() as db:
        db.execute(insert(t.service_ticket_record).values(ticket_id=ticket_id, record_type="note",
            service_code="test-only",content="不应给学生看的内部记录",visibility="internal",to_status="open",
            cycle_no=1,record_key="internal-test",created_at=now))
    visible=ticket.client.get(f"/api/v1/student/tickets/{ticket_id}/records").json()["data"]["items"]
    assert len(visible)==1 and "内部记录" not in json.dumps(visible,ensure_ascii=False)
    assert ticket.client.get(f"/api/v1/student/tickets/{ticket_id}").status_code==200
    ticket.actor.student_id=8
    assert ticket.client.get("/api/v1/student/tickets").json()["data"]["items"]==[]
    assert ticket.client.get(f"/api/v1/student/tickets/{ticket_id}").status_code==404
    assert ticket.client.get(f"/api/v1/student/tickets/{ticket_id}/records").status_code==404
    assert submit(ticket).status_code==200  # 幂等键按学生隔离。
    assert len(rows(ticket,t.service_ticket))==2


def test_fixed_queries_do_not_call_model_and_have_pagination(ticket):
    for n in range(3): assert submit(ticket,key=f"page-{n}").status_code==200
    first=ticket.client.get("/api/v1/student/tickets?limit=2").json()["data"]
    assert len(first["items"])==2 and first["next_before_id"] is not None
    second=ticket.client.get(f"/api/v1/student/tickets?limit=2&before_id={first['next_before_id']}").json()["data"]
    assert len(second["items"])==1 and second["next_before_id"] is None
    assert len(ticket.ticket_requests)==3
    assert ticket.client.get("/api/v1/student/tickets?limit=1000").status_code==422


def test_department_disabled_blocks_before_model_and_writes(ticket):
    with ticket.sessions.begin() as db:
        db.execute(update(shared.org_department).values(status="disabled"))
    assert submit(ticket).status_code==409
    assert rows(ticket,t.service_ticket)==rows(ticket,shared.operation_log)==[]
    assert ticket.ticket_requests==[]


def test_missing_table_blocks_before_model(ticket):
    with ticket.engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE service_ticket_record")
    response=submit(ticket)
    assert response.status_code==503 and ticket.ticket_requests==[]
    assert rows(ticket,t.service_ticket)==[]


def test_missing_foreign_key_is_detected_and_blocks_submit(ticket):
    with ticket.engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE service_ticket_record")
        connection.exec_driver_sql("CREATE TABLE service_ticket_record(ticket_record_id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL)")
        report=check_student_schema(connection,"ticket")
    assert not report["compatible"]
    assert any("missing_foreign_key:service_ticket_record.ticket_id" in i for i in report["issues"])
    assert submit(ticket).status_code==503 and ticket.ticket_requests==[]


def test_unsupported_extra_required_column_is_detected(ticket):
    with ticket.engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE service_ticket ADD COLUMN legacy_required TEXT NOT NULL")
        report=check_student_schema(connection,"ticket")
    assert "unhandled_required_column:service_ticket.legacy_required" in report["issues"]
    assert submit(ticket).status_code==503


def test_record_write_failure_rolls_back_entire_ticket(ticket):
    def fail(conn,cursor,statement,parameters,context,executemany):
        if statement.startswith("INSERT INTO service_ticket_record"): raise RuntimeError("test failure")
    event.listen(ticket.engine,"before_cursor_execute",fail)
    try: assert submit(ticket).status_code==500
    finally: event.remove(ticket.engine,"before_cursor_execute",fail)
    assert rows(ticket,t.service_ticket)==rows(ticket,shared.operation_log)==[]
    assert submit(ticket).status_code==200


def test_archive_student_during_model_call_blocks_write(ticket):
    original=ticket.ticket_workflow.summarize
    def summarize(student_id,body):
        result=original(student_id,body)
        with ticket.sessions.begin() as db:
            db.execute(update(shared.student_profile).where(shared.student_profile.c.student_id==7).values(is_archived=True))
        return result
    ticket.ticket_workflow.summarize=summarize
    assert submit(ticket).status_code==403
    assert rows(ticket,t.service_ticket)==[]


def test_non_student_cannot_use_ticket_route(ticket):
    ticket.actor.identity_type="customer"
    assert submit(ticket).status_code==403 and ticket.ticket_requests==[]
    assert ticket.client.get("/api/v1/student/tickets").status_code==403


def test_workflow_dsl_contract():
    from pathlib import Path
    import yaml
    d=yaml.safe_load((Path(__file__).resolve().parents[2]/"dify/student_ticket/student_ticket_summary.yml").read_text(encoding="utf-8"))
    nodes={n["data"]["type"]:n for n in d["workflow"]["graph"]["nodes"]}
    assert set(nodes)=={"start","llm","end"}
    assert {v["variable"] for v in nodes["start"]["data"]["variables"]}==set(payload())
    edges={(e["source"],e["target"]) for e in d["workflow"]["graph"]["edges"]}
    assert (nodes["start"]["id"],nodes["llm"]["id"]) in edges
    assert (nodes["llm"]["id"],nodes["end"]["id"]) in edges
    assert nodes["end"]["data"]["outputs"][0]["value_selector"]==[nodes["llm"]["id"],"text"]
