"""学生智能助手 ORM 模型。

本文件定义五张学生专属表；初始化另纳入企业共用请假表。
身份、员工、工单、通知和操作记录复用公共设计；模型不执行 AI SQL。
所有字段均有中文数据库注释；下面的 Python 注释解释关键建表语句。
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
    func,
)
from sqlalchemy.dialects.mysql import DATETIME, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
metadata = Base.metadata

from app.models.common import (student_profile, employee, student_academic_event,
    student_academic_reminder, student_application_progress)
from app.models.student.student_types import (
    ID_TYPE,
    student_timestamp,
    binary_string,
    ascii_string,
    utcnow,
    StudentCreatedDefault,
    StudentUpdatedDefault,
)

_student_reference = student_profile
_employee_reference = employee

# 表选项与企业模块一致：InnoDB 支持外键，utf8mb4 支持中文及完整 Unicode。
# 默认排序规则供普通文本使用；状态、外部编码单独使用二进制排序规则。
TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


class CreatedAtMixin:
    """服务端产生创建时间；所有数据库连接须使用 UTC。"""

    # 学生时间沿用既有 DATETIME(6) 微秒精度；它本身不保存时区名称。
    created_at: Mapped[datetime] = mapped_column(
        student_timestamp(),
        nullable=False,
        default=utcnow,
        server_default=StudentCreatedDefault(),
        comment="创建时间，UTC",
    )


class UpdatedAtMixin(CreatedAtMixin):
    """可变记录另外保存最后修改时间。"""

    # ON UPDATE 由 MySQL 更新；这个时间不能代替实际发生/审批时间。
    updated_at: Mapped[datetime] = mapped_column(
        student_timestamp(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=StudentUpdatedDefault(),
        comment="最近修改时间，UTC",
    )


class MentalHealthProfile(CreatedAtMixin, Base):
    """一条源消息评估保存一行，不用覆盖方式保存学生最新画像。"""

    __tablename__ = "mental_health_profile"
    __table_args__ = (
        # 同一学生、同一源事件重复回调只落一条画像。
        UniqueConstraint("student_id", "source_event_id", name="uk_profile_source"),
        # 为预警的组合外键提供明确唯一键，保证评估和预警属于同一学生。
        UniqueConstraint("id", "student_id", name="uk_profile_owner"),
        CheckConstraint(
            "emotion_score >= 0 AND emotion_score <= 100", name="ck_profile_score"
        ),
        CheckConstraint(
            "risk_level IN ('low','medium','high','critical')", name="ck_profile_risk"
        ),
        Index("idx_profile_history", "student_id", "observed_at"),
        Index("idx_profile_report", "observed_at", "risk_level"),
        {**TABLE_OPTIONS, "comment": "学生心理评估历史表"},
    )
    id: Mapped[int] = mapped_column(
        ID_TYPE, primary_key=True, autoincrement=True, comment="评估主键ID"
    )
    # student_id 是企业学生主表的内部主键，不能填学号或教务外部ID。
    student_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey(_student_reference.c.student_id, name="fk_profile_student"),
        nullable=False,
        comment="学生ID，关联student_profile.student_id",
    )
    emotion_tag: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="本次情绪标签"
    )
    emotion_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="分值0至100，越高表示情绪越平稳；不代表医学诊断",
    )
    # 旧方案字段保留为可空兼容列，新数据不再把历史重复累积到 JSON。
    history_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="旧历史JSON兼容字段；新记录保持NULL"
    )
    risk_level: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="评估风险：low/medium/high/critical"
    )
    observed_at: Mapped[datetime] = mapped_column(
        student_timestamp(),
        nullable=False,
        comment="源消息发生时间，UTC；区别于入库时间",
    )
    source_event_id: Mapped[str] = mapped_column(
        ascii_string(128), nullable=False, comment="可信入口生成的源事件ID，重试时复用"
    )
    workflow_run_id: Mapped[str | None] = mapped_column(
        ascii_string(128), nullable=True, comment="Dify工作流运行ID，仅用于追溯"
    )
    analysis_version: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="心理分析配置版本，明确分值和风险口径"
    )


class MentalWarning(UpdatedAtMixin, Base):
    """高危预警及人工处置；通知成功不等于预警已处理。"""

    __tablename__ = "mental_warning"
    __table_args__ = (
        UniqueConstraint("profile_id", name="uk_warning_profile"),
        ForeignKeyConstraint(
            ["profile_id", "student_id"],
            ["mental_health_profile.id", "mental_health_profile.student_id"],
            name="fk_warning_profile",
        ),
        CheckConstraint("risk_level IN ('high','critical')", name="ck_warning_risk"),
        CheckConstraint(
            "follower_status IN ('pending','processing','closed')",
            name="ck_warning_status",
        ),
        CheckConstraint(
            "follower_status <> 'closed' OR (follower_id IS NOT NULL AND "
            "acknowledged_at IS NOT NULL AND closed_at IS NOT NULL AND handling_result IS NOT NULL)",
            name="ck_warning_closed",
        ),
        CheckConstraint("version >= 1", name="ck_warning_version"),
        Index("idx_warning_student", "student_id", "created_at"),
        Index("idx_warning_follower", "follower_id", "follower_status", "created_at"),
        {**TABLE_OPTIONS, "comment": "学生心理预警及人工处置表"},
    )
    id: Mapped[int] = mapped_column(
        ID_TYPE, primary_key=True, autoincrement=True, comment="预警主键ID"
    )
    student_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey(_student_reference.c.student_id, name="fk_warning_student"),
        nullable=False,
        comment="学生ID，关联student_profile.student_id",
    )
    profile_id: Mapped[int] = mapped_column(
        ID_TYPE, nullable=False, comment="触发评估ID，与student_id组成画像外键"
    )
    trigger_reason: Mapped[str] = mapped_column(
        Text, nullable=False, comment="必要的触发依据，仅授权处理人可见"
    )
    risk_level: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="预警等级：high/critical"
    )
    follower_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
        comment="人工处理状态：pending/processing/closed",
    )
    # 外键用 employee.employee_id，保持 BIGINT 有符号类型与企业表一致。
    # 未分派时允许为空，先保存风险；后端须继续分派或升级，不能丢弃预警。
    follower_id: Mapped[int | None] = mapped_column(
        ID_TYPE,
        ForeignKey(_employee_reference.c.employee_id, name="fk_warning_employee"),
        nullable=True,
        comment="处理员工ID，关联employee.employee_id；未分派可空",
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        student_timestamp(), nullable=True, comment="真实人工接手时间，UTC"
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        student_timestamp(), nullable=True, comment="人工关闭时间，UTC"
    )
    handling_result: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="最终人工处置结果；关闭时不能为空"
    )
    # 沿用组长实库命名 version；业务更新须带旧版本条件并自行递增。
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
        comment="并发版本，业务更新时条件校验并递增",
    )


class StudentAcademicEvent(Base):
    __table__ = student_academic_event


class StudentAcademicReminder(Base):
    __table__ = student_academic_reminder


class StudentApplicationProgress(Base):
    __table__ = student_application_progress


# 建表脚本显式传入这五张表，防止其他组员新增的模型被顺带创建。
STUDENT_TABLES = (
    MentalHealthProfile.__table__,
    MentalWarning.__table__,
    StudentAcademicEvent.__table__,
    StudentAcademicReminder.__table__,
    StudentApplicationProgress.__table__,
)
