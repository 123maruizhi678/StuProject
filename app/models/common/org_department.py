"""公共身份关联主档的唯一映射；字段依据操作文档建表文件。"""
from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, LargeBinary, String, Table, Text, func, text
from sqlalchemy.dialects.mysql import CHAR, DATETIME, VARCHAR
from app.database import Base


org_department = Table(
'org_department', Base.metadata,
    Column('department_id', BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True, comment='PK；自增；部门记录主键 ID，供员工、客户、学生及部门层级引用。 主键（PK）。'),
    Column('department_code', String(32).with_variant(VARCHAR(32, collation='utf8mb4_bin'), "mysql"), nullable=False, comment='部门唯一业务编码。'),
    Column('department_name', String(100), nullable=False, comment='部门名称。'),
    Column('parent_department_id', BigInteger().with_variant(Integer, "sqlite"), ForeignKey('org_department.department_id', ondelete="RESTRICT", onupdate="RESTRICT"), nullable=True, comment='上级部门 ID，关联本表；顶级部门为空。 外键（FK）关联 org_department.department_id。'),
    Column('function_description', Text, nullable=True, comment='部门职能与职责说明。'),
    Column('employee_id', BigInteger().with_variant(Integer, "sqlite"), ForeignKey('employee.employee_id', ondelete="RESTRICT", onupdate="RESTRICT"), nullable=True, comment='部门主管员工 ID，关联 employee。 外键（FK）关联 employee.employee_id。'),
    Column('status', String(32).with_variant(VARCHAR(32, collation='utf8mb4_bin'), "mysql"), nullable=False, server_default=text("'active'"), comment='部门状态：active 启用、disabled 停用。'),
    Column('created_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00'),
    Column('updated_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), comment='更新时自动刷新；记录最近更新时间，UTC'),
    Column('row_version', Integer, nullable=False, server_default=text('1'), comment='并发版本号；每次业务修改由后端递增'),
)
