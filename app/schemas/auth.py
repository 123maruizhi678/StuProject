"""Authentication request schemas."""
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求参数；约束用户名和密码输入长度。"""
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
