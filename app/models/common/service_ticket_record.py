"""工单沟通、分派、处理、确认及重开轮次记录；复用唯一Base.metadata，建表由独立SQL负责。"""
from datetime import datetime
from sqlalchemy import Table, Column, BigInteger, Integer, String, Text, DateTime, Date, Boolean, JSON, Numeric, LargeBinary, UniqueConstraint, text
from app.database import Base

service_ticket_record = Table('service_ticket_record', Base.metadata,
    Column('sla_snapshot', JSON(), nullable=True, comment='本轮时限策略和处理事件快照'),
    Column('ticket_record_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='PK；自增；投诉处理记录主键 ID。 主键（PK）。', primary_key=True, autoincrement=True),
    Column('ticket_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='本条业务记录所属工单 ID。 外键（FK）关联 service_ticket.ticket_id。'),
    Column('record_type', String(32), nullable=False, comment='记录类型：分派、人工回应、备注、解决、确认、重开或升级。'),
    Column('employee_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=True, comment='操作员工 ID，外键关联 employee.employee_id；员工操作时填写。'),
    Column('student_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=True, comment='操作学生 ID，外键关联 student_profile.student_id；学生反馈时填写。'),
    Column('service_code', String(64), nullable=True, comment='自动处理的受控服务编码；系统操作时填写，不作为员工或学生 ID。'),
    Column('content', Text(), nullable=True, comment='本次沟通、反馈或处理说明。'),
    Column('visibility', String(20), nullable=False, comment='internal 内部可见或 student_visible 学生可见。', server_default=text("'internal'")),
    Column('to_status', String(32), nullable=True, comment='本次处理后工单状态。'),
    Column('cycle_no', Integer(), nullable=False, comment='当前处理轮次，初次为 1，重开后递增。', server_default=text("'1'")),
    Column('record_key', String(160), nullable=False, comment='唯一业务记录去重键。'),
    Column('created_at', DateTime(), nullable=False, comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00', default=datetime.utcnow),
    UniqueConstraint('record_key', name='uq_ticket_record_key'),
    comment='工单沟通、分派、处理、确认及重开轮次记录',
)
