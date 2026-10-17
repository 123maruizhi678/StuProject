"""学生成绩及当前有效状态；公共唯一映射，复用 Base.metadata。"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, DateTime, FetchedValue, ForeignKey, Index, Integer, Numeric, String, Table, UniqueConstraint, func, text
)
from sqlalchemy.dialects.mysql import DATETIME, VARCHAR

from app.database import Base


student_score = Table(
    'student_score', Base.metadata,
    Column('score_id', BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True, nullable=False, comment='PK；自增；学生成绩记录主键 ID。 主键（PK）。'),
    Column('student_id', BigInteger().with_variant(Integer(), "sqlite"), ForeignKey('student_profile.student_id', name='fk_joint_17', ondelete='RESTRICT', onupdate='RESTRICT'), nullable=False, comment='成绩所属学生 ID。 外键（FK）关联 student_profile.student_id。'),
    Column('course_code', String(64).with_variant(VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=False, comment='受控课程编码。'),
    Column('term_code', String(32).with_variant(VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, comment='学期编码。'),
    Column('assessment_code', String(64).with_variant(VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=False, comment='考试、作业或其他考核项目编码。'),
    Column('attempt_no', Integer, nullable=False, server_default=text('1'), comment='考核尝试次数，首次为 1，补考递增。'),
    Column('score_value', Numeric(8,2), nullable=False, comment='学生实际得分，统一采用数值制，必须填写。'),
    Column('max_score', Numeric(8,2), nullable=False, comment='本次考核满分，必须填写且大于零。'),
    Column('employee_id', BigInteger().with_variant(Integer(), "sqlite"), ForeignKey('employee.employee_id', name='fk_joint_18', ondelete='RESTRICT', onupdate='RESTRICT'), nullable=False, comment='最近录入或更正成绩的员工 ID。 外键（FK）关联 employee.employee_id。'),
    Column('status', String(32).with_variant(VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, server_default=text("'valid'"), comment='成绩状态：valid 有效、void 作废。'),
    Column('created_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00'),
    Column('updated_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), server_onupdate=FetchedValue(), comment='更新时自动刷新；记录最近更新时间，UTC'),
    Column('row_version', Integer, nullable=False, server_default=text('1'), comment='并发版本号；每次业务修改由后端递增'),
    UniqueConstraint('student_id', 'course_code', 'term_code', 'assessment_code', 'attempt_no', name='uq_score_assessment_attempt'),
    Index('idx_score_student_term', 'student_id', 'term_code'),
    Index('idx_score_employee', 'employee_id'),
    CheckConstraint('max_score > 0 AND score_value >= 0 AND score_value <= max_score', name='ck_score_range'),
    CheckConstraint('attempt_no >= 1', name='ck_score_attempt'),
    CheckConstraint("status IN ('valid','void')", name='ck_score_status'),
    CheckConstraint('row_version >= 1', name='ck_student_score_row_version'),
    comment='学生成绩及当前有效状态',
    mysql_engine="InnoDB",
    mysql_charset="utf8mb4",
    mysql_collate="utf8mb4_0900_ai_ci",
)
