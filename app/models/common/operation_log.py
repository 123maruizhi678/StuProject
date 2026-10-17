"""真实操作者、业务审计、变更快照及幂等回执；复用唯一Base.metadata，建表由独立SQL负责。"""
from datetime import datetime
from sqlalchemy import Table, Column, BigInteger, Integer, String, Text, DateTime, Date, Boolean, JSON, Numeric, LargeBinary, UniqueConstraint, text
from app.database import Base

operation_log = Table('operation_log', Base.metadata,
    Column('operation_log_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='PK；自增；业务操作记录主键 ID。 主键（PK）。', primary_key=True, autoincrement=True),
    Column('operation_key', String(64), nullable=False, comment='操作唯一键，由真实操作者、动作和请求幂等键确定，与新建对象 ID 无关。'),
    Column('employee_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=True, comment='真实操作员工 ID，外键关联 employee.employee_id。'),
    Column('student_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=True, comment='真实操作学生 ID，外键关联 student_profile.student_id。'),
    Column('service_code', String(64), nullable=True, comment='执行自动操作的受控服务编码，不伪装成员工或学生身份。'),
    Column('action_code', String(64), nullable=False, comment='预先定义的业务动作编码。'),
    Column('entity_type', String(32), nullable=False, comment='被操作业务实体类型。'),
    Column('entity_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=True, comment='关联对象 ID，新建未完成或失败时可为空。'),
    Column('request_key', String(128), nullable=False, comment='逻辑业务请求幂等键，同一提交重试保持不变。'),
    Column('parameters_hash', String(64), nullable=False, comment='规范化业务参数摘要，用于识别相同幂等键下的参数冲突。'),
    Column('before_data', JSON(), nullable=True, comment='变更前必要业务快照，敏感字段按规则保护。'),
    Column('after_data', JSON(), nullable=True, comment='变更后必要业务快照，保留审批及修订结果。'),
    Column('change_reason', Text(), nullable=True, comment='人工更正、移交、驳回、删除等业务原因。'),
    Column('operation_status', String(32), nullable=False, comment='操作状态：processing 处理中、succeeded 成功、failed 失败、pending_external 等待外部结果、unknown_external 外部结果待核实。', server_default=text("'processing'")),
    Column('result_reference', JSON(), nullable=True, comment='受控操作回执和对象标识，用于重复请求返回原结果。'),
    Column('external_request_id', String(128), nullable=True, comment='外部系统请求标识，用于查询写回结果和对账。'),
    Column('error_code', String(64), nullable=True, comment='操作失败、冲突或待核实的脱敏错误码。'),
    Column('finished_at', DateTime(), nullable=True, comment='操作形成明确成功或失败结果的时间。'),
    Column('created_at', DateTime(), nullable=False, comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00', default=datetime.utcnow),
    Column('updated_at', DateTime(), nullable=False, comment='更新时自动刷新；记录最近更新时间，UTC', default=datetime.utcnow),
    Column('row_version', Integer(), nullable=False, comment='并发版本号；每次业务修改由后端递增', server_default=text("'1'")),
    UniqueConstraint('operation_key', name='uq_operation_key'),
    comment='真实操作者、业务审计、变更快照及幂等回执',
)
