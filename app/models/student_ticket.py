"""投诉共享表字段投影。禁止在生产使用 metadata.create_all 代替迁移。"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table, Text

from app.models.student_leave import identifier, metadata


service_ticket = Table(
    "service_ticket", metadata,
    Column("ticket_id", identifier, primary_key=True, autoincrement=True),
    Column("ticket_no", String(32), nullable=False, unique=True),
    Column("student_id", identifier, ForeignKey("student_profile.student_id"), nullable=False),
    Column("ticket_type", String(20), nullable=False),
    Column("category_code", String(32), nullable=False),
    Column("content", Text, nullable=False),
    Column("ai_summary", Text),
    Column("priority", String(20), nullable=False),
    Column("employee_id", identifier, ForeignKey("employee.employee_id")),
    Column("handling_department_id", identifier, ForeignKey("org_department.department_id"), nullable=False),
    Column("status", String(32), nullable=False),
    Column("first_response_at", DateTime),
    Column("response_due_at", DateTime, nullable=False),
    Column("resolution_due_at", DateTime, nullable=False),
    Column("solution", Text),
    Column("resolved_at", DateTime),
    Column("closed_at", DateTime),
    Column("reopen_count", Integer, nullable=False),
    Column("satisfaction_score", Integer),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
    Column("row_version", Integer, nullable=False),
)

service_ticket_record = Table(
    "service_ticket_record", metadata,
    Column("ticket_record_id", identifier, primary_key=True, autoincrement=True),
    Column("ticket_id", identifier, ForeignKey("service_ticket.ticket_id"), nullable=False),
    Column("record_type", String(32), nullable=False),
    Column("employee_id", identifier, ForeignKey("employee.employee_id")),
    Column("student_id", identifier, ForeignKey("student_profile.student_id")),
    Column("service_code", String(64)),
    Column("content", Text),
    Column("visibility", String(20), nullable=False),
    Column("to_status", String(32)),
    Column("cycle_no", Integer, nullable=False),
    Column("record_key", String(160), nullable=False, unique=True),
    Column("created_at", DateTime, nullable=False),
)
