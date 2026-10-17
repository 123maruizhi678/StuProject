"""客户多次跟进及下次跟进安排；复用唯一Base.metadata，建表由独立SQL负责。"""
from datetime import datetime
from sqlalchemy import Table, Column, BigInteger, Integer, String, Text, DateTime, Date, Boolean, JSON, Numeric, LargeBinary, UniqueConstraint, text
from app.database import Base

customer_followup = Table('customer_followup', Base.metadata,
    Column('schedule_operation_id', BigInteger().with_variant(Integer(), 'sqlite'), nullable=True, comment='当前安排代次成功审计主键'),
    Column('schedule_base_at', DateTime(), nullable=True, comment='当前提醒基准时间UTC'),
    Column('followup_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='PK；自增；客户跟进记录主键 ID。 主键（PK）。', primary_key=True, autoincrement=True),
    Column('customer_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='本记录所属客户 ID。 外键（FK）关联 customer_profile.customer_id。'),
    Column('employee_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='实际执行跟进的员工 ID。 外键（FK）关联 employee.employee_id。'),
    Column('followup_at', DateTime(), nullable=False, comment='客户沟通实际发生时间。', default=datetime.utcnow),
    Column('channel', String(32), nullable=False, comment='跟进方式，如电话、面谈或线上沟通。'),
    Column('content', Text(), nullable=False, comment='完整跟进内容。'),
    Column('summary', Text(), nullable=True, comment='经员工确认的跟进摘要。'),
    Column('next_followup_at', DateTime(), nullable=True, comment='计划下一次跟进的时间。'),
    Column('followup_status', String(20), nullable=False, comment='下一次跟进安排状态：none 未安排、pending 待跟进、done 已完成、cancelled 已取消。', server_default=text("'none'")),
    Column('created_at', DateTime(), nullable=False, comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00', default=datetime.utcnow),
    Column('updated_at', DateTime(), nullable=False, comment='更新时自动刷新；记录最近更新时间，UTC', default=datetime.utcnow),
    Column('row_version', Integer(), nullable=False, comment='并发版本号；每次业务修改由后端递增', server_default=text("'1'")),
    comment='客户多次跟进及下次跟进安排',
)
