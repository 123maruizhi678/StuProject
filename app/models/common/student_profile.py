"""学生唯一主档及业务关联；复用唯一Base.metadata，建表由独立SQL负责。"""
from datetime import datetime
from sqlalchemy import Table, Column, BigInteger, Integer, String, Text, DateTime, Date, Boolean, JSON, Numeric, LargeBinary, UniqueConstraint, text
from app.database import Base

student_profile = Table('student_profile', Base.metadata,
    Column('student_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='PK；自增；学生主键 ID，是成绩、请假、投诉及学生员工关系使用的内部标识。 主键（PK）。', primary_key=True, autoincrement=True),
    Column('student_no', String(32), nullable=False, comment='学生唯一业务编号。'),
    Column('full_name', String(100), nullable=False, comment='学生姓名，允许重名。'),
    Column('phone_ciphertext', LargeBinary(512), nullable=True, comment='加密保存的学生手机号。'),
    Column('customer_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=True, comment='关联客户 ID，不自动授予客户账号访问学生数据的权限。 外键（FK）关联 customer_profile.customer_id。'),
    Column('department_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='学生教务或服务归属部门 ID。 外键（FK）关联 org_department.department_id。'),
    Column('login_provider', String(32), nullable=True, comment='学生登录来源，尚未开通账号时为空。'),
    Column('login_subject', String(128), nullable=True, comment='学生登录身份键，与登录来源同时填写。'),
    Column('status', String(32), nullable=False, comment='学生服务或在读状态。'),
    Column('external_student_id', String(128), nullable=True, comment='教务系统中的学生 ID。'),
    Column('crm_student_id', String(128), nullable=True, comment='CRM 学生独立标识；目标为非空值唯一，类型与学生文档一致；由后续统一迁移核对补齐。'),
    Column('is_archived', Integer(), nullable=False, comment='是否已归档，默认 false；归档不删除已有成绩、请假和投诉关联。', server_default=text("'0'")),
    Column('created_at', DateTime(), nullable=False, comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00', default=datetime.utcnow),
    Column('updated_at', DateTime(), nullable=False, comment='更新时自动刷新；记录最近更新时间，UTC', default=datetime.utcnow),
    Column('row_version', Integer(), nullable=False, comment='并发版本号；每次业务修改由后端递增', server_default=text("'1'")),
    UniqueConstraint('crm_student_id', name='uq_student_crm'),
    UniqueConstraint('external_student_id', name='uq_student_external'),
    UniqueConstraint('login_provider', 'login_subject', name='uq_student_login'),
    UniqueConstraint('student_no', name='uq_student_no'),
    comment='学生唯一主档及业务关联',
)
