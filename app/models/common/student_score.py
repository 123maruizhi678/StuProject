"""student_score 的唯一共享映射；字段依据 scripts/sql/all.sql，不在启动时建表。"""
from sqlalchemy import CheckConstraint, Column, DateTime, FetchedValue, ForeignKeyConstraint, Index, Integer, Numeric, String, Table, UniqueConstraint, text
from sqlalchemy.dialects import mysql

from app.database import Base
from ._types import identifier, utc_now, utc_timestamp

student_score = Table(
    "student_score", Base.metadata,
    Column('score_id', identifier, primary_key=True, autoincrement=True, nullable=False),
    Column('student_id', identifier, nullable=False),
    Column('course_code', String(64).with_variant(mysql.VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=False),
    Column('term_code', String(32).with_variant(mysql.VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False),
    Column('assessment_code', String(64).with_variant(mysql.VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=False),
    Column('attempt_no', Integer, nullable=False, server_default=text('1')),
    Column('score_value', Numeric(8,2), nullable=False),
    Column('max_score', Numeric(8,2), nullable=False),
    Column('employee_id', identifier, nullable=False),
    Column('status', String(32).with_variant(mysql.VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, server_default=text("'valid'")),
    Column('created_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp()),
    Column('updated_at', DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp(), onupdate=utc_now, server_onupdate=FetchedValue()),
    Column('row_version', Integer, nullable=False, server_default=text('1')),
    UniqueConstraint('student_id', 'course_code', 'term_code', 'assessment_code', 'attempt_no', name='uq_score_assessment_attempt'),
    Index('idx_score_student_term', 'student_id', 'term_code'),
    Index('idx_score_employee', 'employee_id'),
    ForeignKeyConstraint(['student_id'], ['student_profile.student_id'], name='fk_student_score_student_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(['employee_id'], ['employee.employee_id'], name='fk_student_score_employee_id', ondelete="RESTRICT", onupdate="RESTRICT"),
    CheckConstraint('max_score > 0 AND score_value >= 0 AND score_value <= max_score', name='ck_score_range'),
    CheckConstraint('attempt_no >= 1', name='ck_score_attempt'),
    CheckConstraint("status IN ('valid','void')", name='ck_score_status'),
    CheckConstraint('row_version >= 1', name='ck_student_score_row_version'),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
)
