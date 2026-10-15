"""智能报告模块 ORM 模型。

表：
    - ReportConfig  报告配置
    - ReportRecord  报告生成记录
    - ReportMetric  报告指标明细

与 scripts/report_module_ddl.sql 保持一致，由 scripts/init_db.py 自动导入并建表。
规范对齐：DATETIME(3)+UTC、编码键 utf8mb4_bin、CHECK 约束、真实外键、乐观锁 row_version。
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.mysql import DATETIME as MySQLDATETIME
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReportConfig(Base):
    """报告配置表。"""

    __tablename__ = "report_config"
    __table_args__ = (
        CheckConstraint(
            "report_code IN ('customer_overview','daily_report','weekly_report','mental_weekly','complaint_weekly')",
            name="ck_report_config_code",
        ),
        CheckConstraint("report_period IN ('day','week','month')", name="ck_report_config_period"),
        CheckConstraint("enabled IN (0,1)", name="ck_report_config_enabled"),
        CheckConstraint("row_version >= 1", name="ck_report_config_row_version"),
    )

    report_config_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="报告配置主键 ID")
    report_code: Mapped[str] = mapped_column(String(64, collation="utf8mb4_bin"), nullable=False, unique=True, comment="报告代码")
    report_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="报告名称")
    report_period: Mapped[str] = mapped_column(String(16, collation="utf8mb4_bin"), nullable=False, default="week", comment="报告周期")
    cron_expr: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="定时表达式")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at: Mapped[datetime] = mapped_column(MySQLDATETIME(fsp=3), nullable=False, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(MySQLDATETIME(fsp=3), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="并发版本号")


class ReportRecord(Base):
    """报告生成记录表。"""

    __tablename__ = "report_record"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_report_record_period"),
        CheckConstraint("status IN ('pending','running','success','failed')", name="ck_report_record_status"),
        CheckConstraint("source_record_count >= 0", name="ck_report_record_count"),
        CheckConstraint("row_version >= 1", name="ck_report_record_row_version"),
    )

    report_record_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="报告生成记录主键 ID")
    report_config_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("report_config.report_config_id", ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False, index=True, comment="报告配置 ID"
    )
    report_code: Mapped[str] = mapped_column(String(64, collation="utf8mb4_bin"), nullable=False, comment="报告代码")
    idempotency_key: Mapped[str] = mapped_column(String(128, collation="utf8mb4_bin"), nullable=False, unique=True, comment="幂等键")
    start_time: Mapped[datetime] = mapped_column(MySQLDATETIME(fsp=3), nullable=False, comment="统计起始时间")
    end_time: Mapped[datetime] = mapped_column(MySQLDATETIME(fsp=3), nullable=False, comment="统计截止时间")
    timezone: Mapped[str] = mapped_column(String(32), nullable=False, default="UTC", comment="统计口径时区")
    data_snapshot_at: Mapped[datetime | None] = mapped_column(MySQLDATETIME(fsp=3), nullable=True, comment="数据快照时间")
    report_version: Mapped[str] = mapped_column(String(32, collation="utf8mb4_bin"), nullable=False, default="v1", comment="报告生成版本")
    source_record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="来源记录数")
    report_content: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True, comment="报告正文")
    metric_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="可复算指标快照")
    status: Mapped[str] = mapped_column(String(16, collation="utf8mb4_bin"), nullable=False, default="pending", comment="状态")
    fail_reason: Mapped[str | None] = mapped_column(Text, nullable=True, comment="失败原因")
    generated_at: Mapped[datetime | None] = mapped_column(MySQLDATETIME(fsp=3), nullable=True, comment="生成完成时间")
    created_at: Mapped[datetime] = mapped_column(MySQLDATETIME(fsp=3), nullable=False, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(MySQLDATETIME(fsp=3), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="并发版本号")


class ReportMetric(Base):
    """报告指标明细表。"""

    __tablename__ = "report_metric"
    __table_args__ = (
        CheckConstraint("metric_value IS NOT NULL OR metric_text IS NOT NULL", name="ck_report_metric_value"),
        CheckConstraint("period_type IS NULL OR period_type IN ('day','week','month')", name="ck_report_metric_period"),
    )

    report_metric_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="报告指标明细主键 ID")
    report_record_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("report_record.report_record_id", ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False, index=True, comment="所属报告记录 ID"
    )
    metric_code: Mapped[str] = mapped_column(String(64, collation="utf8mb4_bin"), nullable=False, index=True, comment="指标代码")
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="指标名称")
    metric_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True, comment="指标数值")
    metric_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="指标文本值")
    metric_unit: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="单位")
    calc_rule: Mapped[str | None] = mapped_column(Text, nullable=True, comment="计算口径")
    period_type: Mapped[str | None] = mapped_column(String(16, collation="utf8mb4_bin"), nullable=True, comment="周期类型")
    created_at: Mapped[datetime] = mapped_column(MySQLDATETIME(fsp=3), nullable=False, server_default=func.now(), comment="创建时间")
