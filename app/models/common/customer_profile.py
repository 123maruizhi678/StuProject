"""统一客户主档、顾问归属及客户状态；复用唯一Base.metadata，建表由独立SQL负责。"""
from datetime import datetime
from sqlalchemy import Table, Column, BigInteger, Integer, String, Text, DateTime, Date, Boolean, JSON, Numeric, LargeBinary, UniqueConstraint, text
from app.database import Base

customer_profile = Table('customer_profile', Base.metadata,
    Column('customer_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='PK；自增；客户主键 ID，是跟进记录及关联学生使用的内部标识。 主键（PK）。', primary_key=True, autoincrement=True),
    Column('customer_no', String(32), nullable=False, comment='客户唯一业务编号。'),
    Column('full_name', String(100), nullable=False, comment='客户姓名，不作为唯一身份依据。'),
    Column('phone_ciphertext', LargeBinary(512), nullable=True, comment='加密保存的客户手机号。'),
    Column('phone_lookup_token', String(64), nullable=True, comment='标准化手机号的带密钥匹配标记，用于提示重复候选。'),
    Column('education_level', String(32), nullable=True, comment='客户学历层次。'),
    Column('target_country_code', String(8), nullable=True, comment='意向留学国家编码。'),
    Column('source_channel', String(32), nullable=False, comment='客户来源，如人工、客服留资或 CRM。'),
    Column('source_reference', String(128), nullable=True, comment='来源留资或研判任务引用；固定服务核验实体及授权，不存明文联系方式'),
    Column('employee_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=True, comment='当前顾问员工 ID，未分派时为空。 外键（FK）关联 employee.employee_id。'),
    Column('department_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='当前客户管理部门 ID。 外键（FK）关联 org_department.department_id。'),
    Column('status', String(32), nullable=False, comment='客户状态：new、contacting、qualified、signed、lost。', server_default=text("'new'")),
    Column('status_changed_at', DateTime(), nullable=False, comment='当前客户状态开始生效的时间。', default=datetime.utcnow),
    Column('lost_reason', Text(), nullable=True, comment='流失原因，状态变为 lost 时必须填写。'),
    Column('last_followup_at', DateTime(), nullable=True, comment='最近一次有效跟进时间，由业务服务维护。'),
    Column('authority_source', String(20), nullable=False, comment='数据权威来源：local 本平台、crm 外部 CRM。', server_default=text("'local'")),
    Column('external_customer_id', String(128), nullable=True, comment='CRM 中的客户 ID。'),
    Column('external_updated_at', DateTime(), nullable=True, comment='最近确认的外部客户更新时间。'),
    Column('is_archived', Integer(), nullable=False, comment='是否已归档，默认 false；保留销售状态和历史，归档后不进入默认客户列表。', server_default=text("'0'")),
    Column('created_at', DateTime(), nullable=False, comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00', default=datetime.utcnow),
    Column('updated_at', DateTime(), nullable=False, comment='更新时自动刷新；记录最近更新时间，UTC', default=datetime.utcnow),
    Column('row_version', Integer(), nullable=False, comment='并发版本号；每次业务修改由后端递增', server_default=text("'1'")),
    UniqueConstraint('external_customer_id', name='uq_customer_external'),
    UniqueConstraint('customer_no', name='uq_customer_no'),
    comment='统一客户主档、顾问归属及客户状态',
)
