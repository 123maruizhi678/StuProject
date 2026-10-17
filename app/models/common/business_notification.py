"""业务站内通知、收件人、去重、投递及重试；复用唯一Base.metadata，建表由独立SQL负责。"""
from datetime import datetime
from sqlalchemy import Table, Column, BigInteger, Integer, String, Text, DateTime, Date, Boolean, JSON, Numeric, LargeBinary, UniqueConstraint, text
from app.database import Base

business_notification = Table('business_notification', Base.metadata,
    Column('notification_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='PK；自增；业务通知记录主键 ID。 主键（PK）。', primary_key=True, autoincrement=True),
    Column('entity_type', String(32), nullable=False, comment='关联业务实体类型，如请假、投诉或跟进。'),
    Column('entity_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='关联业务记录 ID，由业务服务按实体类型校验。'),
    Column('event_code', String(64), nullable=False, comment='业务通知原因，如待审批、审批结果或投诉解决。'),
    Column('employee_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=True, comment='员工接收人 ID，与学生接收人二选一。 外键（FK）关联 employee.employee_id。'),
    Column('student_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=True, comment='学生接收人 ID，与员工接收人二选一。 外键（FK）关联 student_profile.student_id。'),
    Column('channel', String(20), nullable=False, comment='投递渠道，如站内或企业消息。'),
    Column('title', String(200), nullable=False, comment='通知标题，只包含必要信息。'),
    Column('content', Text(), nullable=False, comment='通知内容，不包含敏感业务原文。'),
    Column('dedupe_key', String(160), nullable=False, comment='包含业务事件、轮次、接收人及渠道的唯一通知键。'),
    Column('delivery_status', String(20), nullable=False, comment='pending 待发送、sending 发送中、sent 已发送、failed 失败、dead_letter 终止重试。', server_default=text("'pending'")),
    Column('attempt_count', Integer(), nullable=False, comment='已尝试发送次数，初值 0。', server_default=text("'0'")),
    Column('next_retry_at', DateTime(), nullable=True, comment='下一次允许重试时间。'),
    Column('lease_until', DateTime(), nullable=True, comment='发送任务租约截止时间，用于恢复中断任务。'),
    Column('sent_at', DateTime(), nullable=True, comment='对应渠道确认接收消息的时间。'),
    Column('read_at', DateTime(), nullable=True, comment='真实已读时间，不支持回执时为空。'),
    Column('last_error_code', String(64), nullable=True, comment='最近一次发送失败的脱敏错误码。'),
    Column('created_at', DateTime(), nullable=False, comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00', default=datetime.utcnow),
    Column('updated_at', DateTime(), nullable=False, comment='更新时自动刷新；记录最近更新时间，UTC', default=datetime.utcnow),
    Column('row_version', Integer(), nullable=False, comment='并发版本号；每次业务修改由后端递增', server_default=text("'1'")),
    UniqueConstraint('dedupe_key', name='uq_notification_dedupe'),
    comment='业务站内通知、收件人、去重、投递及重试',
)
