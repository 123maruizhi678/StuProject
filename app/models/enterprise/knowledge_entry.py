"""新人指引、内部制度及知识索引元数据；复用唯一Base.metadata，建表由独立SQL负责。"""
from datetime import datetime
from sqlalchemy import Table, Column, BigInteger, Integer, String, Text, DateTime, Date, Boolean, JSON, Numeric, LargeBinary, UniqueConstraint, text
from app.database import Base

knowledge_entry = Table('knowledge_entry', Base.metadata,
    Column('knowledge_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='PK；自增；知识条目主键 ID。 主键（PK）。', primary_key=True, autoincrement=True),
    Column('entry_code', String(64), nullable=False, comment='知识条目唯一编码。'),
    Column('title', String(200), nullable=False, comment='知识标题。'),
    Column('entry_type', String(20), nullable=False, comment='faq 标准问答或 document 制度文档。'),
    Column('category_code', String(32), nullable=False, comment='入职、制度或业务流程等分类编码。'),
    Column('question', Text(), nullable=True, comment='FAQ 标准问题，faq 时必填。'),
    Column('answer', Text(), nullable=True, comment='FAQ 标准答案，faq 时必填。'),
    Column('content_text', Text(), nullable=True, comment='文档正文，document 时应有正文或受控来源。'),
    Column('source_reference', String(512), nullable=True, comment='原文件、章节或受控资料来源定位。'),
    Column('employee_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='知识维护员工 ID。 外键（FK）关联 employee.employee_id。'),
    Column('access_department_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=True, comment='限定访问部门；为空表示全体员工可见。 外键（FK）关联 org_department.department_id。'),
    Column('version_no', Integer(), nullable=False, comment='当前内容版本号，内容变更时递增。', server_default=text("'1'")),
    Column('status', String(32), nullable=False, comment='draft 草稿、published 已发布、disabled 停用。', server_default=text("'draft'")),
    Column('reviewer_employee_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=True, comment='审核该版本的员工 ID。 外键（FK）关联 employee.employee_id。'),
    Column('reviewed_at', DateTime(), nullable=True, comment='审核完成时间。'),
    Column('effective_from', DateTime(), nullable=True, comment='已发布知识开始生效的时间。'),
    Column('expires_at', DateTime(), nullable=True, comment='知识失效时间。'),
    Column('index_status', String(20), nullable=False, comment='索引状态：pending 待更新、ready 可检索、failed 失败。', server_default=text("'pending'")),
    Column('external_document_id', String(128), nullable=True, comment='Dify 或外部索引中的文档 ID。'),
    Column('created_at', DateTime(), nullable=False, comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00', default=datetime.utcnow),
    Column('updated_at', DateTime(), nullable=False, comment='更新时自动刷新；记录最近更新时间，UTC', default=datetime.utcnow),
    Column('row_version', Integer(), nullable=False, comment='并发版本号；每次业务修改由后端递增', server_default=text("'1'")),
    UniqueConstraint('entry_code', name='uq_knowledge_entry_code'),
    comment='新人指引、内部制度及知识索引元数据',
)
