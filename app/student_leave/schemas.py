"""S01 请求与回执；身份和审批状态不由请求体指定。"""
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class LeaveInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    leave_content: str = Field(min_length=1, max_length=5000)
    leave_type: str = Field(default="personal", min_length=1, max_length=32)
    leave_start_at: AwareDatetime
    leave_end_at: AwareDatetime

    @model_validator(mode="after")
    def validate_period(self):
        if self.leave_end_at <= self.leave_start_at:
            raise ValueError("请假结束时间必须晚于开始时间")
        return self


class LeaveReceipt(BaseModel):
    apply_id: int
    approval_status: str
    reviewer_id: int | None
    row_version: int
    assignment_pending: bool
    notification_queued: bool


class LeaveResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: LeaveReceipt
