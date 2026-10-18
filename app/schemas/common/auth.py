"""认证接口 Pydantic 数据结构：定义登录请求字段及输入长度约束。"""
from pydantic import BaseModel, ConfigDict, Field, field_validator
import unicodedata


class LoginRequest(BaseModel):
    """登录请求参数；约束用户名和密码输入长度。"""
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UpdateProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    full_name: str = Field(min_length=1, max_length=100)
    expected_full_name: str = Field(min_length=1, max_length=100)

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, value):
        if any(unicodedata.category(char).startswith("C") for char in value):
            raise ValueError("姓名不能包含控制字符")
        return value
