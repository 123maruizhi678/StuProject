"""按最终建表 SQL 映射；公共表只注册在 Base.metadata，导入不执行建表。"""
from sqlalchemy import (Table, Column, BigInteger, Integer, String, Text, Boolean, DateTime, Date, JSON, Numeric, LargeBinary, UniqueConstraint, CheckConstraint, ForeignKeyConstraint, text)
from sqlalchemy.dialects.mysql import DATETIME, VARCHAR
from app.database import Base
identifier = BigInteger().with_variant(Integer, "sqlite")

org_department = Table("org_department", Base.metadata,
    Column("department_id", identifier, nullable=False, comment="PK；自增；部门记录主键 ID，供员工、客户、学生及部门层级引用。 主键（PK）。", primary_key=True, autoincrement=True),
    Column("department_code", String(32).with_variant(VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="部门唯一业务编码。"),
    Column("department_name", String(100), nullable=False, comment="部门名称。"),
    Column("parent_department_id", identifier, nullable=True, comment="上级部门 ID，关联本表；顶级部门为空。 外键（FK）关联 org_department.department_id。"),
    Column("function_description", Text, nullable=True, comment="部门职能与职责说明。"),
    Column("employee_id", identifier, nullable=True, comment="部门主管员工 ID，关联 employee。 外键（FK）关联 employee.employee_id。"),
    Column("status", String(32).with_variant(VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="部门状态：active 启用、disabled 停用。", server_default=text("'active'")),
    Column("created_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=False, comment="记录创建时间，UTC；连接必须设置 time_zone 为 +00:00", server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=False, comment="更新时自动刷新；记录最近更新时间，UTC", server_default=text("CURRENT_TIMESTAMP")),
    Column("row_version", Integer, nullable=False, comment="并发版本号；每次业务修改由后端递增", server_default=text("1")),
    UniqueConstraint("department_code", name="uq_department_code"),
    CheckConstraint("status IN ('active','disabled')", name="ck_department_status"),
    CheckConstraint("row_version >= 1", name="ck_org_department_row_version"),
    ForeignKeyConstraint(["parent_department_id"], ["org_department.department_id"], name="fk_joint_04", ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(["employee_id"], ["employee.employee_id"], name="fk_joint_05", ondelete="RESTRICT", onupdate="RESTRICT"),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
    comment="部门层级、职能及主管",
)
