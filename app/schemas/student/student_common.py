"""学生请求契约的公共基类与乐观锁版本，不加载配置或数据库。"""
from pydantic import BaseModel, ConfigDict, Field

class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class VersionInput(Input):
    expected_version: int = Field(ge=1)
