"""S01 请求与回执；身份和审批状态不由请求体指定。"""
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from app.schemas.student.student_common import Input, VersionInput


class LeaveInput(Input):
    leave_content: str = Field(min_length=1, max_length=5000)
    leave_type: str = Field(default="personal", min_length=1, max_length=32)
    leave_start_at: AwareDatetime
    leave_end_at: AwareDatetime
    generate_ai_summary: bool = False

    @model_validator(mode="after")
    def period(self):
        if self.leave_end_at <= self.leave_start_at:
            raise ValueError("请假结束时间必须晚于开始时间")
        return self


class LeaveDecision(VersionInput):
    decision: Literal["approved", "rejected"]
    comment: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def reject_reason(self):
        if self.decision == "rejected" and not self.comment:
            raise ValueError("驳回时必须填写审批意见")
        return self


class DifyLeaveContent(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    summary: str = Field(min_length=1, max_length=200)
    review_points: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(max_length=3)


class LeaveAnalysis(DifyLeaveContent):
    workflow_run_id: str = Field(min_length=1, max_length=128)
    analysis_version: str = Field(min_length=1, max_length=64)


class LeaveReceipt(BaseModel):
    apply_id: int
    approval_status: str
    reviewer_id: int | None
    row_version: int
    assignment_pending: bool
    notification_queued: bool
    ai_analysis: LeaveAnalysis | None = None
    ai_status: Literal["not_requested", "available", "unavailable"] = "not_requested"

    @model_validator(mode="after")
    def legacy_analysis_status(self):
        if "ai_status" not in self.model_fields_set and self.ai_analysis is not None:
            self.ai_status = "available"
        return self


class LeaveResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: LeaveReceipt
