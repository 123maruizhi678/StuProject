"""business_notification 的唯一共享映射；字段依据 scripts/sql/all.sql，不在启动时建表。"""
from sqlalchemy import CheckConstraint, Column, DateTime, FetchedValue, ForeignKeyConstraint, Index, Integer, String, Table, Text, UniqueConstraint, text
from sqlalchemy.dialects import mysql

from app.database import Base
from ._types import identifier, utc_now, utc_timestamp

business_notification = Table(
    "business_notification", Base.metadata,
    Column('notification_id', identifier, primary_key=True, autoincrement=True, nullable=False),
    Column('entity_type', String(32).with_variant(mysql.VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False),
    Column('entity_id', identifier, nullable=False),
    Column('event_code', String(64).with_variant(mysql.VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=False),
    Column('employee_id', identifier, nullable=True),
    Column('student_id', identifier, nullable=True),
    Column('channel', String(20), nullable=False),
    Column('title', String(200), nullable=False),
    Column('content', Text, nullable=False),
    Column('dedupe_key', String(160).with_variant(mysql.VARCHAR(160, collation="utf8mb4_bin"), "mysql"), nullable=False),
    Column('delivery_status', String(20).with_variant(mysql.VARCHAR(20, collation="utf8mb4_bin"), "mysql"), nullable=False, server_default=text("'pending'")),
    Column('attempt_count', Integer, nullable=False, server_default=text('0')),
    Column('next_retry_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=True),
    Column('lease_until', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=True),
    Column('sent_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=True),
    Column('read_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=True),
    Column('last_error_code', String(64).with_variant(mysql.VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=True),
    Column('created_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp()),
    Column('updated_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp(), onupdate=utc_now, server_onupdate=FetchedValue()),
    Column('row_version', Integer, nullable=False, server_default=text('1')),
    UniqueConstraint('dedupe_key', name='uq_notification_dedupe'),
    Index('idx_notification_retry', 'delivery_status', 'next_retry_at'),
    Index('idx_notification_employee_read', 'employee_id', 'read_at', 'created_at'),
    Index('idx_notification_student_read', 'student_id', 'read_at', 'created_at'),
    Index('idx_notification_entity', 'entity_type', 'entity_id'),
    ForeignKeyConstraint(['employee_id'], ['employee.employee_id'], name='fk_business_notification_employee_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(['student_id'], ['student_profile.student_id'], name='fk_business_notification_student_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    CheckConstraint('((employee_id IS NOT NULL) + (student_id IS NOT NULL)) = 1', name='ck_svc_notification_recipient'),
    CheckConstraint("delivery_status IN ('pending','sending','sent','failed','dead_letter')", name='ck_svc_notification_status'),
    CheckConstraint('attempt_count >= 0', name='ck_notification_attempt'),
    CheckConstraint('row_version >= 1', name='ck_business_notification_row_version'),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
)
