"""学生行政申请；请假提交、撤回、审批及结果的唯一事实源；公共唯一映射，复用 Base.metadata。"""
from sqlalchemy import (
    BigInteger, CHAR, CheckConstraint, Column, DateTime, FetchedValue, ForeignKey, Index, Integer, JSON, String, Table, Text, UniqueConstraint, func, text
)
from sqlalchemy.dialects.mysql import CHAR as MYSQL_CHAR, DATETIME, VARCHAR

from app.database import Base


student_admin_service = Table(
    'student_admin_service', Base.metadata,
    Column('id', BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True, nullable=False, comment='PK；自增；主键'),
    Column('student_id', BigInteger().with_variant(Integer(), "sqlite"), ForeignKey('student_profile.student_id', name='fk_joint_19', ondelete='RESTRICT', onupdate='RESTRICT'), nullable=False, comment='统一学生ID'),
    Column('apply_type', String(20), nullable=False, comment='申请类型 leave/academic'),
    Column('apply_content', Text, nullable=False, comment='申请理由/内容'),
    Column('approval_status', String(20), nullable=False, server_default=text("'pending'"), comment='审批状态 pending/approved/rejected/cancelled'),
    Column('edu_related_data', JSON, nullable=True, comment='考务关联扩展信息'),
    Column('leave_start_at', DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=True, comment='请假开始时间（UTC）'),
    Column('leave_end_at', DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=True, comment='请假结束时间（UTC）'),
    Column('reviewer_id', BigInteger().with_variant(Integer(), "sqlite"), ForeignKey('employee.employee_id', name='fk_joint_20', ondelete='RESTRICT', onupdate='RESTRICT'), nullable=True, comment='目标物理 FK → employee.employee_id；当前指定审批老师，实际审批操作者另存 operation_log.employee_id。'),
    Column('reviewed_at', DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=True, comment='审批发生时间（UTC）'),
    Column('approval_comment', Text, nullable=True, comment='审批意见/驳回原因'),
    Column('request_key', String(128).with_variant(VARCHAR(128, collation="ascii_bin", charset="ascii"), "mysql"), nullable=False, comment='请求幂等键'),
    Column('request_hash', CHAR(64).with_variant(MYSQL_CHAR(64, collation="ascii_bin", charset="ascii"), "mysql"), nullable=False, comment='规范化请求SHA-256'),
    Column('row_version', Integer, nullable=False, server_default=text('1'), comment='乐观锁版本'),
    Column('created_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), comment='创建时间（UTC）'),
    Column('updated_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), server_onupdate=FetchedValue(), comment='更新时自动刷新；最后更新时间（UTC）'),
    UniqueConstraint('student_id', 'request_key', name='uk_admin_request'),
    Index('idx_admin_student', 'student_id', 'created_at'),
    Index('idx_admin_review', 'reviewer_id', 'approval_status', 'created_at'),
    CheckConstraint("apply_type IN ('leave', 'academic')", name='ck_admin_type'),
    CheckConstraint("approval_status IN ('pending', 'approved', 'rejected', 'cancelled')", name='ck_admin_status'),
    CheckConstraint("apply_type <> 'leave' OR (leave_start_at IS NOT NULL AND leave_end_at IS NOT NULL AND leave_end_at > leave_start_at)", name='ck_admin_leave'),
    CheckConstraint("approval_status NOT IN ('approved', 'rejected') OR (reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL)", name='ck_admin_decision'),
    CheckConstraint('row_version >= 1', name='ck_admin_version'),
    comment='学生行政申请；请假提交、撤回、审批及结果的唯一事实源',
    mysql_engine="InnoDB",
    mysql_charset="utf8mb4",
    mysql_collate="utf8mb4_0900_ai_ci",
)
