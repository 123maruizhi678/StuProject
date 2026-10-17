"""按最终建表 SQL 映射；公共表只注册在 Base.metadata，导入不执行建表。"""
from sqlalchemy import (Table, Column, BigInteger, Integer, String, Text, Boolean, DateTime, Date, JSON, Numeric, LargeBinary, UniqueConstraint, CheckConstraint, ForeignKeyConstraint, text)
from sqlalchemy.dialects.mysql import DATETIME, VARCHAR
from app.database import Base
identifier = BigInteger().with_variant(Integer, "sqlite")

user_account = Table("user_account", Base.metadata,
    Column("user_id", identifier, nullable=False, comment="PK；自增；统一用户主键 ID。", primary_key=True, autoincrement=True),
    Column("username", String(64).with_variant(VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="登录用户名，唯一。"),
    Column("password_hash", String(255).with_variant(VARCHAR(255, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="密码哈希，不得存储明文密码。"),
    Column("identity_type", String(20).with_variant(VARCHAR(20, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="统一登录身份：admin平台管理员、employee员工、customer客户、student学生；与身份关联外键保持一致"),
    Column("employee_id", identifier, nullable=True, comment="对应员工表 employee.employee_id；非员工身份时为空。"),
    Column("customer_id", identifier, nullable=True, comment="对应客户表 customer_profile.customer_id；非客户身份时为空。"),
    Column("student_id", identifier, nullable=True, comment="对应学生表 student_profile.student_id；非学生身份时为空。"),
    Column("created_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=False, comment="用户记录创建时间（UTC）。", server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=False, comment="更新时自动刷新；用户记录最近更新时间（UTC）。", server_default=text("CURRENT_TIMESTAMP")),
    UniqueConstraint("username", name="uq_user_username"),
    UniqueConstraint("employee_id", name="uq_user_employee"),
    UniqueConstraint("customer_id", name="uq_user_customer"),
    UniqueConstraint("student_id", name="uq_user_student"),
    CheckConstraint("(identity_type = 'admin' AND employee_id IS NULL AND customer_id IS NULL AND student_id IS NULL) OR (identity_type = 'employee' AND employee_id IS NOT NULL AND customer_id IS NULL AND student_id IS NULL) OR (identity_type = 'customer' AND employee_id IS NULL AND customer_id IS NOT NULL AND student_id IS NULL) OR (identity_type = 'student' AND employee_id IS NULL AND customer_id IS NULL AND student_id IS NOT NULL)", name="ck_user_identity_link"),
    ForeignKeyConstraint(["employee_id"], ["employee.employee_id"], name="fk_joint_01", ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(["customer_id"], ["customer_profile.customer_id"], name="fk_joint_02", ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(["student_id"], ["student_profile.student_id"], name="fk_joint_03", ondelete="RESTRICT", onupdate="RESTRICT"),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
    comment="统一登录账号、身份及业务主键映射",
)

class UserAccount(Base):
    __table__=user_account
