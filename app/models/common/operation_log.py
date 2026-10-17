"""operation_log 的唯一共享映射；字段依据 scripts/sql/all.sql，不在启动时建表。"""
from sqlalchemy import CHAR, CheckConstraint, Column, DateTime, FetchedValue, ForeignKeyConstraint, Index, Integer, JSON, String, Table, Text, UniqueConstraint, text
from sqlalchemy.dialects import mysql

from app.database import Base
from ._types import identifier, utc_now, utc_timestamp

operation_log = Table(
    "operation_log", Base.metadata,
    Column('operation_log_id', identifier, primary_key=True, autoincrement=True, nullable=False),
    Column('operation_key', CHAR(64).with_variant(mysql.CHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=False),
    Column('employee_id', identifier, nullable=True),
    Column('student_id', identifier, nullable=True),
    Column('service_code', String(64).with_variant(mysql.VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=True),
    Column('action_code', String(64).with_variant(mysql.VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=False),
    Column('entity_type', String(32).with_variant(mysql.VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False),
    Column('entity_id', identifier, nullable=True),
    Column('request_key', String(128).with_variant(mysql.VARCHAR(128, collation="ascii_bin"), "mysql"), nullable=False),
    Column('parameters_hash', CHAR(64).with_variant(mysql.CHAR(64, collation="ascii_bin"), "mysql"), nullable=False),
    Column('before_data', JSON, nullable=True),
    Column('after_data', JSON, nullable=True),
    Column('change_reason', Text, nullable=True),
    Column('operation_status', String(32).with_variant(mysql.VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, server_default=text("'processing'")),
    Column('result_reference', JSON, nullable=True),
    Column('external_request_id', String(128).with_variant(mysql.VARCHAR(128, collation="utf8mb4_bin"), "mysql"), nullable=True),
    Column('error_code', String(64).with_variant(mysql.VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=True),
    Column('finished_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=True),
    Column('created_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp()),
    Column('updated_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp(), onupdate=utc_now, server_onupdate=FetchedValue()),
    Column('row_version', Integer, nullable=False, server_default=text('1')),
    UniqueConstraint('operation_key', name='uq_operation_key'),
    Index('idx_operation_entity_time', 'entity_type', 'entity_id', 'created_at'),
    Index('idx_operation_employee_time', 'employee_id', 'created_at'),
    Index('idx_operation_student_time', 'student_id', 'created_at'),
    Index('idx_operation_status_time', 'operation_status', 'created_at'),
    ForeignKeyConstraint(['employee_id'], ['employee.employee_id'], name='fk_operation_log_employee_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(['student_id'], ['student_profile.student_id'], name='fk_operation_log_student_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    CheckConstraint('((employee_id IS NOT NULL) + (student_id IS NOT NULL) + (service_code IS NOT NULL)) = 1', name='ck_operation_actor'),
    CheckConstraint('service_code IS NULL OR LENGTH(TRIM(service_code)) > 0', name='ck_operation_service'),
    CheckConstraint("operation_status IN ('processing','succeeded','failed','pending_external','unknown_external')", name='ck_operation_status'),
    CheckConstraint('row_version >= 1', name='ck_operation_log_row_version'),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
)
