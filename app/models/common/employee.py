"""employee 的唯一共享映射；字段依据 scripts/sql/all.sql，不在启动时建表。"""
from sqlalchemy import CheckConstraint, Column, Date, DateTime, FetchedValue, ForeignKeyConstraint, Index, Integer, JSON, LargeBinary, String, Table, UniqueConstraint, text
from sqlalchemy.dialects import mysql

from app.database import Base
from ._types import identifier, utc_now, utc_timestamp

employee = Table(
    "employee", Base.metadata,
    Column('employee_id', identifier, primary_key=True, autoincrement=True, nullable=False),
    Column('employee_no', String(32), nullable=False),
    Column('full_name', String(100), nullable=False),
    Column('department_id', identifier, nullable=False),
    Column('position_title', String(100), nullable=True),
    Column('login_provider', String(32).with_variant(mysql.VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False),
    Column('login_subject', String(128).with_variant(mysql.VARCHAR(128, collation="utf8mb4_bin"), "mysql"), nullable=False),
    Column('role_codes', JSON, nullable=False),
    Column('work_phone_ciphertext', LargeBinary(512).with_variant(mysql.VARBINARY(512), "mysql"), nullable=True),
    Column('work_email', String(254), nullable=True),
    Column('status', String(32).with_variant(mysql.VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, server_default=text("'active'")),
    Column('joined_date', Date, nullable=False),
    Column('left_date', Date, nullable=True),
    Column('external_employee_id', String(128).with_variant(mysql.VARCHAR(128, collation="utf8mb4_bin"), "mysql"), nullable=True),
    Column('created_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp()),
    Column('updated_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp(), onupdate=utc_now, server_onupdate=FetchedValue()),
    Column('row_version', Integer, nullable=False, server_default=text('1')),
    UniqueConstraint('employee_no', name='uq_employee_no'),
    UniqueConstraint('login_provider', 'login_subject', name='uq_employee_login'),
    UniqueConstraint('external_employee_id', name='uq_employee_external'),
    Index('idx_employee_department_status', 'department_id', 'status'),
    ForeignKeyConstraint(['department_id'], ['org_department.department_id'], name='fk_employee_department_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    CheckConstraint("status IN ('active','disabled','left')", name='ck_employee_status'),
    CheckConstraint("JSON_TYPE(role_codes) = 'ARRAY' AND JSON_LENGTH(role_codes) > 0", name='ck_employee_roles').ddl_if(dialect="mysql"),
    CheckConstraint('left_date IS NULL OR left_date >= joined_date', name='ck_employee_dates'),
    CheckConstraint('row_version >= 1', name='ck_employee_row_version'),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
)
