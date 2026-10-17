"""客户字段抽取 v1：模型只提供事实字段，不能提供权限或研判结论。"""
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

EXTRACT_CONTRACT_VERSION = "v1"
MAX_TEXT_BYTES = 100 * 1024


def text_type(length):
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=length)]


class CustomerExtractFields(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    full_name: text_type(100) | None = None
    gender: Literal["男", "女"] | None = None
    age: Annotated[int, Field(ge=0, le=120)] | None = None
    education_level: text_type(32) | None = None
    major: text_type(100) | None = None
    work_years: Annotated[int, Field(ge=0, le=80)] | None = None
    industry: text_type(64) | None = None
    position_title: text_type(100) | None = None
    city: text_type(64) | None = None
    income_level: text_type(32) | None = None
    target_product_code: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,31}$")] | None = None
    contact_email: text_type(254) | None = None
    phone: Annotated[str, StringConstraints(pattern=r"^1[3-9][0-9]{9}$")] | None = None

    @field_validator("contact_email")
    @classmethod
    def email_format(cls, value):
        if value is not None and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("invalid email")
        return value


FIELD_SCHEMA = CustomerExtractFields.model_json_schema()
