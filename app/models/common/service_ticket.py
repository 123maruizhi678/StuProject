"""学生投诉／建议主工单；公共唯一映射，复用 Base.metadata。"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, DateTime, FetchedValue, ForeignKey, Index, Integer, String, Table, Text, UniqueConstraint, func, text
)
from sqlalchemy.dialects.mysql import DATETIME, TINYINT, VARCHAR

from app.database import Base


service_ticket = Table(
    'service_ticket', Base.metadata,
    Column('ticket_id', BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True, nullable=False, comment='PK；自增；投诉反馈工单主键 ID，供处理记录引用。 主键（PK）。'),
    Column('ticket_no', String(32), nullable=False, comment='统一工单业务编号。'),
    Column('student_id', BigInteger().with_variant(Integer(), "sqlite"), ForeignKey('student_profile.student_id', name='fk_joint_21', ondelete='RESTRICT', onupdate='RESTRICT'), nullable=False, comment='投诉或反馈对应学生 ID。 外键（FK）关联 student_profile.student_id。'),
    Column('ticket_type', String(20).with_variant(VARCHAR(20, collation="utf8mb4_bin"), "mysql"), nullable=False, server_default=text("'complaint'"), comment='complaint 投诉或 suggestion 建议。'),
    Column('category_code', String(32).with_variant(VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, comment='申请、签证、教学等受控分类编码。'),
    Column('content', Text, nullable=False, comment='学生提交的原始内容。'),
    Column('ai_summary', Text, nullable=True, comment='辅助摘要，不覆盖学生原文。'),
    Column('priority', String(20), nullable=False, server_default=text("'normal'"), comment='处理优先级。'),
    Column('employee_id', BigInteger().with_variant(Integer(), "sqlite"), ForeignKey('employee.employee_id', name='fk_joint_22', ondelete='RESTRICT', onupdate='RESTRICT'), nullable=True, comment='当前处理员工 ID，未分派时为空。 外键（FK）关联 employee.employee_id。'),
    Column('handling_department_id', BigInteger().with_variant(Integer(), "sqlite"), ForeignKey('org_department.department_id', name='fk_joint_23', ondelete='RESTRICT', onupdate='RESTRICT'), nullable=False, comment='当前处理部门 ID。 外键（FK）关联 org_department.department_id。'),
    Column('status', String(32).with_variant(VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, server_default=text("'open'"), comment='工单状态：open 待分派、assigned 已分派、processing 处理中、awaiting_student 待学生确认、closed 已关闭、reopened 已重开。'),
    Column('first_response_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=True, comment='首次有效人工回应时间，自动回执不计入。'),
    Column('response_due_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, comment='首次回应截止时间。'),
    Column('resolution_due_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, comment='当前轮次解决截止时间。'),
    Column('solution', Text, nullable=True, comment='当前解决方案，进入待学生确认状态时必填。'),
    Column('resolved_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=True, comment='最近给出解决方案的时间。'),
    Column('closed_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=True, comment='当前有效关闭时间。'),
    Column('reopen_count', Integer, nullable=False, server_default=text('0'), comment='重新打开次数，默认 0。'),
    Column('satisfaction_score', Integer().with_variant(TINYINT(), "mysql"), nullable=True, comment='学生实际评价分数，建议 1—5。'),
    Column('created_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00'),
    Column('updated_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), server_onupdate=FetchedValue(), comment='更新时自动刷新；记录最近更新时间，UTC'),
    Column('row_version', Integer, nullable=False, server_default=text('1'), comment='并发版本号；每次业务修改由后端递增'),
    UniqueConstraint('ticket_no', name='uq_ticket_no'),
    Index('idx_ticket_employee_status_due', 'employee_id', 'status', 'resolution_due_at'),
    Index('idx_ticket_student_created', 'student_id', 'created_at'),
    Index('idx_ticket_department_status', 'handling_department_id', 'status'),
    CheckConstraint("ticket_type IN ('complaint','suggestion')", name='ck_svc_ticket_type'),
    CheckConstraint("status IN ('open','assigned','processing','awaiting_student','closed','reopened')", name='ck_svc_ticket_status'),
    CheckConstraint('satisfaction_score IS NULL OR satisfaction_score BETWEEN 1 AND 5', name='ck_ticket_satisfaction'),
    CheckConstraint('reopen_count >= 0', name='ck_ticket_reopen_count'),
    CheckConstraint("status NOT IN ('awaiting_student','closed') OR (solution IS NOT NULL AND CHAR_LENGTH(TRIM(solution)) > 0)", name='ck_ticket_solution'),
    CheckConstraint('row_version >= 1', name='ck_service_ticket_row_version'),
    comment='学生投诉／建议主工单',
    mysql_engine="InnoDB",
    mysql_charset="utf8mb4",
    mysql_collate="utf8mb4_0900_ai_ci",
)
