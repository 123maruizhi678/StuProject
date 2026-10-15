from datetime import timedelta
import json
import pytest
from sqlalchemy import select, update, insert, func
from app.core.student_auth import Principal, sign_token, verify_token
from app.core.response import BusinessException
from app.config import settings
from app.services.student_service import (
    StudentService,
    events,
    reminders,
    warnings,
    profiles,
    progress,
)
from app.services.student_sync import StudentSyncService
from app.models import student_shared as shared
from app.models.student_types import utcnow
from app.schemas.student import (
    LeaveInput,
    TicketInput,
    TicketConfirm,
    RatingInput,
    TicketReply,
    MentalAssessment,
    WarningInput,
    ReminderInput,
    AcademicBatch,
    ProgressBatch,
    ChatDecision,
    ChatInput,
)
from app.tasks.student_tasks import StudentTasks
from app.services.student_chat import StudentChatService
from app.services.student_clients import (
    StudentQueryClient,
    StudentDifyClient,
    get_dify,
    get_query_client,
)
from app.main import app

STUDENT = Principal("student", 1)
SYNC = Principal("service", service_code="test.sync", scopes=("student:sync",))


def leave():
    return LeaveInput(
        leave_content="因病请假",
        leave_start_at="2026-11-01T09:00:00+08:00",
        leave_end_at="2026-11-02T09:00:00+08:00",
    )


def assessment(level="high"):
    return MentalAssessment(
        emotion_tag="压力",
        emotion_score=30,
        risk_level=level,
        trigger_reason="需要人工关怀",
    )


def event_batch(when=None, source_time=None, status="active"):
    return AcademicBatch(
        student_id=1,
        source_system="education",
        records=[
            dict(
                external_event_id="ddl-1",
                event_type="ddl",
                title="论文截止",
                due_at=(when or utcnow() + timedelta(days=2)).isoformat() + "Z",
                source_timezone="Asia/Shanghai",
                event_status=status,
                source_updated_at=(source_time or utcnow()).isoformat() + "Z",
            )
        ],
    )


def count(db, table):
    return db.scalar(select(func.count()).select_from(table))


def test_leave_idempotent_and_conflict(db):
    service = StudentService(db)
    first = service.submit_leave(STUDENT, "leave-001", leave())
    assert service.submit_leave(STUDENT, "leave-001", leave()) == first
    assert count(db, shared.student_leave_request) == 1
    assert count(db, shared.operation_log) == 1
    assert count(db, shared.business_notification) == 1
    changed = leave().model_copy(update={"leave_content": "不同内容"})
    with pytest.raises(BusinessException) as error:
        service.submit_leave(STUDENT, "leave-001", changed)
    assert error.value.code == 409
    assert db.scalar(select(shared.student_leave_request.c.start_at)).hour == 1


def test_leave_owner_version_and_state(db):
    service = StudentService(db)
    result = service.submit_leave(STUDENT, "leave-001", leave())
    entity_id = result["apply_id"]
    with pytest.raises(BusinessException) as error:
        service.withdraw_leave(Principal("student", 2), "withdraw-other", entity_id, 1)
    assert error.value.code == 404
    with pytest.raises(BusinessException) as error:
        service.withdraw_leave(STUDENT, "withdraw-stale", entity_id, 5)
    assert error.value.code == 409
    assert (
        service.withdraw_leave(STUDENT, "withdraw-001", entity_id, 1)["row_version"]
        == 2
    )
    with pytest.raises(BusinessException):
        service.withdraw_leave(STUDENT, "withdraw-002", entity_id, 2)


def test_missing_teacher_preserves_leave(db):
    db.execute(update(shared.student_staff_binding).values(status="disabled"))
    db.commit()
    result = StudentService(db).submit_leave(STUDENT, "leave-001", leave())
    assert result["assignment_pending"] is True
    assert count(db, shared.student_leave_request) == 1


def test_ticket_without_ai_and_confirmation(db):
    service = StudentService(db)
    ticket = service.submit_ticket(
        STUDENT, "ticket-001", TicketInput(complaint_content="进度太慢")
    )
    entity_id = ticket["ticket_id"]
    assert ticket["summary_available"] is False
    row = db.execute(select(shared.service_ticket)).mappings().one()
    assert row["content"] == "进度太慢" and row["ai_summary"] is None
    # 企业端按约定处理同一张表；此处只模拟对接，不实现企业模块。
    db.execute(
        update(shared.service_ticket)
        .where(shared.service_ticket.c.ticket_id == entity_id)
        .values(
            status="awaiting_student",
            solution="已补充材料",
            resolved_at=utcnow(),
            row_version=2,
        )
    )
    db.commit()
    result = service.confirm_ticket(
        STUDENT,
        "confirm-001",
        entity_id,
        TicketConfirm(expected_version=2, resolved=True),
    )
    assert result["process_status"] == "closed"
    service.rate_ticket(
        STUDENT,
        "rate-001",
        entity_id,
        RatingInput(expected_version=3, satisfaction_score=5),
    )
    assert db.scalar(select(shared.service_ticket.c.satisfaction_score)) == 5
    assert count(db, shared.service_ticket_record) == 3


