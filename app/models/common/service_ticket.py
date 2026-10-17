"""学生投诉／建议主工单；复用唯一Base.metadata，建表由独立SQL负责。"""
from datetime import datetime
from sqlalchemy import Table, Column, BigInteger, Integer, String, Text, DateTime, Date, Boolean, JSON, Numeric, LargeBinary, UniqueConstraint, text
from app.database import Base

service_ticket = Table('service_ticket', Base.metadata,
    Column('ticket_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='PK；自增；投诉反馈工单主键 ID，供处理记录引用。 主键（PK）。', primary_key=True, autoincrement=True),
    Column('ticket_no', String(32), nullable=False, comment='统一工单业务编号。'),
    Column('student_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='投诉或反馈对应学生 ID。 外键（FK）关联 student_profile.student_id。'),
    Column('ticket_type', String(20), nullable=False, comment='complaint 投诉或 suggestion 建议。', server_default=text("'complaint'")),
    Column('category_code', String(32), nullable=False, comment='申请、签证、教学等受控分类编码。'),
    Column('content', Text(), nullable=False, comment='学生提交的原始内容。'),
    Column('ai_summary', Text(), nullable=True, comment='辅助摘要，不覆盖学生原文。'),
    Column('priority', String(20), nullable=False, comment='处理优先级。', server_default=text("'normal'")),
    Column('employee_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=True, comment='当前处理员工 ID，未分派时为空。 外键（FK）关联 employee.employee_id。'),
    Column('handling_department_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='当前处理部门 ID。 外键（FK）关联 org_department.department_id。'),
    Column('status', String(32), nullable=False, comment='工单状态：open 待分派、assigned 已分派、processing 处理中、awaiting_student 待学生确认、closed 已关闭、reopened 已重开。', server_default=text("'open'")),
    Column('first_response_at', DateTime(), nullable=True, comment='首次有效人工回应时间，自动回执不计入。'),
    Column('response_due_at', DateTime(), nullable=False, comment='首次回应截止时间。'),
    Column('resolution_due_at', DateTime(), nullable=False, comment='当前轮次解决截止时间。'),
    Column('solution', Text(), nullable=True, comment='当前解决方案，进入待学生确认状态时必填。'),
    Column('resolved_at', DateTime(), nullable=True, comment='最近给出解决方案的时间。'),
    Column('closed_at', DateTime(), nullable=True, comment='当前有效关闭时间。'),
    Column('reopen_count', Integer(), nullable=False, comment='重新打开次数，默认 0。', server_default=text("'0'")),
    Column('satisfaction_score', Integer(), nullable=True, comment='学生实际评价分数，建议 1—5。'),
    Column('created_at', DateTime(), nullable=False, comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00', default=datetime.utcnow),
    Column('updated_at', DateTime(), nullable=False, comment='更新时自动刷新；记录最近更新时间，UTC', default=datetime.utcnow),
    Column('row_version', Integer(), nullable=False, comment='并发版本号；每次业务修改由后端递增', server_default=text("'1'")),
    UniqueConstraint('ticket_no', name='uq_ticket_no'),
    comment='学生投诉／建议主工单',
)
