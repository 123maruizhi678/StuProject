"""按最终建表 SQL 映射；公共表只注册在 Base.metadata，导入不执行建表。"""
from sqlalchemy import (Table, Column, BigInteger, Integer, String, Text, Boolean, DateTime, Date, JSON, Numeric, LargeBinary, UniqueConstraint, CheckConstraint, ForeignKeyConstraint, text)
from sqlalchemy.dialects.mysql import DATETIME, VARCHAR
from app.database import Base
identifier = BigInteger().with_variant(Integer, "sqlite")

operation_log = Table("operation_log", Base.metadata,
    Column("operation_log_id", identifier, nullable=False, comment="PK；自增；业务操作记录主键 ID。 主键（PK）。", primary_key=True, autoincrement=True),
    Column("operation_key", String(64).with_variant(VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="操作唯一键，由真实操作者、动作和请求幂等键确定，与新建对象 ID 无关。"),
    Column("employee_id", identifier, nullable=True, comment="真实操作员工 ID，外键关联 employee.employee_id。"),
    Column("student_id", identifier, nullable=True, comment="真实操作学生 ID，外键关联 student_profile.student_id。"),
    Column("service_code", String(64).with_variant(VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=True, comment="执行自动操作的受控服务编码，不伪装成员工或学生身份。"),
    Column("action_code", String(64).with_variant(VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="预先定义的业务动作编码。"),
    Column("entity_type", String(32).with_variant(VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="被操作业务实体类型。"),
    Column("entity_id", identifier, nullable=True, comment="关联对象 ID，新建未完成或失败时可为空。"),
    Column("request_key", String(128).with_variant(VARCHAR(128, collation="ascii_bin", charset="ascii"), "mysql"), nullable=False, comment="逻辑业务请求幂等键，同一提交重试保持不变。"),
    Column("parameters_hash", String(64).with_variant(VARCHAR(64, collation="ascii_bin", charset="ascii"), "mysql"), nullable=False, comment="规范化业务参数摘要，用于识别相同幂等键下的参数冲突。"),
    Column("before_data", JSON, nullable=True, comment="变更前必要业务快照，敏感字段按规则保护。"),
    Column("after_data", JSON, nullable=True, comment="变更后必要业务快照，保留审批及修订结果。"),
    Column("change_reason", Text, nullable=True, comment="人工更正、移交、驳回、删除等业务原因。"),
    Column("operation_status", String(32).with_variant(VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="操作状态：processing 处理中、succeeded 成功、failed 失败、pending_external 等待外部结果、unknown_external 外部结果待核实。", server_default=text("'processing'")),
    Column("result_reference", JSON, nullable=True, comment="受控操作回执和对象标识，用于重复请求返回原结果。"),
    Column("external_request_id", String(128).with_variant(VARCHAR(128, collation="utf8mb4_bin"), "mysql"), nullable=True, comment="外部系统请求标识，用于查询写回结果和对账。"),
    Column("error_code", String(64).with_variant(VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=True, comment="操作失败、冲突或待核实的脱敏错误码。"),
    Column("finished_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=True, comment="操作形成明确成功或失败结果的时间。"),
    Column("created_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=False, comment="记录创建时间，UTC；连接必须设置 time_zone 为 +00:00", server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=False, comment="更新时自动刷新；记录最近更新时间，UTC", server_default=text("CURRENT_TIMESTAMP")),
    Column("row_version", Integer, nullable=False, comment="并发版本号；每次业务修改由后端递增", server_default=text("1")),
    UniqueConstraint("operation_key", name="uq_operation_key"),
    CheckConstraint("((employee_id IS NOT NULL) + (student_id IS NOT NULL) + (service_code IS NOT NULL)) = 1", name="ck_operation_actor"),
    CheckConstraint("service_code IS NULL OR CHAR_LENGTH(TRIM(service_code)) > 0", name="ck_operation_service"),
    CheckConstraint("operation_status IN ('processing','succeeded','failed','pending_external','unknown_external')", name="ck_operation_status"),
    CheckConstraint("row_version >= 1", name="ck_operation_log_row_version"),
    ForeignKeyConstraint(["employee_id"], ["employee.employee_id"], name="fk_joint_32", ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(["student_id"], ["student_profile.student_id"], name="fk_joint_33", ondelete="RESTRICT", onupdate="RESTRICT"),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
    comment="真实操作者、业务审计、变更快照及幂等回执",
)
