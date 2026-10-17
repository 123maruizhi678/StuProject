"""学生行政申请；请假提交、撤回、审批及结果的唯一事实源；复用唯一Base.metadata，建表由独立SQL负责。"""
from datetime import datetime
from sqlalchemy import Table, Column, BigInteger, Integer, String, Text, DateTime, Date, Boolean, JSON, Numeric, LargeBinary, UniqueConstraint, text
from app.database import Base

student_admin_service = Table('student_admin_service', Base.metadata,
    Column('id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='PK；自增；主键', primary_key=True, autoincrement=True),
    Column('student_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='统一学生ID'),
    Column('apply_type', String(20), nullable=False, comment='申请类型 leave/academic'),
    Column('apply_content', Text(), nullable=False, comment='申请理由/内容'),
    Column('approval_status', String(20), nullable=False, comment='审批状态 pending/approved/rejected/cancelled', server_default=text("'pending'")),
    Column('edu_related_data', JSON(), nullable=True, comment='考务关联扩展信息'),
    Column('leave_start_at', DateTime(), nullable=True, comment='请假开始时间（UTC）'),
    Column('leave_end_at', DateTime(), nullable=True, comment='请假结束时间（UTC）'),
    Column('reviewer_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=True, comment='目标物理 FK → employee.employee_id；当前指定审批老师，实际审批操作者另存 operation_log.employee_id。'),
    Column('reviewed_at', DateTime(), nullable=True, comment='审批发生时间（UTC）'),
    Column('approval_comment', Text(), nullable=True, comment='审批意见/驳回原因'),
    Column('request_key', String(128), nullable=False, comment='请求幂等键'),
    Column('request_hash', String(64), nullable=False, comment='规范化请求SHA-256'),
    Column('row_version', Integer(), nullable=False, comment='乐观锁版本', server_default=text("'1'")),
    Column('created_at', DateTime(), nullable=False, comment='创建时间（UTC）', default=datetime.utcnow),
    Column('updated_at', DateTime(), nullable=False, comment='更新时自动刷新；最后更新时间（UTC）', default=datetime.utcnow),
    UniqueConstraint('student_id', 'request_key', name='uk_admin_request'),
    comment='学生行政申请；请假提交、撤回、审批及结果的唯一事实源',
)
