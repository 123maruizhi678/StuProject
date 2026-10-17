"""员工正式日报、修订及作废状态；复用唯一Base.metadata，建表由独立SQL负责。"""
from datetime import datetime
from sqlalchemy import Table, Column, BigInteger, Integer, String, Text, DateTime, Date, Boolean, JSON, Numeric, LargeBinary, UniqueConstraint, text
from app.database import Base

employee_daily_report = Table('employee_daily_report', Base.metadata,
    Column('daily_report_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='PK；自增；员工日报记录主键 ID。 主键（PK）。', primary_key=True, autoincrement=True),
    Column('employee_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='日报所属员工 ID。 外键（FK）关联 employee.employee_id。'),
    Column('report_date', Date(), nullable=False, comment='日报对应机构工作日日期。'),
    Column('department_id_at_submit', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='最近提交时的部门快照。 外键（FK）关联 org_department.department_id。'),
    Column('submitted_content', Text(), nullable=False, comment='最近一次员工确认提交的正式内容，必须填写。'),
    Column('ai_summary', Text(), nullable=True, comment='与最近提交内容对应的辅助摘要。'),
    Column('status', String(32), nullable=False, comment='日报状态：submitted 已提交、void 已作废。', server_default=text("'submitted'")),
    Column('submitted_at', DateTime(), nullable=False, comment='最近正式提交时间。', default=datetime.utcnow),
    Column('created_at', DateTime(), nullable=False, comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00', default=datetime.utcnow),
    Column('updated_at', DateTime(), nullable=False, comment='更新时自动刷新；记录最近更新时间，UTC', default=datetime.utcnow),
    Column('row_version', Integer(), nullable=False, comment='并发版本号；每次业务修改由后端递增', server_default=text("'1'")),
    UniqueConstraint('employee_id', 'report_date', name='uq_daily_employee_date'),
    comment='员工正式日报、修订及作废状态',
)
