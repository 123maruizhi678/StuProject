"""all.sql 公共表的字段投影；生产建表仍由公共 SQL/迁移负责。"""
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Integer, JSON, MetaData, String,
    Table, Text, UniqueConstraint,
)

metadata = MetaData()
identifier = BigInteger().with_variant(Integer, "sqlite")

student_profile = Table(
    "student_profile", metadata,
    Column("student_id", identifier, primary_key=True),
    Column("status", String(32), nullable=False),
    Column("is_archived", Boolean, nullable=False),
)
employee = Table(
    "employee", metadata,
    Column("employee_id", identifier, primary_key=True),
    Column("status", String(32), nullable=False),
    Column("role_codes", JSON, nullable=False),
)
student_staff_binding = Table(
    "student_staff_binding", metadata,
    Column("binding_id", identifier, primary_key=True),
    Column("student_id", identifier, nullable=False),
    Column("employee_id", identifier, nullable=False),
    Column("relation_type", String(32), nullable=False),
    Column("is_primary", Boolean, nullable=False),
    Column("status", String(32), nullable=False),
    Column("valid_from", DateTime, nullable=False),
    Column("valid_to", DateTime),
)
student_admin_service = Table(
    "student_admin_service", metadata,
    Column("id", identifier, primary_key=True, autoincrement=True),
    Column("student_id", identifier, nullable=False),
    Column("apply_type", String(20), nullable=False),
    Column("apply_content", Text, nullable=False),
    Column("approval_status", String(20), nullable=False),
    Column("edu_related_data", JSON),
    Column("leave_start_at", DateTime, nullable=False),
    Column("leave_end_at", DateTime, nullable=False),
    Column("reviewer_id", identifier),
    Column("request_key", String(128), nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("row_version", Integer, nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
    UniqueConstraint("student_id", "request_key", name="uk_admin_request"),
)
business_notification = Table(
    "business_notification", metadata,
    Column("notification_id", identifier, primary_key=True, autoincrement=True),
    Column("entity_type", String(32), nullable=False),
    Column("entity_id", identifier, nullable=False),
    Column("event_code", String(64), nullable=False),
    Column("employee_id", identifier),
    Column("student_id", identifier),
    Column("channel", String(20), nullable=False),
    Column("title", String(200), nullable=False),
    Column("content", Text, nullable=False),
    Column("dedupe_key", String(160), nullable=False, unique=True),
    Column("delivery_status", String(20), nullable=False),
    Column("attempt_count", Integer, nullable=False),
    Column("row_version", Integer, nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)
operation_log = Table(
    "operation_log", metadata,
    Column("operation_log_id", identifier, primary_key=True, autoincrement=True),
    Column("operation_key", String(64), nullable=False, unique=True),
    Column("student_id", identifier),
    Column("employee_id", identifier),
    Column("service_code", String(64)),
    Column("action_code", String(64), nullable=False),
    Column("entity_type", String(32), nullable=False),
    Column("entity_id", identifier),
    Column("request_key", String(128), nullable=False),
    Column("parameters_hash", String(64), nullable=False),
    Column("operation_status", String(32), nullable=False),
    Column("after_data", JSON),
    Column("result_reference", JSON),
    Column("row_version", Integer, nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
    Column("finished_at", DateTime),
)
