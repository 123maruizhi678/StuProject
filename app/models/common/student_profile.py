"""student_profile 的唯一共享映射；字段依据 scripts/sql/all.sql，不在启动时建表。"""
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, FetchedValue, ForeignKeyConstraint, Index, Integer, LargeBinary, String, Table, UniqueConstraint, text
from sqlalchemy.dialects import mysql

from app.database import Base
from ._types import identifier, utc_now, utc_timestamp

student_profile = Table(
    "student_profile", Base.metadata,
    Column('student_id', identifier, primary_key=True, autoincrement=True, nullable=False),
    Column('student_no', String(32), nullable=False),
    Column('full_name', String(100), nullable=False),
    Column('phone_ciphertext', LargeBinary(512).with_variant(mysql.VARBINARY(512), "mysql"), nullable=True),
    Column('customer_id', identifier, nullable=True),
    Column('department_id', identifier, nullable=False),
    Column('login_provider', String(32).with_variant(mysql.VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=True),
    Column('login_subject', String(128).with_variant(mysql.VARCHAR(128, collation="utf8mb4_bin"), "mysql"), nullable=True),
    Column('status', String(32).with_variant(mysql.VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False),
    Column('external_student_id', String(128).with_variant(mysql.VARCHAR(128, collation="utf8mb4_bin"), "mysql"), nullable=True),
    Column('is_archived', Boolean, nullable=False, server_default=text('0')),
    Column('created_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp()),
    Column('updated_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp(), onupdate=utc_now, server_onupdate=FetchedValue()),
    Column('row_version', Integer, nullable=False, server_default=text('1')),
    UniqueConstraint('student_no', name='uq_student_no'),
    UniqueConstraint('login_provider', 'login_subject', name='uq_student_login'),
    UniqueConstraint('external_student_id', name='uq_student_external'),
    Index('idx_student_department_status', 'department_id', 'status'),
    Index('idx_student_customer', 'customer_id'),
    ForeignKeyConstraint(['customer_id'], ['customer_profile.customer_id'], name='fk_student_profile_customer_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(['department_id'], ['org_department.department_id'], name='fk_student_profile_department_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    CheckConstraint('(login_provider IS NULL AND login_subject IS NULL) OR (login_provider IS NOT NULL AND login_subject IS NOT NULL)', name='ck_student_login_pair'),
    CheckConstraint('is_archived IN (0,1)', name='ck_student_archived'),
    CheckConstraint('row_version >= 1', name='ck_student_profile_row_version'),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
)
