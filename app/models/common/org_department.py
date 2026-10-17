"""部门层级、职能及主管；复用唯一Base.metadata，建表由独立SQL负责。"""
from datetime import datetime
from sqlalchemy import Table, Column, BigInteger, Integer, String, Text, DateTime, Date, Boolean, JSON, Numeric, LargeBinary, UniqueConstraint, text
from app.database import Base

org_department = Table('org_department', Base.metadata,
    Column('department_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='PK；自增；部门记录主键 ID，供员工、客户、学生及部门层级引用。 主键（PK）。', primary_key=True, autoincrement=True),
    Column('department_code', String(32), nullable=False, comment='部门唯一业务编码。'),
    Column('department_name', String(100), nullable=False, comment='部门名称。'),
    Column('parent_department_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=True, comment='上级部门 ID，关联本表；顶级部门为空。 外键（FK）关联 org_department.department_id。'),
    Column('function_description', Text(), nullable=True, comment='部门职能与职责说明。'),
    Column('employee_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=True, comment='部门主管员工 ID，关联 employee。 外键（FK）关联 employee.employee_id。'),
    Column('status', String(32), nullable=False, comment='部门状态：active 启用、disabled 停用。', server_default=text("'active'")),
    Column('created_at', DateTime(), nullable=False, comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00', default=datetime.utcnow),
    Column('updated_at', DateTime(), nullable=False, comment='更新时自动刷新；记录最近更新时间，UTC', default=datetime.utcnow),
    Column('row_version', Integer(), nullable=False, comment='并发版本号；每次业务修改由后端递增', server_default=text("'1'")),
    UniqueConstraint('department_code', name='uq_department_code'),
    comment='部门层级、职能及主管',
)
