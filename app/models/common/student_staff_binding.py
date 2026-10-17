"""student_staff_binding 的唯一共享映射；字段依据 scripts/sql/all.sql，不在启动时建表。"""
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, FetchedValue, ForeignKeyConstraint, Index, Integer, String, Table, text
from sqlalchemy.dialects import mysql

from app.database import Base
from ._types import identifier, utc_now, utc_timestamp

student_staff_binding = Table(
    "student_staff_binding", Base.metadata,
    Column('binding_id', identifier, primary_key=True, autoincrement=True, nullable=False),
    Column('student_id', identifier, nullable=False),
    Column('employee_id', identifier, nullable=False),
    Column('relation_type', String(32).with_variant(mysql.VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False),
    Column('course_scope_code', String(64).with_variant(mysql.VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=True),
    Column('is_primary', Boolean, nullable=False, server_default=text('0')),
    Column('valid_from', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp()),
    Column('valid_to', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=True),
    Column('status', String(32).with_variant(mysql.VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, server_default=text("'active'")),
    Column('created_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp()),
    Column('updated_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp(), onupdate=utc_now, server_onupdate=FetchedValue()),
    Column('row_version', Integer, nullable=False, server_default=text('1')),
    Index('idx_binding_employee_type_status', 'employee_id', 'relation_type', 'status'),
    Index('idx_binding_student_type_status', 'student_id', 'relation_type', 'status'),
    ForeignKeyConstraint(['student_id'], ['student_profile.student_id'], name='fk_student_staff_binding_student_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(['employee_id'], ['employee.employee_id'], name='fk_student_staff_binding_employee_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    CheckConstraint("relation_type IN ('class_teacher','score_editor','service_advisor')", name='ck_binding_type'),
    CheckConstraint("status IN ('active','disabled')", name='ck_binding_status'),
    CheckConstraint('valid_to IS NULL OR valid_to > valid_from', name='ck_binding_dates'),
    CheckConstraint('is_primary IN (0,1)', name='ck_binding_primary'),
    CheckConstraint('row_version >= 1', name='ck_student_staff_binding_row_version'),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
)
