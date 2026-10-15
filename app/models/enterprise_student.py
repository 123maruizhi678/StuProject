"""学生查询及成绩的列映射，匹配 scripts/sql/all.sql；不自动建表。"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

ID = BigInteger().with_variant(Integer, "sqlite")


class Employee(Base):
    __tablename__ = "employee"
    employee_id: Mapped[int] = mapped_column(ID, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100))
    department_id: Mapped[int] = mapped_column(BigInteger)
    role_codes: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32))


class StudentProfile(Base):
    __tablename__ = "student_profile"
    student_id: Mapped[int] = mapped_column(ID, primary_key=True)
    student_no: Mapped[str] = mapped_column(String(32), unique=True)
    full_name: Mapped[str] = mapped_column(String(100))
    department_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(32))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    external_student_id: Mapped[str | None] = mapped_column(String(128))
    crm_student_id: Mapped[str | None] = mapped_column(String(128))
    row_version: Mapped[int] = mapped_column(Integer, default=1)


class StudentStaffBinding(Base):
    __tablename__ = "student_staff_binding"
    binding_id: Mapped[int] = mapped_column(ID, primary_key=True)
    student_id: Mapped[int] = mapped_column(BigInteger)
    employee_id: Mapped[int] = mapped_column(BigInteger)
    relation_type: Mapped[str] = mapped_column(String(32))
    course_scope_code: Mapped[str | None] = mapped_column(String(64))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="active")


class StudentScore(Base):
    __tablename__ = "student_score"
    __table_args__ = (UniqueConstraint("student_id", "course_code", "term_code", "assessment_code", "attempt_no", name="uq_score_assessment_attempt"),)
    score_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(BigInteger)
    course_code: Mapped[str] = mapped_column(String(64))
    term_code: Mapped[str] = mapped_column(String(32))
    assessment_code: Mapped[str] = mapped_column(String(64))
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    score_value: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    max_score: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    employee_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(32), default="valid")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    row_version: Mapped[int] = mapped_column(Integer, default=1)


class OperationLog(Base):
    __tablename__ = "operation_log"
    operation_log_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    operation_key: Mapped[str] = mapped_column(String(64), unique=True)
    employee_id: Mapped[int | None] = mapped_column(BigInteger)
    action_code: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int | None] = mapped_column(BigInteger)
    request_key: Mapped[str] = mapped_column(String(128))
    parameters_hash: Mapped[str] = mapped_column(String(64))
    before_data: Mapped[dict | None] = mapped_column(JSON)
    after_data: Mapped[dict | None] = mapped_column(JSON)
    change_reason: Mapped[str | None] = mapped_column(Text)
    operation_status: Mapped[str] = mapped_column(String(32), default="processing")
    result_reference: Mapped[dict | None] = mapped_column(JSON)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
