"""智能报告接口 Pydantic 数据结构。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ReportConfigOut(BaseModel):
    """报告配置响应模型（查询/更新成功时返回）。"""

    model_config = ConfigDict(from_attributes=True)

    report_config_id: int
    report_code: str
    report_name: str
    report_period: str
    cron_expr: Optional[str] = None
    enabled: bool
    row_version: int
    created_at: datetime
    updated_at: datetime


class UpdateReportConfigRequest(BaseModel):
    """更新报告配置请求体；report_code 与 report_period 是枚举，不允许修改。"""

    row_version: int = Field(ge=1, description="乐观锁版本，传查询接口返回的值")
    report_name: str = Field(min_length=1, max_length=128)
    cron_expr: Optional[str] = Field(default=None, max_length=64)
    enabled: bool