def test_ticket_reopen_and_reply(db):
    service = StudentService(db)
    entity_id = service.submit_ticket(
        STUDENT, "ticket-001", TicketInput(complaint_content="建议")
    )["ticket_id"]
    service.ticket_reply(
        STUDENT,
        "reply-001",
        entity_id,
        TicketReply(expected_version=1, content="补充信息"),
    )
    db.execute(
        update(shared.service_ticket).values(
            status="awaiting_student",
            solution="方案",
            resolved_at=utcnow(),
            row_version=3,
        )
    )
    db.commit()
    result = service.confirm_ticket(
        STUDENT,
        "confirm-001",
        entity_id,
        TicketConfirm(expected_version=3, resolved=False, content="尚未解决"),
    )
    assert result["process_status"] == "reopened"
    row = db.execute(select(shared.service_ticket)).mappings().one()
    assert (
        row["reopen_count"] == 1
        and row["solution"] is None
        and row["resolved_at"] is None
    )


def test_psychology_history_and_acl(db):
    service = StudentService(db)
    result = service.record_mental(STUDENT, "mental-001", "测试原文", assessment())
    assert "trigger_reason" not in result and "warning_id" not in result
    service.record_mental(STUDENT, "mental-001", "测试原文", assessment())
    service.record_mental(STUDENT, "mental-002", "另一消息", assessment("low"))
    assert count(db, profiles) == 2 and count(db, warnings) == 1
    warning_id = db.scalar(select(warnings.c.id))
    with pytest.raises(BusinessException) as error:
        service.handle_warning(
            Principal("employee", 2),
            "warn-001",
            warning_id,
            "ack",
            WarningInput(expected_version=1, note="接手"),
        )
    assert error.value.code == 403
    service.handle_warning(
        Principal("employee", 1),
        "warn-001",
        warning_id,
        "ack",
        WarningInput(expected_version=1, note="接手"),
    )
    service.handle_warning(
        Principal("employee", 1),
        "warn-002",
        warning_id,
        "follow",
        WarningInput(expected_version=2, note="已联系"),
    )
    service.handle_warning(
        Principal("employee", 1),
        "warn-003",
        warning_id,
        "close",
        WarningInput(expected_version=3, note="已完成跟进"),
    )
    row = db.execute(select(warnings)).mappings().one()
    assert row["follower_status"] == "closed" and row["handling_result"] == "已完成跟进"


def test_unassigned_warning_is_retried(db, sessions):
    db.execute(update(shared.student_staff_binding).values(status="disabled"))
    db.commit()
    StudentService(db).record_mental(STUDENT, "mental-001", "测试", assessment())
    assert db.scalar(select(warnings.c.follower_id)) is None
    db.rollback()
    db.execute(update(shared.student_staff_binding).values(status="active"))
    db.commit()
    StudentTasks(sessions).prepare()
    assert db.scalar(select(warnings.c.follower_id)) == 1


def test_sync_old_data_and_replan(db):
    service = StudentSyncService(db)
    first = event_batch()
    service.academic(SYNC, "sync-001", first)
    event_id = db.scalar(select(events.c.id))
    db.rollback()
    StudentService(db).set_reminder(
        STUDENT,
        "remind-001",
        ReminderInput(academic_event_id=event_id, lead_minutes=60),
    )
    second = event_batch(
        when=first.records[0].due_at.replace(tzinfo=None) + timedelta(days=1),
        source_time=first.records[0].source_updated_at.replace(tzinfo=None)
        + timedelta(seconds=1),
    )
    service.academic(SYNC, "sync-002", second)
    row = db.execute(select(reminders)).mappings().one()
    assert row["event_version"] == 2 and row["status"] == "pending"
    assert service.academic(SYNC, "sync-003", first)["ignored_stale"] == 1
    assert db.scalar(select(events.c.event_version)) == 2


