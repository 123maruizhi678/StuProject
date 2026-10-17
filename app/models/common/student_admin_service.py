"""按最终建表 SQL 映射；公共表只注册在 Base.metadata，导入不执行建表。"""
from sqlalchemy import (Table, Column, BigInteger, Integer, String, Text, Boolean, DateTime, Date, JSON, Numeric, LargeBinary, UniqueConstraint, CheckConstraint, ForeignKeyConstraint, text)
from sqlalchemy.dialects.mysql import DATETIME, VARCHAR
from app.database import Base
identifier = BigInteger().with_variant(Integer, "sqlite")

student_admin_service = Table("student_admin_service", Base.metadata,
    Column("id", identifier, nullable=False, comment="PK；自增；主键", primary_key=True, autoincrement=True),
    Column("student_id", identifier, nullable=False, comment="统一学生ID"),
    Column("apply_type", String(20), nullable=False, comment="申请类型 leave/academic"),
    Column("apply_content", Text, nullable=False, comment="申请理由/内容"),
    Column("approval_status", String(20), nullable=False, comment="审批状态 pending/approved/rejected/cancelled", server_default=text("'pending'")),
    Column("edu_related_data", JSON, nullable=True, comment="考务关联扩展信息"),
    Column("leave_start_at", DATETIME(fsp=6).with_variant(DateTime(), "sqlite"), nullable=True, comment="请假开始时间（UTC）"),
    Column("leave_end_at", DATETIME(fsp=6).with_variant(DateTime(), "sqlite"), nullable=True, comment="请假结束时间（UTC）"),
    Column("reviewer_id", identifier, nullable=True, comment="目标物理 FK → employee.employee_id；当前指定审批老师，实际审批操作者另存 operation_log.employee_id。"),
    Column("reviewed_at", DATETIME(fsp=6).with_variant(DateTime(), "sqlite"), nullable=True, comment="审批发生时间（UTC）"),
    Column("approval_comment", Text, nullable=True, comment="审批意见/驳回原因"),
    Column("request_key", String(128).with_variant(VARCHAR(128, collation="ascii_bin", charset="ascii"), "mysql"), nullable=False, comment="请求幂等键"),
    Column("request_hash", String(64).with_variant(VARCHAR(64, collation="ascii_bin", charset="ascii"), "mysql"), nullable=False, comment="规范化请求SHA-256"),
    Column("row_version", Integer, nullable=False, comment="乐观锁版本", server_default=text("1")),
    Column("created_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=False, comment="创建时间（UTC）", server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=False, comment="更新时自动刷新；最后更新时间（UTC）", server_default=text("CURRENT_TIMESTAMP")),
    UniqueConstraint("student_id", "request_key", name="uk_admin_request"),
    CheckConstraint("apply_type IN ('leave', 'academic')", name="ck_admin_type"),
    CheckConstraint("approval_status IN ('pending', 'approved', 'rejected', 'cancelled')", name="ck_admin_status"),
    CheckConstraint("apply_type <> 'leave' OR (leave_start_at IS NOT NULL AND leave_end_at IS NOT NULL AND leave_end_at > leave_start_at)", name="ck_admin_leave"),
    CheckConstraint("approval_status NOT IN ('approved', 'rejected') OR (reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL)", name="ck_admin_decision"),
    CheckConstraint("row_version >= 1", name="ck_admin_version"),
    ForeignKeyConstraint(["student_id"], ["student_profile.student_id"], name="fk_joint_19", ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(["reviewer_id"], ["employee.employee_id"], name="fk_joint_20", ondelete="RESTRICT", onupdate="RESTRICT"),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
    comment="学生行政申请；请假提交、撤回、审批及结果的唯一事实源",
)
