"""student_admin_service 的唯一共享映射；字段依据 scripts/sql/all.sql，不在启动时建表。"""
from sqlalchemy import CHAR, CheckConstraint, Column, DateTime, FetchedValue, ForeignKeyConstraint, Index, Integer, JSON, String, Table, Text, UniqueConstraint, text
from sqlalchemy.dialects import mysql

from app.database import Base
from ._types import identifier, utc_now, utc_timestamp

student_admin_service = Table(
    "student_admin_service", Base.metadata,
    Column('id', identifier, primary_key=True, autoincrement=True, nullable=False),
    Column('student_id', identifier, nullable=False),
    Column('apply_type', String(20), nullable=False),
    Column('apply_content', Text, nullable=False),
    Column('approval_status', String(20), nullable=False, server_default=text("'pending'")),
    Column('edu_related_data', JSON, nullable=True),
    Column('leave_start_at', DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=True),
    Column('leave_end_at', DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=True),
    Column('reviewer_id', identifier, nullable=True),
    Column('reviewed_at', DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=True),
    Column('approval_comment', Text, nullable=True),
    Column('request_key', String(128).with_variant(mysql.VARCHAR(128, collation="ascii_bin"), "mysql"), nullable=False),
    Column('request_hash', CHAR(64).with_variant(mysql.CHAR(64, collation="ascii_bin"), "mysql"), nullable=False),
    Column('row_version', Integer, nullable=False, server_default=text('1')),
    Column('created_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp()),
    Column('updated_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp(), onupdate=utc_now, server_onupdate=FetchedValue()),
    UniqueConstraint('student_id', 'request_key', name='uk_admin_request'),
    Index('idx_admin_student', 'student_id', 'created_at'),
    Index('idx_admin_review', 'reviewer_id', 'approval_status', 'created_at'),
    ForeignKeyConstraint(['student_id'], ['student_profile.student_id'], name='fk_admin_student'),
    CheckConstraint("apply_type IN ('leave', 'academic')", name='ck_admin_type'),
    CheckConstraint("approval_status IN ('pending', 'approved', 'rejected', 'cancelled')", name='ck_admin_status'),
    CheckConstraint("apply_type <> 'leave' OR (leave_start_at IS NOT NULL AND leave_end_at IS NOT NULL AND leave_end_at > leave_start_at)", name='ck_admin_leave'),
    CheckConstraint("approval_status NOT IN ('approved', 'rejected') OR (reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL)", name='ck_admin_decision'),
    CheckConstraint('row_version >= 1', name='ck_admin_version'),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
)