def test_sync_atomic_and_scope(db):
    service = StudentSyncService(db)
    body = event_batch()
    with pytest.raises(BusinessException):
        service.academic(STUDENT, "sync-001", body)
    duplicate = body.model_copy(update={"records": body.records * 2})
    with pytest.raises(BusinessException):
        service.academic(SYNC, "sync-002", duplicate)
    assert count(db, events) == 0 and count(db, shared.operation_log) == 0


def test_progress_multi_application(db):
    data = ProgressBatch(
        student_id=1,
        source_system="crm",
        records=[
            dict(
                external_application_id=key,
                application_name="院校" + key,
                stage_code="school_application",
                stage_status="submitted",
                source_updated_at="2026-10-15T00:00:00Z",
            )
            for key in ("a", "b")
        ],
    )
    service = StudentSyncService(db)
    service.application(SYNC, "progress-001", data)
    assert count(db, progress) == 2
    service.application(SYNC, "progress-002", data)
    assert count(db, progress) == 2


def test_reminder_dispatch_and_cancel_reopen(db, sessions):
    StudentSyncService(db).academic(SYNC, "sync-001", event_batch())
    event_id = db.scalar(select(events.c.id))
    db.rollback()
    service = StudentService(db)
    reminder_id = service.set_reminder(
        STUDENT,
        "remind-001",
        ReminderInput(academic_event_id=event_id, lead_minutes=60),
    )["reminder_id"]
    service.cancel_reminder(STUDENT, "cancel-001", reminder_id)
    service.set_reminder(
        STUDENT,
        "remind-002",
        ReminderInput(academic_event_id=event_id, lead_minutes=60),
    )
    db.execute(update(reminders).values(notify_at=utcnow() - timedelta(seconds=1)))
    db.commit()
    task = StudentTasks(sessions)
    assert task.prepare() == 1
    assert task.prepare() == 0
    assert task.dispatch()["sent"] == 1
    assert task.dispatch()["sent"] == 0
    assert db.scalar(select(reminders.c.status)) == "sent"


def test_cancel_queued_notification(db, sessions):
    StudentSyncService(db).academic(SYNC, "sync-001", event_batch())
    entity_id = db.scalar(select(events.c.id))
    db.rollback()
    service = StudentService(db)
    reminder_id = service.set_reminder(
        STUDENT,
        "remind-001",
        ReminderInput(academic_event_id=entity_id, lead_minutes=60),
    )["reminder_id"]
    db.execute(update(reminders).values(notify_at=utcnow() - timedelta(seconds=1)))
    db.commit()
    task = StudentTasks(sessions)
    task.prepare()
    service.cancel_reminder(STUDENT, "cancel-001", reminder_id)
    assert task.dispatch()["sent"] == 0


def test_notification_retry_lease_and_student_read(db, sessions):
    StudentService(db).submit_leave(STUDENT, "leave-001", leave())

    def fail(_):
        raise RuntimeError("secret must not be persisted")

    tasks = StudentTasks(sessions, sender=fail)
    assert tasks.dispatch()["failed"] == 1
    n = shared.business_notification
    row = db.execute(select(n)).mappings().one()
    assert row["last_error_code"] == "DELIVERY_FAILED" and row["attempt_count"] == 1
    db.execute(
        update(n).values(
            delivery_status="sending", lease_until=utcnow() - timedelta(seconds=1)
        )
    )
    db.commit()
    assert StudentTasks(sessions).dispatch()["sent"] == 1
    # 发给老师的消息，学生不可标记已读。
    with pytest.raises(BusinessException) as error:
        StudentService(db).read_notification(
            STUDENT, "read-001", row["notification_id"]
        )
    assert error.value.code == 404


def test_worker_does_not_take_enterprise_messages(db, sessions):
    db.execute(
        insert(shared.business_notification).values(
            entity_type="leave",
            entity_id=1,
            event_code="enterprise.result",
            student_id=1,
            channel="in_app",
            title="企业结果",
            content="通知",
            dedupe_key="enterprise-only",
            delivery_status="pending",
        )
    )
    db.commit()
    assert StudentTasks(sessions).dispatch() == {"sent": 0, "failed": 0, "skipped": 0}


def test_action_requires_confirmation_and_replay(db):
    class AI:
        def chat(self, *_):
            return (
                ChatDecision(
                    intent="leave",
                    answer="请确认",
                    mental=assessment("low"),
                    action="leave.submit",
                    parameters=leave().model_dump(mode="json"),
                ),
                "conversation",
                [],
            )

    chat = StudentChatService(StudentService(db), AI(), None)
    result = chat.chat(STUDENT, "chat-001", ChatInput(message="我要请假"))
    assert count(db, shared.student_leave_request) == 0
    token = result["pending_action"]["action_token"]
    with pytest.raises(BusinessException):
        chat.confirm(Principal("student", 2), token)
    first = chat.confirm(STUDENT, token)
    assert chat.confirm(STUDENT, token) == first
    assert count(db, shared.student_leave_request) == 1


