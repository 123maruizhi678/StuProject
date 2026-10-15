"""智能报告接口 Pydantic 数据结构。"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# 五种报告代码（与 report_config.report_code 的 CHECK 约束保持一致）。
REPORT_CODES = (
    "customer_overview",
    "daily_report",
    "weekly_report",
    "mental_weekly",
    "complaint_weekly",
)

# 报告生成记录的状态集合（与 report_record.status 的 CHECK 约束保持一致）。
REPORT_STATUSES = ("pending", "running", "success", "failed")


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


class GenerateReportRequest(BaseModel):
    """生成报告请求体。

    report_code 是否属于五类枚举由 service 层对照 REPORT_CODES 校验，
    以便非法取值返回统一信封的 code=400，而不是 FastAPI 默认的 422。
    """

    report_code: str = Field(min_length=1, max_length=64, description="五类报告代码之一")
    start_time: Optional[datetime] = Field(default=None, description="统计起始时间（可选）")
    end_time: Optional[datetime] = Field(default=None, description="统计截止时间（可选）")
    timezone: str = Field(default="UTC", max_length=32, description="统计口径时区")


class ReportRecordOut(BaseModel):
    """单份报告详情响应（含正文与指标快照）。"""

    model_config = ConfigDict(from_attributes=True)

    report_record_id: int
    report_code: str
    report_name: str
    idempotency_key: str
    start_time: datetime
    end_time: datetime
    timezone: str
    data_snapshot_at: Optional[datetime] = None
    report_version: str
    source_record_count: int
    status: str
    report_content: Optional[str] = None
    metric_json: Optional[dict[str, Any]] = None
    fail_reason: Optional[str] = None
    generated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ReportListItem(BaseModel):
    """报告列表项（不含正文，只给元数据）。"""

    model_config = ConfigDict(from_attributes=True)

    report_record_id: int
    report_code: str
    report_name: str
    start_time: datetime
    end_time: datetime
    status: str
    generated_at: Optional[datetime] = None


class ReportListOut(BaseModel):
    """报告分页列表响应。"""

    total: int
    page: int
    page_size: int
    items: list[ReportListItem]
