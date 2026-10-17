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

from app.models.common import student_profile, employee
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


class StudentAcademicEvent(UpdatedAtMixin, Base):
    """教务 DDL/考试节点的最小本地镜像，不建设完整教务系统。"""

    __tablename__ = "student_academic_event"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "source_system",
            "external_event_id",
            name="uk_academic_source",
        ),
        UniqueConstraint("id", "student_id", name="uk_academic_owner"),
        CheckConstraint("event_type IN ('ddl','exam')", name="ck_academic_type"),
        CheckConstraint(
            "event_status IN ('active','cancelled')", name="ck_academic_status"
        ),
        CheckConstraint("event_version >= 1", name="ck_academic_version"),
        Index("idx_academic_student", "student_id", "event_status", "due_at"),
        {**TABLE_OPTIONS, "comment": "学生学业截止及考试节点镜像表"},
    )
    id: Mapped[int] = mapped_column(
        ID_TYPE, primary_key=True, autoincrement=True, comment="学业节点主键ID"
    )
    student_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey(_student_reference.c.student_id, name="fk_academic_student"),
        nullable=False,
        comment="学生ID，关联student_profile.student_id",
    )
    source_system: Mapped[str] = mapped_column(
        ascii_string(32), nullable=False, comment="教务来源编码，如education"
    )
    external_event_id: Mapped[str] = mapped_column(
        binary_string(128),
        nullable=False,
        comment="源系统节点ID，与学生和来源组成同步唯一键",
    )
    event_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="节点类型：ddl截止日期/exam考试"
    )
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="论文或考试标题"
    )
    due_at: Mapped[datetime] = mapped_column(
        student_timestamp(), nullable=False, comment="准确截止或考试时点，UTC"
    )
    source_timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="来源IANA时区，如Asia/Shanghai"
    )
    event_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'active'"),
        comment="节点状态：active/cancelled",
    )
    # event_version 是影响提醒的业务版本，不能用 updated_at 或入库次数代替。
    event_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
        comment="节点时间或有效状态改变时递增的提醒版本",
    )
    source_updated_at: Mapped[datetime | None] = mapped_column(
        student_timestamp(),
        nullable=True,
        comment="源系统更新时间，UTC；防止旧消息覆盖新节点",
    )
    synced_at: Mapped[datetime | None] = mapped_column(
        student_timestamp(),
        nullable=True,
        comment="最后成功同步时间，UTC；用于展示数据新鲜度",
    )


class StudentAcademicReminder(CreatedAtMixin, Base):
    updated_at: Mapped[datetime] = mapped_column(student_timestamp(), nullable=False, default=utcnow, server_default=StudentCreatedDefault(), comment="提醒设置代次时间；发布不修改，六位微秒")
    """一条节点、一个提前量保存一份提醒设置。"""

    __tablename__ = "student_academic_reminder"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "academic_event_id",
            "lead_minutes",
            name="uk_reminder_setting",
        ),
        # 组合外键阻止学生B给学生A的节点建立提醒。
        ForeignKeyConstraint(
            ["academic_event_id", "student_id"],
            ["student_academic_event.id", "student_academic_event.student_id"],
            name="fk_reminder_event",
        ),
        CheckConstraint("lead_minutes >= 0", name="ck_reminder_lead"),
        CheckConstraint("event_version >= 1", name="ck_reminder_version"),
        CheckConstraint(
            "status IN ('pending','queued','sent','cancelled')",
            name="ck_reminder_status",
        ),
        CheckConstraint(
            "status <> 'sent' OR sent_at IS NOT NULL", name="ck_reminder_sent"
        ),
        Index("idx_reminder_due", "status", "notify_at"),
        {**TABLE_OPTIONS, "comment": "学生学业提醒设置与执行状态表"},
    )
    id: Mapped[int] = mapped_column(
        ID_TYPE, primary_key=True, autoincrement=True, comment="提醒主键ID"
    )
    student_id: Mapped[int] = mapped_column(
        ID_TYPE, nullable=False, comment="节点所属学生，通过组合外键关联同一学生"
    )
    academic_event_id: Mapped[int] = mapped_column(
        ID_TYPE, nullable=False, comment="学业节点ID，组合关联student_academic_event"
    )
    lead_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="提前分钟数；1440为一天，0为到点提醒"
    )
    notify_at: Mapped[datetime] = mapped_column(
        student_timestamp(),
        nullable=False,
        comment="计划提醒时点，UTC；由节点时间减提前量计算",
    )
    event_version: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="对应节点版本，发送前须检查仍一致"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
        comment="pending待执行/queued已入队/sent已投递/cancelled已取消",
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        student_timestamp(), nullable=True, comment="当前版本实际成功发送时间，UTC"
    )


class StudentApplicationProgress(UpdatedAtMixin, Base):
    """一个学生的一份申请、一个阶段保留最新进度。"""

    __tablename__ = "student_application_progress"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "source_system",
            "external_application_id",
            "stage_code",
            name="uk_progress_stage",
        ),
        CheckConstraint(
            "stage_code IN ('document_review','school_application','visa_process')",
            name="ck_progress_stage",
        ),
        Index("idx_progress_student", "student_id", "synced_at"),
        {**TABLE_OPTIONS, "comment": "学生留学申请阶段最新进度镜像表"},
    )
    id: Mapped[int] = mapped_column(
        ID_TYPE, primary_key=True, autoincrement=True, comment="阶段进度主键ID"
    )
    student_id: Mapped[int] = mapped_column(
        ID_TYPE,
        ForeignKey(_student_reference.c.student_id, name="fk_progress_student"),
        nullable=False,
        comment="学生ID，关联student_profile.student_id",
    )
    source_system: Mapped[str] = mapped_column(
        ascii_string(32), nullable=False, comment="CRM或申请系统来源编码"
    )
    external_application_id: Mapped[str] = mapped_column(
        binary_string(128),
        nullable=False,
        comment="源系统申请ID，用于区分不同院校和项目",
    )
    application_name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="院校或申请项目展示名称"
    )
    stage_code: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="document_review文书/school_application院校/visa_process签证",
    )
    stage_status: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="外部契约映射的阶段状态，不由AI臆造"
    )
    detail: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="必要进度说明，如需补充材料"
    )
    source_updated_at: Mapped[datetime | None] = mapped_column(
        student_timestamp(), nullable=True, comment="源系统更新时间，UTC"
    )
    synced_at: Mapped[datetime | None] = mapped_column(
        student_timestamp(), nullable=True, comment="最后成功同步时间，UTC；失败不刷新"
    )


# 建表脚本显式传入这五张表，防止其他组员新增的模型被顺带创建。
STUDENT_TABLES = (
    MentalHealthProfile.__table__,
    MentalWarning.__table__,
    StudentAcademicEvent.__table__,
    StudentAcademicReminder.__table__,
    StudentApplicationProgress.__table__,
)
