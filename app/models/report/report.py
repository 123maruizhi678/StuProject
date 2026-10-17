"""智能报告模块 ORM 模型。

本文件定义智能报告模块的表映射，与 SQL 脚本保持一致：
    - scripts/sql/all.sql（全量结构唯一主基线）
    - scripts/sql/bk/智能报告/report_module_ddl.sql（模块建表脚本，受控抽取件）

    - ReportConfig  报告配置表（9 字段，已部署）
    - ReportRecord  报告生成记录表（18 字段，已部署）
    - ReportMetric  报告指标明细表（10 字段，已部署）
    - ReportTask    报告执行任务表（041 拟新增，尚未部署；仅声明映射，
                     不纳入 REPORT_TABLES，初始化脚本不创建）

所有字段均有中文数据库注释；时间统一存 UTC、精确到毫秒 DATETIME(3)；
代码/状态/幂等键使用 utf8mb4_bin 排序规则，普通文本使用表默认
utf8mb4_0900_ai_ci。

范围（006）与审计（043）等目标增量字段不在此声明：新增表字段须开发评审，
未部署前不得写入本文件或据此声称已建表。
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import DATETIME, JSON, LONGTEXT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# 表选项与全量脚本一致：InnoDB 支持外键，utf8mb4 支持中文及完整 Unicode。
# 默认排序规则供普通文本使用；状态、编码列单独使用二进制排序规则。
TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


def utcnow() -> datetime:
    """数据库连接统一使用 UTC；naive datetime 由 MySQL 侧按会话时区解释。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def report_timestamp():
    """报告模块统一 DATETIME(3) 毫秒精度，不能降级为 DATE 或秒级 DATETIME。"""
    return DateTime().with_variant(DATETIME(fsp=3), "mysql")


def binary_string(length: int):
    """编码、状态、幂等键使用二进制排序规则，避免大小写/重音误判。"""
    return String(length).with_variant(
        VARCHAR(length, collation="utf8mb4_bin"), "mysql"
    )


def longtext_type():
    """报告正文可能超出 TEXT 上限，MySQL 侧存 LONGTEXT。"""
    return Text().with_variant(LONGTEXT(), "mysql")


class CreatedAtMixin:
    """服务端产生创建时间；所有数据库连接须使用 UTC。"""

    created_at: Mapped[datetime] = mapped_column(
        report_timestamp(),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="记录创建时间，UTC。",
    )


class UpdatedAtMixin(CreatedAtMixin):
    """可变记录另外保存最后修改时间。"""

    # ON UPDATE 由 MySQL 更新；不能代替实际发生时间或报告生成时间。
    updated_at: Mapped[datetime] = mapped_column(
        report_timestamp(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"),
        comment="记录最近更新时间，UTC。",
    )


class ReportConfig(UpdatedAtMixin, Base):
    """报告配置表：五种报告各自的名称、周期、定时表达式与启停开关。"""

    __tablename__ = "report_config"
    __table_args__ = (
        UniqueConstraint("report_code", name="uq_report_config_code"),
        CheckConstraint(
            "report_code IN ('customer_overview','daily_report','weekly_report',"
            "'mental_weekly','complaint_weekly')",
            name="ck_report_config_code",
        ),
        CheckConstraint(
            "report_period IN ('day','week','month')", name="ck_report_config_period"
        ),
        CheckConstraint("enabled IN (0,1)", name="ck_report_config_enabled"),
        CheckConstraint("row_version >= 1", name="ck_report_config_row_version"),
        {**TABLE_OPTIONS, "comment": "报告配置表"},
    )
    report_config_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="报告配置主键ID",
    )
    report_code: Mapped[str] = mapped_column(
        binary_string(64), nullable=False, comment="报告代码（五类枚举，见 CHECK）。"
    )
    report_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="报告名称。"
    )
    report_period: Mapped[str] = mapped_column(
        binary_string(16),
        nullable=False,
        server_default=text("'week'"),
        comment="报告周期：day/week/month。",
    )
    cron_expr: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="定时表达式（cron，按东八区配置）。"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("1"),
        comment="是否启用：1 启用、0 停用。",
    )
    row_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
        comment="并发版本号，每次业务修改递增。",
    )


class ReportRecord(UpdatedAtMixin, Base):
    """报告生成记录表：一次生成任务 / 一份报告正文与指标快照各一行。"""

    __tablename__ = "report_record"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_report_record_idempotency"),
        CheckConstraint("end_time > start_time", name="ck_report_record_period"),
        CheckConstraint(
            "status IN ('pending','running','success','failed')",
            name="ck_report_record_status",
        ),
        CheckConstraint("source_record_count >= 0", name="ck_report_record_count"),
        CheckConstraint("row_version >= 1", name="ck_report_record_row_version"),
        Index("idx_report_record_config", "report_config_id"),
        Index("idx_report_record_code_time", "report_code", "start_time", "end_time"),
        Index("idx_report_record_status", "status"),
        {**TABLE_OPTIONS, "comment": "报告生成记录表"},
    )
    report_record_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="报告生成记录主键ID",
    )
    report_config_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "report_config.report_config_id",
            name="fk_report_record_config_id",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
        comment="报告配置ID，外键关联 report_config.report_config_id。",
    )
    report_code: Mapped[str] = mapped_column(
        binary_string(64), nullable=False, comment="报告代码（冗余，便于按类型检索）。"
    )
    idempotency_key: Mapped[str] = mapped_column(
        binary_string(128),
        nullable=False,
        comment="幂等键：report_code+时间窗+版本。",
    )
    start_time: Mapped[datetime] = mapped_column(
        report_timestamp(), nullable=False, comment="统计起始时间（UTC）。"
    )
    end_time: Mapped[datetime] = mapped_column(
        report_timestamp(),
        nullable=False,
        comment="统计截止时间（UTC），必须晚于起始。",
    )
    timezone: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'UTC'"),
        comment="统计口径时区。",
    )
    data_snapshot_at: Mapped[datetime | None] = mapped_column(
        report_timestamp(),
        nullable=True,
        comment="数据快照时间，用于指标可复算。",
    )
    report_version: Mapped[str] = mapped_column(
        binary_string(32),
        nullable=False,
        server_default=text("'v1'"),
        comment="报告生成版本，参与幂等键。",
    )
    source_record_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="来源记录数，用于追溯与识别数据不足。",
    )
    report_content: Mapped[str | None] = mapped_column(
        longtext_type(), nullable=True, comment="报告正文（AI 生成的结构化文本）。"
    )
    metric_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="可复算指标快照（JSON）。"
    )
    status: Mapped[str] = mapped_column(
        binary_string(32),
        nullable=False,
        server_default=text("'pending'"),
        comment="状态：pending/running/success/failed。",
    )
    fail_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="失败原因。"
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        report_timestamp(), nullable=True, comment="生成完成时间（UTC）。"
    )
    row_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
        comment="并发版本号。",
    )


