"""service_ticket_record 的唯一共享映射；字段依据 scripts/sql/all.sql，不在启动时建表。"""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKeyConstraint, Index, Integer, String, Table, Text, UniqueConstraint, text
from sqlalchemy.dialects import mysql

from app.database import Base
from ._types import identifier, utc_now, utc_timestamp

service_ticket_record = Table(
    "service_ticket_record", Base.metadata,
    Column('ticket_record_id', identifier, primary_key=True, autoincrement=True, nullable=False),
    Column('ticket_id', identifier, nullable=False),
    Column('record_type', String(32), nullable=False),
    Column('employee_id', identifier, nullable=True),
    Column('student_id', identifier, nullable=True),
    Column('service_code', String(64).with_variant(mysql.VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=True),
    Column('content', Text, nullable=True),
    Column('visibility', String(20).with_variant(mysql.VARCHAR(20, collation="utf8mb4_bin"), "mysql"), nullable=False, server_default=text("'internal'")),
    Column('to_status', String(32), nullable=True),
    Column('cycle_no', Integer, nullable=False, server_default=text('1')),
    Column('record_key', String(160).with_variant(mysql.VARCHAR(160, collation="utf8mb4_bin"), "mysql"), nullable=False),
    Column('created_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp()),
    UniqueConstraint('record_key', name='uq_ticket_record_key'),
    Index('idx_ticket_record_time', 'ticket_id', 'created_at', 'ticket_record_id'),
    Index('idx_ticket_record_employee', 'employee_id'),
    Index('idx_ticket_record_student', 'student_id'),
    ForeignKeyConstraint(['ticket_id'], ['service_ticket.ticket_id'], name='fk_service_ticket_record_ticket_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(['employee_id'], ['employee.employee_id'], name='fk_service_ticket_record_employee_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(['student_id'], ['student_profile.student_id'], name='fk_service_ticket_record_student_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    CheckConstraint('((employee_id IS NOT NULL) + (student_id IS NOT NULL) + (service_code IS NOT NULL)) = 1', name='ck_ticket_record_actor'),
    CheckConstraint('service_code IS NULL OR LENGTH(TRIM(service_code)) > 0', name='ck_ticket_record_service'),
    CheckConstraint("visibility IN ('internal','student_visible')", name='ck_ticket_record_visibility'),
    CheckConstraint('cycle_no >= 1', name='ck_ticket_record_cycle'),
    CheckConstraint("to_status IS NULL OR to_status IN ('open','assigned','processing','awaiting_student','closed','reopened')", name='ck_ticket_record_to_status'),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
)
