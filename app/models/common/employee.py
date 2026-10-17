"""按最终建表 SQL 映射；公共表只注册在 Base.metadata，导入不执行建表。"""
from sqlalchemy import (Table, Column, BigInteger, Integer, String, Text, Boolean, DateTime, Date, JSON, Numeric, LargeBinary, UniqueConstraint, CheckConstraint, ForeignKeyConstraint, text)
from sqlalchemy.dialects.mysql import DATETIME, VARCHAR
from app.database import Base
identifier = BigInteger().with_variant(Integer, "sqlite")

employee = Table("employee", Base.metadata,
    Column("employee_id", identifier, nullable=False, comment="PK；自增；员工主键 ID，是所有员工业务关联的内部标识，不使用工号代替。 主键（PK）。", primary_key=True, autoincrement=True),
    Column("employee_no", String(32), nullable=False, comment="员工唯一工号。"),
    Column("full_name", String(100), nullable=False, comment="员工姓名，允许重名。"),
    Column("department_id", identifier, nullable=False, comment="当前主部门 ID，关联 org_department。 外键（FK）关联 org_department.department_id。"),
    Column("position_title", String(100), nullable=True, comment="员工岗位或职务名称。"),
    Column("login_provider", String(32).with_variant(VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="登录来源，如企业统一登录。"),
    Column("login_subject", String(128).with_variant(VARCHAR(128, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="登录来源提供的不可变账号标识。"),
    Column("role_codes", JSON, nullable=False, comment="受控角色代码数组；权限由后端固定配置解释。"),
    Column("work_phone_ciphertext", LargeBinary(512), nullable=True, comment="加密保存的工作联系电话。"),
    Column("work_email", String(254), nullable=True, comment="工作邮箱。"),
    Column("status", String(32).with_variant(VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="员工状态：active 启用、disabled 停用、left 离职。", server_default=text("'active'")),
    Column("joined_date", Date, nullable=False, comment="入职日期。"),
    Column("left_date", Date, nullable=True, comment="离职日期，未离职时为空。"),
    Column("external_employee_id", String(128).with_variant(VARCHAR(128, collation="utf8mb4_bin"), "mysql"), nullable=True, comment="权威通讯录中的员工 ID。"),
    Column("created_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=False, comment="记录创建时间，UTC；连接必须设置 time_zone 为 +00:00", server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=False, comment="更新时自动刷新；记录最近更新时间，UTC", server_default=text("CURRENT_TIMESTAMP")),
    Column("row_version", Integer, nullable=False, comment="并发版本号；每次业务修改由后端递增", server_default=text("1")),
    UniqueConstraint("employee_no", name="uq_employee_no"),
    UniqueConstraint("login_provider", "login_subject", name="uq_employee_login"),
    UniqueConstraint("external_employee_id", name="uq_employee_external"),
    CheckConstraint("status IN ('active','disabled','left')", name="ck_employee_status"),
    CheckConstraint("JSON_TYPE(role_codes) = 'ARRAY' AND JSON_LENGTH(role_codes) > 0", name="ck_employee_roles"),
    CheckConstraint("left_date IS NULL OR left_date >= joined_date", name="ck_employee_dates"),
    CheckConstraint("row_version >= 1", name="ck_employee_row_version"),
    ForeignKeyConstraint(["department_id"], ["org_department.department_id"], name="fk_joint_06", ondelete="RESTRICT", onupdate="RESTRICT"),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
    comment="员工资料、部门、业务角色及有效状态",
)