class ReportMetric(CreatedAtMixin, Base):
    """报告指标明细表：一条指标一行，支撑“指标可复算”验收。"""

    __tablename__ = "report_metric"
    __table_args__ = (
        CheckConstraint(
            "metric_value IS NOT NULL OR metric_text IS NOT NULL",
            name="ck_report_metric_value",
        ),
        CheckConstraint(
            "period_type IS NULL OR period_type IN ('day','week','month')",
            name="ck_report_metric_period",
        ),
        Index("idx_report_metric_record", "report_record_id"),
        Index("idx_report_metric_code", "metric_code"),
        {**TABLE_OPTIONS, "comment": "报告指标明细表"},
    )
    report_metric_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="报告指标明细主键ID",
    )
    report_record_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "report_record.report_record_id",
            name="fk_report_metric_record_id",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
        comment="所属报告记录ID，外键关联 report_record.report_record_id。",
    )
    metric_code: Mapped[str] = mapped_column(
        binary_string(64), nullable=False, comment="指标代码。"
    )
    metric_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="指标名称。"
    )
    metric_value: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 4), nullable=True, comment="指标数值（数值型指标）。"
    )
    metric_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="指标文本值（非数值型指标）。"
    )
    metric_unit: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="单位。"
    )
    calc_rule: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="计算口径/规则说明，用于指标可复算。"
    )
    period_type: Mapped[str | None] = mapped_column(
        binary_string(16), nullable=True, comment="周期类型：day/week/month。"
    )


class ReportTask(UpdatedAtMixin, Base):
    """报告执行任务表（041 拟新增，尚未部署）。

    报告原三表继续保留；report_record.status 仍为对外四状态投影，执行所有权
    以本任务为准。任务为执行基础设施，不新建第四张报告结果表。
    本映射仅声明目标结构：纳入 REPORT_TASK_TABLE 供未来受控增量建表使用，
    当前初始化脚本不创建、运行时不依赖；report_task 未部署时执行所有权
    回退为 report_record 行版本栅栏（见 app/tasks/report/report_tasks.py）。
    """

    __tablename__ = "report_task"
    __table_args__ = (
        UniqueConstraint("report_record_id", name="uq_report_task_record"),
        UniqueConstraint("idempotency_key", name="uq_report_task_idempotency"),
        CheckConstraint(
            "status IN ('pending','running','success','failed')",
            name="ck_report_task_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_report_task_attempt"),
        CheckConstraint("row_version >= 1", name="ck_report_task_row_version"),
        Index("idx_report_task_status_lease", "status", "lease_expires_at"),
        {**TABLE_OPTIONS, "comment": "报告执行任务表（拟新增）"},
    )
    report_task_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="报告执行任务主键ID",
    )
    report_record_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "report_record.report_record_id",
            name="fk_report_task_record_id",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
        comment="所属报告记录ID，外键关联 report_record.report_record_id。",
    )
    report_code: Mapped[str] = mapped_column(
        binary_string(64), nullable=False, comment="报告代码，与关联记录一致。"
    )
    idempotency_key: Mapped[str] = mapped_column(
        binary_string(128),
        nullable=False,
        comment="报告业务键，与关联记录一致。",
    )
    status: Mapped[str] = mapped_column(
        binary_string(32),
        nullable=False,
        server_default=text("'pending'"),
        comment="任务状态：pending/running/success/failed。",
    )
    lease_owner: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="当前租约持有者标识。"
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        report_timestamp(), nullable=True, comment="租约截止时间（UTC）。"
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="执行尝试计数；不参与业务键。",
    )
    last_error: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="最近一次脱敏错误说明。"
    )
    model_checkpoint: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="受控模型调用检查点：调用阶段、可信workflow_run_id及受保护结果回执引用；不写Key或原业务文本。",
    )
    row_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
        comment="并发版本号。",
    )


# 建表脚本显式传入这三张已部署表，防止其他组员新增的模型被顺带创建。
REPORT_TABLES = (
    ReportConfig.__table__,
    ReportRecord.__table__,
    ReportMetric.__table__,
)

# 041 拟新增执行任务表；尚未部署，仅在未来受控增量中使用。
REPORT_TASK_TABLE = ReportTask.__table__
