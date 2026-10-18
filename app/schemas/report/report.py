"""智能报告接口 Pydantic 数据结构。

契约来源（操作文档第一章「报告五接口完整 Schema」035）：
    POST /api/v1/report/generate            手动生成（异步，先返回 pending + 报告ID）
    GET  /api/v1/report/list                分页列表（只给授权元数据）
    GET  /api/v1/report/{report_record_id}  查单份报告（含正文与指标快照）
    GET  /api/v1/report/configs             查询全部配置（平台管理员）
    PUT  /api/v1/report/configs/{report_code}  更新配置（乐观锁，平台管理员）

统一约定：
    - 所有时间响应使用带 Z 的 UTC ISO 8601 文本；业务默认时区为北京时间
      Asia/Shanghai，省略窗口按北京时间自然周期解析后转 UTC 存储（038）。
    - 拒绝未知字段（extra="forbid"），不接收客户端自报指标、操作者、版本、
      快照或报告正文。
"""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# 业务默认时区；本期显式值也仅接受该值（038）。
BUSINESS_TIMEZONE = "Asia/Shanghai"

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
    """报告配置响应模型（查询/更新成功时返回），按 report_code 排序。"""

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
    """更新报告配置请求体。

    report_code 与 report_period 由路径和存量配置决定，不允许修改；
    cron_expr 必填且可为 NULL（NULL 仅关闭该类自动调度，不放开手动生成权限）。
    """

    model_config = ConfigDict(extra="forbid")

    row_version: int = Field(ge=1, description="乐观锁版本，传查询接口返回的值")
    report_name: str = Field(min_length=1, max_length=128)
    # 必填（键必须存在）但可为 NULL；无默认值即 required。
    cron_expr: Optional[str] = Field(default=None, max_length=64)
    enabled: bool

    @field_validator("report_name")
    @classmethod
    def _trim_report_name(cls, value: str) -> str:
        """报告名称去首尾空白后须为 1..128 字符。"""
        trimmed = value.strip()
        if not 1 <= len(trimmed) <= 128:
            raise ValueError("report_name 去首尾空白后须为 1..128 字符")
        return trimmed

    @field_validator("cron_expr")
    @classmethod
    def _validate_cron_expr(cls, value: Optional[str]) -> Optional[str]:
        """cron_expr 非空时长度 1..64；调度语法由实际调度适配器复核。"""
        if value is None:
            return None
        trimmed = value.strip()
        if not 1 <= len(trimmed) <= 64:
            raise ValueError("cron_expr 非空时长度须为 1..64")
        return trimmed


class GenerateReportRequest(BaseModel):
    """生成报告请求体。

    report_code / timezone 在 schema 层收敛为枚举：前端按 OpenAPI 渲染下拉框，
    非法取值由统一异常处理器转为 200 + code=400 信封；
    时间窗合法性（对齐、跨度、不晚于受理时刻）仍由 service 层校验。
    """

    model_config = ConfigDict(extra="forbid")

    report_code: Literal[tuple(REPORT_CODES)] = Field(
        description="五类报告代码之一（下拉枚举）"
    )
    start_time: Optional[datetime] = Field(default=None, description="统计起始时间（显式时须带时区偏移）")
    end_time: Optional[datetime] = Field(default=None, description="统计截止时间（显式时须带时区偏移）")
    timezone: Literal["Asia/Shanghai"] = Field(
        default=BUSINESS_TIMEZONE, description="统计口径时区（下拉枚举）"
    )


class GenerateReportOut(BaseModel):
    """生成报告受理响应；复用时返回已有记录的真实状态，不强制改为 pending。"""

    report_record_id: int
    idempotency_key: str
    status: str
    reused: bool
    start_time: datetime
    end_time: datetime
    timezone: str


class ReportRecordOut(BaseModel):
    """单份报告详情响应（含正文与指标快照）。

    pending/running 时正文、完成时间、指标快照均为 NULL（不发布半成品）；
    success 才返回正式正文与已发布指标白名单；failed 返回脱敏 fail_reason
    且不返回半成品正文。
    """

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
    """报告列表项（不含正文、指标、失败详情或幂等请求凭据）。"""

    model_config = ConfigDict(from_attributes=True)

    report_record_id: int
    report_code: str
    report_name: str
    start_time: datetime
    end_time: datetime
    status: str
    generated_at: Optional[datetime] = None


class ReportListOut(BaseModel):
    """报告分页列表响应；total 与 items 使用相同授权过滤。"""

    total: int
    page: int
    page_size: int
    items: list[ReportListItem]
