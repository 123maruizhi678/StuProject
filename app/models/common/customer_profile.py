"""公共身份关联主档的唯一映射；字段依据操作文档建表文件。"""
from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, LargeBinary, String, Table, Text, func, text
from sqlalchemy.dialects.mysql import CHAR, DATETIME, VARCHAR
from app.database import Base


customer_profile = Table(
'customer_profile', Base.metadata,
    Column('customer_id', BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True, comment='PK；自增；客户主键 ID，是跟进记录及关联学生使用的内部标识。 主键（PK）。'),
    Column('customer_no', String(32), nullable=False, comment='客户唯一业务编号。'),
    Column('full_name', String(100), nullable=False, comment='客户姓名，不作为唯一身份依据。'),
    Column('phone_ciphertext', LargeBinary(512), nullable=True, comment='加密保存的客户手机号。'),
    Column('phone_lookup_token', String(64).with_variant(CHAR(64, collation='utf8mb4_bin'), "mysql"), nullable=True, comment='标准化手机号的带密钥匹配标记，用于提示重复候选。'),
    Column('education_level', String(32), nullable=True, comment='客户学历层次。'),
    Column('target_country_code', String(8).with_variant(VARCHAR(8, collation='utf8mb4_bin'), "mysql"), nullable=True, comment='意向留学国家编码。'),
    Column('source_channel', String(32), nullable=False, comment='客户来源，如人工、客服留资或 CRM。'),
    Column('source_reference', String(128), nullable=True, comment='来源留资或研判任务引用；固定服务核验实体及授权，不存明文联系方式'),
    Column('employee_id', BigInteger().with_variant(Integer, "sqlite"), ForeignKey('employee.employee_id', ondelete="RESTRICT", onupdate="RESTRICT"), nullable=True, comment='当前顾问员工 ID，未分派时为空。 外键（FK）关联 employee.employee_id。'),
    Column('department_id', BigInteger().with_variant(Integer, "sqlite"), ForeignKey('org_department.department_id', ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False, comment='当前客户管理部门 ID。 外键（FK）关联 org_department.department_id。'),
    Column('status', String(32).with_variant(VARCHAR(32, collation='utf8mb4_bin'), "mysql"), nullable=False, server_default=text("'new'"), comment='客户状态：new、contacting、qualified、signed、lost。'),
    Column('status_changed_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), comment='当前客户状态开始生效的时间。'),
    Column('lost_reason', Text, nullable=True, comment='流失原因，状态变为 lost 时必须填写。'),
    Column('last_followup_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=True, comment='最近一次有效跟进时间，由业务服务维护。'),
    Column('authority_source', String(20), nullable=False, server_default=text("'local'"), comment='数据权威来源：local 本平台、crm 外部 CRM。'),
    Column('external_customer_id', String(128).with_variant(VARCHAR(128, collation='utf8mb4_bin'), "mysql"), nullable=True, comment='CRM 中的客户 ID。'),
    Column('external_updated_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=True, comment='最近确认的外部客户更新时间。'),
    Column('is_archived', Boolean, nullable=False, server_default=text('0'), comment='是否已归档，默认 false；保留销售状态和历史，归档后不进入默认客户列表。'),
    Column('created_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00'),
    Column('updated_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), comment='更新时自动刷新；记录最近更新时间，UTC'),
    Column('row_version', Integer, nullable=False, server_default=text('1'), comment='并发版本号；每次业务修改由后端递增'),
)
