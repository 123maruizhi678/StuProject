"""学生投诉输入、受控模型输出及对外回执。"""
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, model_validator
from app.schemas.student.student_common import Input, VersionInput


Category = Literal["application", "visa", "teaching", "service", "other"]
UtcDateTime = Annotated[datetime, PlainSerializer(
    lambda value: value.replace(tzinfo=timezone.utc).isoformat(), return_type=str, when_used="json")]

class TicketInput(Input):
    content: str = Field(min_length=1, max_length=5000)
    ticket_type: Literal["complaint", "suggestion"] = "complaint"
    category_code: Category = "other"


class TicketReply(VersionInput):
    content: str = Field(min_length=1, max_length=5000)


class TicketConfirm(VersionInput):
    resolved: bool
    comment: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def reason(self):
        if not self.resolved and not self.comment:
            raise ValueError("反馈未解决时请填写原因")
        return self


class RatingInput(VersionInput):
    satisfaction_score: int = Field(ge=1, le=5)


class ComplaintInput(TicketInput):
    """历史最小单元输入名称，字段与统一工单契约一致。"""


class DifyTicketContent(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    summary: str = Field(min_length=1, max_length=300)
    # 分类只提供建议，不覆盖学生选择和企业分派。
    suggested_category: Category


class TicketAnalysis(DifyTicketContent):
    workflow_run_id: str = Field(min_length=1, max_length=128)
    analysis_version: str = Field(min_length=1, max_length=64)


class TicketReceipt(BaseModel):
    ticket_id: int
    ticket_no: str
    status: str
    category_code: Category
    handling_department_id: int
    row_version: int
    ai_status: Literal["available", "unavailable"]
    ai_analysis: TicketAnalysis | None
    response_due_at: UtcDateTime
    resolution_due_at: UtcDateTime


class TicketView(BaseModel):
    ticket_id: int
    ticket_no: str
    ticket_type: str
    category_code: str
    content: str
    ai_summary: str | None
    priority: str
    status: str
    solution: str | None
    row_version: int
    created_at: UtcDateTime
    updated_at: UtcDateTime


class TicketRecordView(BaseModel):
    ticket_record_id: int
    record_type: str
    content: str | None
    to_status: str | None
    cycle_no: int
    created_at: UtcDateTime


class TicketResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: TicketReceipt


class TicketDetailResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: TicketView


class TicketPage(BaseModel):
    items: list[TicketView]
    next_before_id: int | None


class TicketListResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: TicketPage


class TicketRecordPage(BaseModel):
    items: list[TicketRecordView]
    next_after_id: int | None


class TicketRecordsResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: TicketRecordPage
