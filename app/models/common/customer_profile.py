"""customer_profile 的唯一共享映射；字段依据 scripts/sql/all.sql，不在启动时建表。"""
from sqlalchemy import Boolean, CHAR, CheckConstraint, Column, DateTime, FetchedValue, ForeignKeyConstraint, Index, Integer, LargeBinary, String, Table, Text, UniqueConstraint, text
from sqlalchemy.dialects import mysql

from app.database import Base
from ._types import identifier, utc_now, utc_timestamp

customer_profile = Table(
    "customer_profile", Base.metadata,
    Column('customer_id', identifier, primary_key=True, autoincrement=True, nullable=False),
    Column('customer_no', String(32), nullable=False),
    Column('full_name', String(100), nullable=False),
    Column('phone_ciphertext', LargeBinary(512).with_variant(mysql.VARBINARY(512), "mysql"), nullable=True),
    Column('phone_lookup_token', CHAR(64).with_variant(mysql.CHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=True),
    Column('education_level', String(32), nullable=True),
    Column('target_country_code', String(8).with_variant(mysql.VARCHAR(8, collation="utf8mb4_bin"), "mysql"), nullable=True),
    Column('source_channel', String(32), nullable=False),
    Column('source_reference', String(128), nullable=True),
    Column('employee_id', identifier, nullable=True),
    Column('department_id', identifier, nullable=False),
    Column('status', String(32).with_variant(mysql.VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, server_default=text("'new'")),
    Column('status_changed_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp()),
    Column('lost_reason', Text, nullable=True),
    Column('last_followup_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=True),
    Column('authority_source', String(20), nullable=False, server_default=text("'local'")),
    Column('external_customer_id', String(128).with_variant(mysql.VARCHAR(128, collation="utf8mb4_bin"), "mysql"), nullable=True),
    Column('external_updated_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=True),
    Column('is_archived', Boolean, nullable=False, server_default=text('0')),
    Column('created_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp()),
    Column('updated_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp(), onupdate=utc_now, server_onupdate=FetchedValue()),
    Column('row_version', Integer, nullable=False, server_default=text('1')),
    UniqueConstraint('customer_no', name='uq_customer_no'),
    UniqueConstraint('external_customer_id', name='uq_customer_external'),
    Index('idx_customer_employee_status', 'employee_id', 'status'),
    Index('idx_customer_department_status', 'department_id', 'status'),
    Index('idx_customer_phone_token', 'phone_lookup_token'),
    ForeignKeyConstraint(['employee_id'], ['employee.employee_id'], name='fk_customer_profile_employee_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(['department_id'], ['org_department.department_id'], name='fk_customer_profile_department_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    CheckConstraint("status IN ('new','contacting','qualified','signed','lost')", name='ck_customer_status'),
    CheckConstraint("authority_source IN ('local','crm')", name='ck_customer_authority'),
    CheckConstraint("status <> 'lost' OR (lost_reason IS NOT NULL AND LENGTH(TRIM(lost_reason)) > 0)", name='ck_customer_lost_reason'),
    CheckConstraint('is_archived IN (0,1)', name='ck_customer_archived'),
    CheckConstraint('row_version >= 1', name='ck_customer_profile_row_version'),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
)
