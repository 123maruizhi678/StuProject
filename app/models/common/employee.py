"""公共身份关联主档的唯一映射；字段依据操作文档建表文件。"""
from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, LargeBinary, String, Table, Text, func, text
from sqlalchemy.dialects.mysql import CHAR, DATETIME, VARCHAR
from app.database import Base


employee = Table(
'employee', Base.metadata,
    Column('employee_id', BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True, comment='PK；自增；员工主键 ID，是所有员工业务关联的内部标识，不使用工号代替。 主键（PK）。'),
    Column('employee_no', String(32), nullable=False, comment='员工唯一工号。'),
    Column('full_name', String(100), nullable=False, comment='员工姓名，允许重名。'),
    Column('department_id', BigInteger().with_variant(Integer, "sqlite"), ForeignKey('org_department.department_id', ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False, comment='当前主部门 ID，关联 org_department。 外键（FK）关联 org_department.department_id。'),
    Column('position_title', String(100), nullable=True, comment='员工岗位或职务名称。'),
    Column('login_provider', String(32).with_variant(VARCHAR(32, collation='utf8mb4_bin'), "mysql"), nullable=False, comment='登录来源，如企业统一登录。'),
    Column('login_subject', String(128).with_variant(VARCHAR(128, collation='utf8mb4_bin'), "mysql"), nullable=False, comment='登录来源提供的不可变账号标识。'),
    Column('role_codes', JSON, nullable=False, comment='受控角色代码数组；权限由后端固定配置解释。'),
    Column('work_phone_ciphertext', LargeBinary(512), nullable=True, comment='加密保存的工作联系电话。'),
    Column('work_email', String(254), nullable=True, comment='工作邮箱。'),
    Column('status', String(32).with_variant(VARCHAR(32, collation='utf8mb4_bin'), "mysql"), nullable=False, server_default=text("'active'"), comment='员工状态：active 启用、disabled 停用、left 离职。'),
    Column('joined_date', Date, nullable=False, comment='入职日期。'),
    Column('left_date', Date, nullable=True, comment='离职日期，未离职时为空。'),
    Column('external_employee_id', String(128).with_variant(VARCHAR(128, collation='utf8mb4_bin'), "mysql"), nullable=True, comment='权威通讯录中的员工 ID。'),
    Column('created_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00'),
    Column('updated_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), comment='更新时自动刷新；记录最近更新时间，UTC'),
    Column('row_version', Integer, nullable=False, server_default=text('1'), comment='并发版本号；每次业务修改由后端递增'),
)