def test_signed_auth_tamper_expiry_and_algorithm():
    token = sign_token({"actor_type": "student", "actor_id": 1})
    assert verify_token(token)["actor_id"] == 1
    with pytest.raises(BusinessException):
        verify_token(token[:-3] + "aaa")
    with pytest.raises(BusinessException):
        verify_token(sign_token({"actor_type": "student", "actor_id": 1}, lifetime=-1))
    with pytest.raises(BusinessException):
        verify_token(token, "student-action")


def test_api_auth_validation_and_core_flow(client, student_headers):
    assert client.get("/api/v1/student/academic").json()["code"] == 401
    invalid = client.post(
        "/api/v1/student/leave",
        headers=student_headers(),
        json={**leave().model_dump(mode="json"), "student_id": 2},
    ).json()
    assert invalid["code"] == 400
    assert "因病" not in json.dumps(invalid, ensure_ascii=False)
    result = client.post(
        "/api/v1/student/leave",
        headers=student_headers(),
        json=leave().model_dump(mode="json"),
    ).json()
    assert result["code"] == 0
    entity_id = result["data"]["apply_id"]
    assert (
        client.request(
            "DELETE",
            f"/api/v1/student/leave/{entity_id}",
            headers=student_headers(key="withdraw-001"),
            json={"expected_version": 1},
        ).json()["code"]
        == 0
    )


def test_api_ai_failure_preserves_complaint(client, student_headers, db):
    class Unavailable:
        def ticket(self, *_):
            raise BusinessException("not configured", 503)

    app.dependency_overrides[get_dify] = Unavailable
    result = client.post(
        "/api/v1/student/complaint",
        headers=student_headers(),
        json={"complaint_content": "反馈正文"},
    ).json()
    assert result["code"] == 0 and result["data"]["summary_available"] is False
    assert count(db, shared.service_ticket) == 1


def test_query_adapter_enforces_contract(monkeypatch):
    import app.services.student_clients as clients

    def upstream(*args, **kwargs):
        assert kwargs["payload"]["subject"] == {"type": "student", "id": 1}
        return {
            "code": 0,
            "data": {
                "contract_version": "student-v1",
                "scenario": "academic",
                "subject_id": 1,
                "total": 1,
                "rows": [{"student_id": 2, "id": 1, "title": "其他学生"}],
            },
        }

    monkeypatch.setattr(clients, "request_json", upstream)
    with pytest.raises(BusinessException) as error:
        StudentQueryClient().query(STUDENT, "academic")
    assert error.value.code == 503


def test_query_adapter_removes_private_fields(monkeypatch):
    import app.services.student_clients as clients

    monkeypatch.setattr(
        clients,
        "request_json",
        lambda *a, **k: {
            "code": 0,
            "data": {
                "contract_version": "student-v1",
                "scenario": "leave",
                "subject_id": 1,
                "total": 1,
                "rows": [
                    {
                        "student_id": 1,
                        "leave_request_id": 1,
                        "status": "approved",
                        "row_version": 2,
                        "sql": "secret",
                        "operation_key": "secret",
                    }
                ],
            },
        },
    )
    result = StudentQueryClient().query(STUDENT, "leave", entity_id=1)
    assert (
        result["items"][0]["status"] == "approved" and "sql" not in result["items"][0]
    )


def test_dify_malformed_risk_rejected(monkeypatch):
    import app.services.student_clients as clients

    monkeypatch.setattr(
        clients,
        "request_json",
        lambda *a, **k: {
            "data": {
                "status": "succeeded",
                "outputs": {
                    "result": {
                        "emotion_tag": "压力",
                        "emotion_score": 200,
                        "risk_level": "high",
                    }
                },
            }
        },
    )
    with pytest.raises(BusinessException) as error:
        StudentDifyClient().mental("消息", STUDENT)
    assert error.value.code == 503


def test_my_sql_fk_and_check_constraints(db, test_engine):
    if test_engine.dialect.name != "mysql":
        pytest.skip("正式MySQL约束专项验证")
    from sqlalchemy.exc import IntegrityError, OperationalError

    with pytest.raises(IntegrityError):
        db.execute(
            insert(profiles).values(
                student_id=999,
                emotion_tag="test",
                emotion_score=50,
                risk_level="low",
                observed_at=utcnow(),
                source_event_id="x",
                analysis_version="test",
            )
        )
        db.commit()
    db.rollback()
    with pytest.raises(OperationalError) as error:
        db.execute(
            insert(profiles).values(
                student_id=1,
                emotion_tag="test",
                emotion_score=101,
                risk_level="low",
                observed_at=utcnow(),
                source_event_id="x",
                analysis_version="test",
            )
        )
        db.commit()
    db.rollback()


