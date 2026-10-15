"""认证接口 Pydantic 数据结构：定义登录请求字段及输入长度约束。"""
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求参数；约束用户名和密码输入长度。"""
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
