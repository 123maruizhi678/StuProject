"""按最终建表 SQL 映射；公共表只注册在 Base.metadata，导入不执行建表。"""
from sqlalchemy import (Table, Column, BigInteger, Integer, String, Text, Boolean, DateTime, Date, JSON, Numeric, LargeBinary, UniqueConstraint, CheckConstraint, ForeignKeyConstraint, text)
from sqlalchemy.dialects.mysql import DATETIME, VARCHAR
from app.database import Base
identifier = BigInteger().with_variant(Integer, "sqlite")

business_notification = Table("business_notification", Base.metadata,
    Column("notification_id", identifier, nullable=False, comment="PK；自增；业务通知记录主键 ID。 主键（PK）。", primary_key=True, autoincrement=True),
    Column("entity_type", String(32).with_variant(VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="关联业务实体类型，如请假、投诉或跟进。"),
    Column("entity_id", identifier, nullable=False, comment="关联业务记录 ID，由业务服务按实体类型校验。"),
    Column("event_code", String(64).with_variant(VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="业务通知原因，如待审批、审批结果或投诉解决。"),
    Column("employee_id", identifier, nullable=True, comment="员工接收人 ID，与学生接收人二选一。 外键（FK）关联 employee.employee_id。"),
    Column("student_id", identifier, nullable=True, comment="学生接收人 ID，与员工接收人二选一。 外键（FK）关联 student_profile.student_id。"),
    Column("channel", String(20), nullable=False, comment="投递渠道，如站内或企业消息。"),
    Column("title", String(200), nullable=False, comment="通知标题，只包含必要信息。"),
    Column("content", Text, nullable=False, comment="通知内容，不包含敏感业务原文。"),
    Column("dedupe_key", String(160).with_variant(VARCHAR(160, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="包含业务事件、轮次、接收人及渠道的唯一通知键。"),
    Column("delivery_status", String(20).with_variant(VARCHAR(20, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="pending 待发送、sending 发送中、sent 已发送、failed 失败、dead_letter 终止重试。", server_default=text("'pending'")),
    Column("attempt_count", Integer, nullable=False, comment="已尝试发送次数，初值 0。", server_default=text("0")),
    Column("next_retry_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=True, comment="下一次允许重试时间。"),
    Column("lease_until", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=True, comment="发送任务租约截止时间，用于恢复中断任务。"),
    Column("sent_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=True, comment="对应渠道确认接收消息的时间。"),
    Column("read_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=True, comment="真实已读时间，不支持回执时为空。"),
    Column("last_error_code", String(64).with_variant(VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=True, comment="最近一次发送失败的脱敏错误码。"),
    Column("created_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=False, comment="记录创建时间，UTC；连接必须设置 time_zone 为 +00:00", server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=False, comment="更新时自动刷新；记录最近更新时间，UTC", server_default=text("CURRENT_TIMESTAMP")),
    Column("row_version", Integer, nullable=False, comment="并发版本号；每次业务修改由后端递增", server_default=text("1")),
    UniqueConstraint("dedupe_key", name="uq_notification_dedupe"),
    CheckConstraint("((employee_id IS NOT NULL) + (student_id IS NOT NULL)) = 1", name="ck_svc_notification_recipient"),
    CheckConstraint("delivery_status IN ('pending','sending','sent','failed','dead_letter')", name="ck_svc_notification_status"),
    CheckConstraint("attempt_count >= 0", name="ck_notification_attempt"),
    CheckConstraint("row_version >= 1", name="ck_business_notification_row_version"),
    ForeignKeyConstraint(["employee_id"], ["employee.employee_id"], name="fk_joint_30", ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(["student_id"], ["student_profile.student_id"], name="fk_joint_31", ondelete="RESTRICT", onupdate="RESTRICT"),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
    comment="业务站内通知、收件人、去重、投递及重试",
)
