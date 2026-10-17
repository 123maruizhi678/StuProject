"""按最终建表 SQL 映射；公共表只注册在 Base.metadata，导入不执行建表。"""
from sqlalchemy import (Table, Column, BigInteger, Integer, String, Text, Boolean, DateTime, Date, JSON, Numeric, LargeBinary, UniqueConstraint, CheckConstraint, ForeignKeyConstraint, text)
from sqlalchemy.dialects.mysql import DATETIME, VARCHAR
from app.database import Base
identifier = BigInteger().with_variant(Integer, "sqlite")

student_profile = Table("student_profile", Base.metadata,
    Column("student_id", identifier, nullable=False, comment="PK；自增；学生主键 ID，是成绩、请假、投诉及学生员工关系使用的内部标识。 主键（PK）。", primary_key=True, autoincrement=True),
    Column("student_no", String(32), nullable=False, comment="学生唯一业务编号。"),
    Column("full_name", String(100), nullable=False, comment="学生姓名，允许重名。"),
    Column("phone_ciphertext", LargeBinary(512), nullable=True, comment="加密保存的学生手机号。"),
    Column("customer_id", identifier, nullable=True, comment="关联客户 ID，不自动授予客户账号访问学生数据的权限。 外键（FK）关联 customer_profile.customer_id。"),
    Column("department_id", identifier, nullable=False, comment="学生教务或服务归属部门 ID。 外键（FK）关联 org_department.department_id。"),
    Column("login_provider", String(32).with_variant(VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=True, comment="学生登录来源，尚未开通账号时为空。"),
    Column("login_subject", String(128).with_variant(VARCHAR(128, collation="utf8mb4_bin"), "mysql"), nullable=True, comment="学生登录身份键，与登录来源同时填写。"),
    Column("status", String(32).with_variant(VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="学生服务或在读状态。"),
    Column("external_student_id", String(128).with_variant(VARCHAR(128, collation="utf8mb4_bin"), "mysql"), nullable=True, comment="教务系统中的学生 ID。"),
    Column("crm_student_id", String(128), nullable=True, comment="CRM 学生独立标识；目标为非空值唯一，类型与学生文档一致；由后续统一迁移核对补齐。"),
    Column("is_archived", Boolean, nullable=False, comment="是否已归档，默认 false；归档不删除已有成绩、请假和投诉关联。", server_default=text("0")),
    Column("created_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=False, comment="记录创建时间，UTC；连接必须设置 time_zone 为 +00:00", server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=False, comment="更新时自动刷新；记录最近更新时间，UTC", server_default=text("CURRENT_TIMESTAMP")),
    Column("row_version", Integer, nullable=False, comment="并发版本号；每次业务修改由后端递增", server_default=text("1")),
    UniqueConstraint("student_no", name="uq_student_no"),
    UniqueConstraint("login_provider", "login_subject", name="uq_student_login"),
    UniqueConstraint("external_student_id", name="uq_student_external"),
    CheckConstraint("(login_provider IS NULL AND login_subject IS NULL) OR (login_provider IS NOT NULL AND login_subject IS NOT NULL)", name="ck_student_login_pair"),
    CheckConstraint("is_archived IN (0,1)", name="ck_student_archived"),
    CheckConstraint("row_version >= 1", name="ck_student_profile_row_version"),
    UniqueConstraint("crm_student_id", name="uq_student_crm"),
    ForeignKeyConstraint(["customer_id"], ["customer_profile.customer_id"], name="fk_joint_13", ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(["department_id"], ["org_department.department_id"], name="fk_joint_14", ondelete="RESTRICT", onupdate="RESTRICT"),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
    comment="学生唯一主档及业务关联",
)
