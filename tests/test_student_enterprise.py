"""学生模块向企业侧提供的公共请假与权限集成验证。"""

import pytest
from pydantic import ValidationError
from sqlalchemy import select, update, func
from app.core.response import BusinessException
from app.core.student_auth import Principal, sign_token
from app.schemas.student import LeaveDecision, LeaveInput
from app.services.student_service import StudentService
from app.services.student_local_query import LocalStudentQueryClient
from app.services.student_clients import StudentSourceClient
from app.models import student_shared as shared
from app.tasks.student_tasks import StudentTasks
from app.config import settings

STUDENT = Principal("student", 1)
TEACHER = Principal("employee", 1)


def leave():
    return LeaveInput(
        leave_content="课程请假",
        leave_start_at="2026-11-01T09:00:00+08:00",
        leave_end_at="2026-11-02T09:00:00+08:00",
    )


@pytest.mark.parametrize("decision", ["approved", "rejected"])
def test_leave_enterprise_roundtrip(db, sessions, decision):
    service = StudentService(db)
    entity_id = service.submit_leave(STUDENT, "leave-enterprise", leave())["apply_id"]
    assert service.teacher_leaves(TEACHER, "submitted")["total"] == 1
    assert service.teacher_leaves(Principal("employee", 2))["total"] == 0
    body = LeaveDecision(expected_version=1, decision=decision, comment="审批意见")
    with pytest.raises(BusinessException) as error:
        service.decide_leave(
            Principal("employee", 2), "decision-wrong", entity_id, body
        )
    assert error.value.code == 403
    result = service.decide_leave(TEACHER, "decision-001", entity_id, body)
    assert result == service.decide_leave(TEACHER, "decision-001", entity_id, body)
    assert result["row_version"] == 2 and result["approval_status"] == decision
    with pytest.raises(BusinessException) as error:
        service.withdraw_leave(STUDENT, "withdraw-after-decision", entity_id, 2)
    assert error.value.code == 409
    tasks = StudentTasks(sessions)
    assert tasks.dispatch() == {"sent": 1, "failed": 0, "skipped": 1}
    student_data = LocalStudentQueryClient(db).query(
        STUDENT, "leave", entity_id=entity_id
    )["items"][0]
    assert (
        student_data["status"] == decision
        and student_data["decision_comment"] == "审批意见"
    )
    assert LocalStudentQueryClient(db).query(STUDENT, "notifications")["total"] == 1


def test_leave_reject_reason_and_stale_version(db):
    with pytest.raises(ValidationError):
        LeaveDecision(expected_version=1, decision="rejected")
    service = StudentService(db)
    entity_id = service.submit_leave(STUDENT, "leave", leave())["apply_id"]
    service.withdraw_leave(STUDENT, "withdraw", entity_id, 1)
    with pytest.raises(BusinessException) as error:
        service.decide_leave(
            TEACHER,
            "approve",
            entity_id,
            LeaveDecision(expected_version=1, decision="approved"),
        )
    assert error.value.code == 409


def test_leave_assignment_retry_and_disabled_teacher(db, sessions):
    db.execute(update(shared.student_staff_binding).values(status="disabled"))
    db.commit()
    service = StudentService(db)
    entity_id = service.submit_leave(STUDENT, "leave", leave())["apply_id"]
    db.execute(update(shared.student_staff_binding).values(status="active"))
    db.commit()
    StudentTasks(sessions).prepare()
    row = service.leave_for_teacher(TEACHER, entity_id)
    assert row["approver_employee_id"] == 1 and row["row_version"] == 2
    with pytest.raises(BusinessException) as error:
        service.decide_leave(
            TEACHER,
            "old-version",
            entity_id,
            LeaveDecision(expected_version=1, decision="approved"),
        )
    assert error.value.code == 409
    service.decide_leave(
        TEACHER,
        "current-version",
        entity_id,
        LeaveDecision(expected_version=2, decision="approved"),
    )
    db.execute(update(shared.student_staff_binding).values(status="disabled"))
    db.commit()
    with pytest.raises(BusinessException) as error:
        service.decide_leave(
            TEACHER,
            "current-version",
            entity_id,
            LeaveDecision(expected_version=2, decision="approved"),
        )
    assert error.value.code == 403


def test_enterprise_leave_http(client, student_headers, monkeypatch):
    monkeypatch.setattr(settings, "STUDENT_QUERY_BACKEND", "local")
    entity_id = client.post(
        "/api/v1/student/leave",
        headers=student_headers(),
        json=leave().model_dump(mode="json"),
    ).json()["data"]["apply_id"]
    headers = {
        "Authorization": "Bearer "
        + sign_token({"actor_type": "employee", "actor_id": 1}),
        "Idempotency-Key": "approve-001",
    }
    prefix = "/api/v1/internal/student/leave"
    assert (
        client.get(prefix + "?status=submitted", headers=headers).json()["data"][
            "total"
        ]
        == 1
    )
    assert (
        client.get(prefix + f"/{entity_id}", headers=headers).json()["data"][
            "row_version"
        ]
        == 1
    )
    response = client.post(
        prefix + f"/{entity_id}/decision",
        headers=headers,
        json={"expected_version": 1, "decision": "approved", "comment": "同意"},
    ).json()
    assert response["code"] == 0 and response["data"]["row_version"] == 2
    assert (
        client.get(
            f"/api/v1/student/leave/{entity_id}", headers=student_headers()
        ).json()["data"]["items"][0]["status"]
        == "approved"
    )
    assert client.get(prefix, headers=student_headers()).json()["code"] == 403


def test_local_query_owner_and_record_visibility(db):
    service = StudentService(db)
    entity_id = service.submit_leave(STUDENT, "leave", leave())["apply_id"]
    query = LocalStudentQueryClient(db)
    with pytest.raises(BusinessException) as error:
        query.query(Principal("student", 2), "leave", entity_id=entity_id)
    assert error.value.code == 404
    assert query.query(STUDENT, "leave")["query_backend"] == "local_fixed_sql"


def test_source_uses_distinct_external_identity(db, monkeypatch):
    seen = []

    def request(method, url, token, *, params):
        seen.append(params)
        return {**params, "source_system": "test", "records": []}

    monkeypatch.setattr("app.services.student_clients.request_json", request)
    student = StudentService(db).student(STUDENT)
    StudentSourceClient().fetch("academic", student)
    StudentSourceClient().fetch("progress", student)
    assert seen == [{"external_student_id": "external-1"}, {"crm_student_id": "crm-1"}]


def test_teacher_notification_acl(db, sessions):
    service = StudentService(db)
    service.submit_leave(STUDENT, "leave", leave())
    assert StudentTasks(sessions).dispatch()["sent"] == 1
    notices = service.teacher_notifications(TEACHER)
    assert notices["total"] == 1
    assert service.teacher_notifications(Principal("employee", 2))["total"] == 0
    notification_id = notices["items"][0]["notification_id"]
    with pytest.raises(BusinessException) as error:
        service.read_teacher_notification(
            Principal("employee", 2), "read-other", notification_id
        )
    assert error.value.code == 404
    assert (
        service.read_teacher_notification(TEACHER, "read-own", notification_id)["read"]
        is True
    )
