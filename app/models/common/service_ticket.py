"""service_ticket 的唯一共享映射；字段依据 scripts/sql/all.sql，不在启动时建表。"""
from sqlalchemy import CheckConstraint, Column, DateTime, FetchedValue, ForeignKeyConstraint, Index, Integer, SmallInteger, String, Table, Text, UniqueConstraint, text
from sqlalchemy.dialects import mysql

from app.database import Base
from ._types import identifier, utc_now, utc_timestamp

service_ticket = Table(
    "service_ticket", Base.metadata,
    Column('ticket_id', identifier, primary_key=True, autoincrement=True, nullable=False),
    Column('ticket_no', String(32), nullable=False),
    Column('student_id', identifier, nullable=False),
    Column('ticket_type', String(20).with_variant(mysql.VARCHAR(20, collation="utf8mb4_bin"), "mysql"), nullable=False, server_default=text("'complaint'")),
    Column('category_code', String(32).with_variant(mysql.VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False),
    Column('content', Text, nullable=False),
    Column('ai_summary', Text, nullable=True),
    Column('priority', String(20), nullable=False, server_default=text("'normal'")),
    Column('employee_id', identifier, nullable=True),
    Column('handling_department_id', identifier, nullable=False),
    Column('status', String(32).with_variant(mysql.VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, server_default=text("'open'")),
    Column('first_response_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=True),
    Column('response_due_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False),
    Column('resolution_due_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False),
    Column('solution', Text, nullable=True),
    Column('resolved_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=True),
    Column('closed_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=True),
    Column('reopen_count', Integer, nullable=False, server_default=text('0')),
    Column('satisfaction_score', SmallInteger, nullable=True),
    Column('created_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp()),
    Column('updated_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp(), onupdate=utc_now, server_onupdate=FetchedValue()),
    Column('row_version', Integer, nullable=False, server_default=text('1')),
    UniqueConstraint('ticket_no', name='uq_ticket_no'),
    Index('idx_ticket_employee_status_due', 'employee_id', 'status', 'resolution_due_at'),
    Index('idx_ticket_student_created', 'student_id', 'created_at'),
    Index('idx_ticket_department_status', 'handling_department_id', 'status'),
    ForeignKeyConstraint(['student_id'], ['student_profile.student_id'], name='fk_service_ticket_student_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(['employee_id'], ['employee.employee_id'], name='fk_service_ticket_employee_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(['handling_department_id'], ['org_department.department_id'], name='fk_service_ticket_handling_department_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    CheckConstraint("ticket_type IN ('complaint','suggestion')", name='ck_svc_ticket_type'),
    CheckConstraint("status IN ('open','assigned','processing','awaiting_student','closed','reopened')", name='ck_svc_ticket_status'),
    CheckConstraint('satisfaction_score IS NULL OR satisfaction_score BETWEEN 1 AND 5', name='ck_ticket_satisfaction'),
    CheckConstraint('reopen_count >= 0', name='ck_ticket_reopen_count'),
    CheckConstraint("status NOT IN ('awaiting_student','closed') OR (solution IS NOT NULL AND LENGTH(TRIM(solution)) > 0)", name='ck_ticket_solution'),
    CheckConstraint('row_version >= 1', name='ck_service_ticket_row_version'),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
)
