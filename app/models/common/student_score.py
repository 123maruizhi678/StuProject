"""学生成绩及当前有效状态；复用唯一Base.metadata，建表由独立SQL负责。"""
from datetime import datetime
from sqlalchemy import Table, Column, BigInteger, Integer, String, Text, DateTime, Date, Boolean, JSON, Numeric, LargeBinary, UniqueConstraint, text
from app.database import Base

student_score = Table('student_score', Base.metadata,
    Column('score_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='PK；自增；学生成绩记录主键 ID。 主键（PK）。', primary_key=True, autoincrement=True),
    Column('student_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='成绩所属学生 ID。 外键（FK）关联 student_profile.student_id。'),
    Column('course_code', String(64), nullable=False, comment='受控课程编码。'),
    Column('term_code', String(32), nullable=False, comment='学期编码。'),
    Column('assessment_code', String(64), nullable=False, comment='考试、作业或其他考核项目编码。'),
    Column('attempt_no', Integer(), nullable=False, comment='考核尝试次数，首次为 1，补考递增。', server_default=text("'1'")),
    Column('score_value', Numeric(8, 2), nullable=False, comment='学生实际得分，统一采用数值制，必须填写。'),
    Column('max_score', Numeric(8, 2), nullable=False, comment='本次考核满分，必须填写且大于零。'),
    Column('employee_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='最近录入或更正成绩的员工 ID。 外键（FK）关联 employee.employee_id。'),
    Column('status', String(32), nullable=False, comment='成绩状态：valid 有效、void 作废。', server_default=text("'valid'")),
    Column('created_at', DateTime(), nullable=False, comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00', default=datetime.utcnow),
    Column('updated_at', DateTime(), nullable=False, comment='更新时自动刷新；记录最近更新时间，UTC', default=datetime.utcnow),
    Column('row_version', Integer(), nullable=False, comment='并发版本号；每次业务修改由后端递增', server_default=text("'1'")),
    UniqueConstraint('student_id', 'course_code', 'term_code', 'assessment_code', 'attempt_no', name='uq_score_assessment_attempt'),
    comment='学生成绩及当前有效状态',
)
