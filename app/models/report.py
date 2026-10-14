"""智能报告模块 ORM 模型。

表：
    - ReportConfig  报告配置
    - ReportRecord  报告生成记录
    - ReportMetric  报告指标明细

由 scripts/init_db.py 自动导入并建表。
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReportConfig(Base):
    """报告配置表。"""

    __tablename__ = "report_config"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    report_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="报告代码")
    report_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="报告名称")
    report_period: Mapped[str] = mapped_column(String(16), nullable=False, default="week", comment="报告周期")
    cron_expr: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="定时表达式")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )


class ReportRecord(Base):
    """报告生成记录表。"""

    __tablename__ = "report_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    report_config_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="报告配置ID")
    report_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="报告代码")
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, comment="幂等键")
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="统计起始时间")
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="统计截止时间")
    timezone: Mapped[str] = mapped_column(String(32), nullable=False, default="UTC", comment="统计时区")
    data_snapshot_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="数据快照时间")
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1", comment="生成版本")
    source_record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="来源记录数")
    report_content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="报告正文")
    metric_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="可复算指标快照")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", comment="状态")
    fail_reason: Mapped[str | None] = mapped_column(Text, nullable=True, comment="失败原因")
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="生成完成时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")


class ReportMetric(Base):
    """报告指标明细表。"""

    __tablename__ = "report_metric"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    report_record_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="报告记录ID")
    metric_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="指标代码")
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="指标名称")
    metric_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True, comment="指标数值")
    metric_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="指标文本值")
    metric_unit: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="单位")
    calc_rule: Mapped[str | None] = mapped_column(Text, nullable=True, comment="计算口径")
    period_type: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="周期类型")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
