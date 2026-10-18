from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AnnouncementWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20000)
    status: Literal["draft", "published", "withdrawn"] = "draft"
    pinned: bool = False
    published_at: datetime | None = None
    expires_at: datetime | None = None
    expected_version: int | None = Field(default=None, ge=1)

    @field_validator("published_at", "expires_at")
    @classmethod
    def utc_time(cls, value):
        if value is not None:
            if value.tzinfo is None:
                raise ValueError("时间必须包含时区")
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    @model_validator(mode="after")
    def date_order(self):
        if self.expires_at and self.published_at and self.expires_at <= self.published_at:
            raise ValueError("结束时间必须晚于发布时间")
        return self