def test_employee_cannot_use_student_identity(db):
    with pytest.raises(BusinessException) as error:
        StudentService(db).submit_leave(
            Principal("employee", 1), "leave-employee", leave()
        )
    assert error.value.code == 403 and count(db, shared.student_leave_request) == 0


def test_disabled_identity_cannot_replay(db):
    service = StudentService(db)
    service.submit_leave(STUDENT, "leave-001", leave())
    db.execute(
        update(shared.student_profile)
        .where(shared.student_profile.c.student_id == 1)
        .values(is_archived=True)
    )
    db.commit()
    with pytest.raises(BusinessException) as error:
        service.submit_leave(STUDENT, "leave-001", leave())
    assert error.value.code == 403


def test_chat_retry_has_stable_confirmation(db):
    class AI:
        def chat(self, *_):
            return (
                ChatDecision(
                    intent="leave",
                    answer="请确认",
                    mental=assessment("low"),
                    action="leave.submit",
                    parameters=leave().model_dump(mode="json"),
                ),
                "conversation",
                [],
            )

    chat = StudentChatService(StudentService(db), AI(), None)
    one = chat.chat(STUDENT, "chat-retry", ChatInput(message="我要请假"))
    two = chat.chat(STUDENT, "chat-retry", ChatInput(message="我要请假"))
    chat.confirm(STUDENT, one["pending_action"]["action_token"])
    chat.confirm(STUDENT, two["pending_action"]["action_token"])
    assert count(db, shared.student_leave_request) == 1


def test_concurrent_leave_mysql(sessions, db, test_engine):
    if test_engine.dialect.name != "mysql":
        pytest.skip("并发数据库专项验证")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    barrier = Barrier(2)

    def submit(_):
        with sessions() as session:
            barrier.wait(timeout=5)
            return StudentService(session).submit_leave(
                STUDENT, "concurrent-001", leave()
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, [1, 2]))
    assert results[0] == results[1]
    assert count(db, shared.student_leave_request) == 1
    assert count(db, shared.operation_log) == 1


def test_query_rejects_internal_ticket_notes(monkeypatch):
    import app.services.student_clients as clients

    monkeypatch.setattr(
        clients,
        "request_json",
        lambda *a, **k: {
            "code": 0,
            "data": {
                "contract_version": "student-v1",
                "scenario": "ticket_records",
                "subject_id": 1,
                "total": 1,
                "rows": [
                    {
                        "student_id": 1,
                        "ticket_id": 1,
                        "visibility": "internal",
                        "content": "内部备注",
                    }
                ],
            },
        },
    )
    with pytest.raises(BusinessException) as error:
        StudentQueryClient().query(STUDENT, "ticket_records", entity_id=1)
    assert error.value.code == 503


def test_reminder_cancel_reopen_has_distinct_generation(db, sessions):
    StudentSyncService(db).academic(SYNC, "sync-reopen", event_batch())
    entity_id = db.scalar(select(events.c.id))
    db.rollback()
    service = StudentService(db)
    body = ReminderInput(academic_event_id=entity_id, lead_minutes=60)
    reminder_id = service.set_reminder(STUDENT, "reminder-first", body)["reminder_id"]
    db.execute(
        update(reminders)
        .where(reminders.c.id == reminder_id)
        .values(notify_at=utcnow() - timedelta(seconds=1))
    )
    db.commit()
    task = StudentTasks(sessions)
    task.prepare()
    first_key = db.scalar(select(shared.business_notification.c.dedupe_key))
    db.rollback()
    service.cancel_reminder(STUDENT, "cancel-first", reminder_id)
    service.set_reminder(STUDENT, "reminder-reopen", body)
    db.execute(
        update(reminders)
        .where(reminders.c.id == reminder_id)
        .values(notify_at=utcnow() - timedelta(seconds=1))
    )
    db.commit()
    task.prepare()
    rows = db.execute(select(shared.business_notification)).mappings().all()
    assert len(rows) == 2 and len({r["dedupe_key"] for r in rows}) == 2
    assert any(
        r["dedupe_key"] == first_key and r["delivery_status"] == "dead_letter"
        for r in rows
    )
    db.rollback()
    assert task.dispatch()["sent"] == 1
    assert db.scalar(select(reminders.c.status)) == "sent"
