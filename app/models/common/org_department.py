"""org_department 的唯一共享映射；字段依据 scripts/sql/all.sql，不在启动时建表。"""
from sqlalchemy import CheckConstraint, Column, DateTime, FetchedValue, ForeignKeyConstraint, Index, Integer, String, Table, Text, UniqueConstraint, text
from sqlalchemy.dialects import mysql

from app.database import Base
from ._types import identifier, utc_now, utc_timestamp

org_department = Table(
    "org_department", Base.metadata,
    Column('department_id', identifier, primary_key=True, autoincrement=True, nullable=False),
    Column('department_code', String(32).with_variant(mysql.VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False),
    Column('department_name', String(100), nullable=False),
    Column('parent_department_id', identifier, nullable=True),
    Column('function_description', Text, nullable=True),
    Column('employee_id', identifier, nullable=True),
    Column('status', String(32).with_variant(mysql.VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, server_default=text("'active'")),
    Column('created_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp()),
    Column('updated_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp(), onupdate=utc_now, server_onupdate=FetchedValue()),
    Column('row_version', Integer, nullable=False, server_default=text('1')),
    UniqueConstraint('department_code', name='uq_department_code'),
    Index('idx_department_parent', 'parent_department_id'),
    Index('idx_department_manager', 'employee_id'),
    ForeignKeyConstraint(['parent_department_id'], ['org_department.department_id'], name='fk_org_department_parent_department_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    CheckConstraint("status IN ('active','disabled')", name='ck_department_status'),
    CheckConstraint('row_version >= 1', name='ck_org_department_row_version'),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
)
