"""按最终建表 SQL 映射；公共表只注册在 Base.metadata，导入不执行建表。"""
from sqlalchemy import (Table, Column, BigInteger, Integer, String, Text, Boolean, DateTime, Date, JSON, Numeric, LargeBinary, UniqueConstraint, CheckConstraint, ForeignKeyConstraint, text)
from sqlalchemy.dialects.mysql import DATETIME, VARCHAR
from app.database import Base
identifier = BigInteger().with_variant(Integer, "sqlite")

service_ticket_record = Table("service_ticket_record", Base.metadata,
    Column("ticket_record_id", identifier, nullable=False, comment="PK；自增；投诉处理记录主键 ID。 主键（PK）。", primary_key=True, autoincrement=True),
    Column("ticket_id", identifier, nullable=False, comment="本条业务记录所属工单 ID。 外键（FK）关联 service_ticket.ticket_id。"),
    Column("record_type", String(32), nullable=False, comment="记录类型：分派、人工回应、备注、解决、确认、重开或升级。"),
    Column("employee_id", identifier, nullable=True, comment="操作员工 ID，外键关联 employee.employee_id；员工操作时填写。"),
    Column("student_id", identifier, nullable=True, comment="操作学生 ID，外键关联 student_profile.student_id；学生反馈时填写。"),
    Column("service_code", String(64).with_variant(VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=True, comment="自动处理的受控服务编码；系统操作时填写，不作为员工或学生 ID。"),
    Column("content", Text, nullable=True, comment="本次沟通、反馈或处理说明。"),
    Column("visibility", String(20).with_variant(VARCHAR(20, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="internal 内部可见或 student_visible 学生可见。", server_default=text("'internal'")),
    Column("to_status", String(32), nullable=True, comment="本次处理后工单状态。"),
    Column("cycle_no", Integer, nullable=False, comment="当前处理轮次，初次为 1，重开后递增。", server_default=text("1")),
    Column("record_key", String(160).with_variant(VARCHAR(160, collation="utf8mb4_bin"), "mysql"), nullable=False, comment="唯一业务记录去重键。"),
    Column("created_at", DATETIME(fsp=3).with_variant(DateTime(), "sqlite"), nullable=False, comment="记录创建时间，UTC；连接必须设置 time_zone 为 +00:00", server_default=text("CURRENT_TIMESTAMP")),
    UniqueConstraint("record_key", name="uq_ticket_record_key"),
    CheckConstraint("((employee_id IS NOT NULL) + (student_id IS NOT NULL) + (service_code IS NOT NULL)) = 1", name="ck_ticket_record_actor"),
    CheckConstraint("service_code IS NULL OR CHAR_LENGTH(TRIM(service_code)) > 0", name="ck_ticket_record_service"),
    CheckConstraint("visibility IN ('internal','student_visible')", name="ck_ticket_record_visibility"),
    CheckConstraint("cycle_no >= 1", name="ck_ticket_record_cycle"),
    CheckConstraint("to_status IS NULL OR to_status IN ('open','assigned','processing','awaiting_student','closed','reopened')", name="ck_ticket_record_to_status"),
    ForeignKeyConstraint(["ticket_id"], ["service_ticket.ticket_id"], name="fk_joint_24", ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(["student_id"], ["student_profile.student_id"], name="fk_joint_25", ondelete="RESTRICT", onupdate="RESTRICT"),
    ForeignKeyConstraint(["employee_id"], ["employee.employee_id"], name="fk_joint_26", ondelete="RESTRICT", onupdate="RESTRICT"),
    mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
    comment="工单沟通、分派、处理、确认及重开轮次记录",
)
