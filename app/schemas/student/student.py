"""学生请求与外部输出契约。身份不接受请求体指定，所有输入拒绝多余字段。"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from pydantic import Field, AwareDatetime, model_validator
from app.schemas.student.student_common import Input, VersionInput
from app.schemas.student.student_leave import LeaveInput, LeaveDecision
from app.schemas.student.student_ticket import TicketInput, TicketReply, TicketConfirm, RatingInput


class ReminderInput(Input):
    academic_event_id: int = Field(gt=0)
    lead_minutes: int = Field(ge=0, le=525600)
    expected_event_version: int = Field(ge=1)
    expected_updated_at: AwareDatetime | None = None


class ReminderCancel(Input):
    expected_event_version: int = Field(ge=1)
    expected_updated_at: AwareDatetime


class AssignmentInput(VersionInput):
    employee_id: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=2000)


class MentalInput(Input):
    chat_content: str = Field(min_length=1, max_length=10000)


class MentalAssessment(Input):
    workflow_run_id: str | None = Field(default=None, max_length=128)
    emotion_tag: str = Field(min_length=1, max_length=50)
    emotion_score: Decimal = Field(ge=0, le=100)
    risk_level: Literal["low", "medium", "high", "critical"]
    trigger_reason: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def risk_reason(self):
        if self.risk_level in ("high", "critical") and not self.trigger_reason:
            raise ValueError("高危评估必须提供依据")
        return self


class WarningInput(VersionInput):
    note: str = Field(min_length=1, max_length=2000)


class AcademicRecord(Input):
    external_event_id: str = Field(min_length=1, max_length=128)
    event_type: Literal["ddl", "exam"]
    title: str = Field(min_length=1, max_length=200)
    due_at: AwareDatetime
    source_timezone: str = Field(min_length=1, max_length=64)
    event_status: Literal["active", "cancelled"] = "active"
    source_updated_at: AwareDatetime

    @model_validator(mode="after")
    def timezone_valid(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(self.source_timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("无效的IANA时区")
        return self


class ProgressRecord(Input):
    external_application_id: str = Field(min_length=1, max_length=128)
    application_name: str = Field(min_length=1, max_length=200)
    stage_code: Literal["document_review", "school_application", "visa_process"]
    stage_status: str = Field(min_length=1, max_length=64)
    detail: str | None = Field(default=None, max_length=500)
    source_updated_at: AwareDatetime


class AcademicBatch(Input):
    student_id: int = Field(gt=0)
    source_system: str = Field(
        min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_.:-]+$"
    )
    records: list[AcademicRecord] = Field(max_length=500)


class ProgressBatch(Input):
    student_id: int = Field(gt=0)
    source_system: str = Field(
        min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_.:-]+$"
    )
    records: list[ProgressRecord] = Field(max_length=500)


class SyncRequest(Input):
    student_id: int = Field(gt=0)


class TicketSummary(Input):
    workflow_run_id: str = Field(min_length=1,max_length=128)
    summary: str = Field(min_length=1, max_length=500)
    category: Literal["application", "visa", "teaching", "service", "other"] = "other"


class ChatInput(Input):
    message: str = Field(min_length=1, max_length=10000)
    conversation_token: str | None = Field(default=None, max_length=4000)


class ChatDecision(Input):
    intent: Literal[
        "leave", "mental", "feedback", "academic", "progress", "life", "upgrade"
    ]
    answer: str = Field(min_length=1, max_length=10000)
    mental: MentalAssessment
    action: Literal[
        "none",
        "leave.submit",
        "ticket.submit",
        "reminder.set",
        "academic.query",
        "courses.query",
        "scores.query",
        "progress.query",
        "leave.query",
        "ticket.query",
        "reminders.query",
        "notifications.query",
    ] = "none"
    parameters: dict = Field(default_factory=dict)
    summary: str | None = Field(default=None,max_length=300)


class ConfirmInput(Input):
    action_token: str = Field(min_length=1, max_length=64000)


def as_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None)
