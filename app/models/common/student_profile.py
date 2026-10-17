"""公共身份关联主档的唯一映射；字段依据操作文档建表文件。"""
from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, LargeBinary, String, Table, Text, func, text
from sqlalchemy.dialects.mysql import CHAR, DATETIME, VARCHAR
from app.database import Base


student_profile = Table(
'student_profile', Base.metadata,
    Column('student_id', BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True, comment='PK；自增；学生主键 ID，是成绩、请假、投诉及学生员工关系使用的内部标识。 主键（PK）。'),
    Column('student_no', String(32), nullable=False, comment='学生唯一业务编号。'),
    Column('full_name', String(100), nullable=False, comment='学生姓名，允许重名。'),
    Column('phone_ciphertext', LargeBinary(512), nullable=True, comment='加密保存的学生手机号。'),
    Column('customer_id', BigInteger().with_variant(Integer, "sqlite"), ForeignKey('customer_profile.customer_id', ondelete="RESTRICT", onupdate="RESTRICT"), nullable=True, comment='关联客户 ID，不自动授予客户账号访问学生数据的权限。 外键（FK）关联 customer_profile.customer_id。'),
    Column('department_id', BigInteger().with_variant(Integer, "sqlite"), ForeignKey('org_department.department_id', ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False, comment='学生教务或服务归属部门 ID。 外键（FK）关联 org_department.department_id。'),
    Column('login_provider', String(32).with_variant(VARCHAR(32, collation='utf8mb4_bin'), "mysql"), nullable=True, comment='学生登录来源，尚未开通账号时为空。'),
    Column('login_subject', String(128).with_variant(VARCHAR(128, collation='utf8mb4_bin'), "mysql"), nullable=True, comment='学生登录身份键，与登录来源同时填写。'),
    Column('status', String(32).with_variant(VARCHAR(32, collation='utf8mb4_bin'), "mysql"), nullable=False, comment='学生服务或在读状态。'),
    Column('external_student_id', String(128).with_variant(VARCHAR(128, collation='utf8mb4_bin'), "mysql"), nullable=True, comment='教务系统中的学生 ID。'),
    Column('crm_student_id', String(128), nullable=True, comment='CRM 学生独立标识；目标为非空值唯一，类型与学生文档一致；由后续统一迁移核对补齐。'),
    Column('is_archived', Boolean, nullable=False, server_default=text('0'), comment='是否已归档，默认 false；归档不删除已有成绩、请假和投诉关联。'),
    Column('created_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00'),
    Column('updated_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), comment='更新时自动刷新；记录最近更新时间，UTC'),
    Column('row_version', Integer, nullable=False, server_default=text('1'), comment='并发版本号；每次业务修改由后端递增'),
)
