"""公共认证的请求及响应契约。"""
from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256, repr=False)

    @field_validator("username")
    @classmethod
    def meaningful_username(cls, value: str) -> str:
        if value != value.strip() or not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError("用户名不得为空或包含首尾空白、控制字符")
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AccessResponse(BaseModel):
    user_id: int
    identity_type: str
    role_codes: list[str]
    permissions: list[str]
    pages: dict
    modules: dict


class PublicAccessResponse(BaseModel):
    pages: dict
    modules: dict
