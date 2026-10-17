"""统一登录账号 ORM 模型，对应 scripts/sql/all.sql 中的 user_account。"""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, FetchedValue, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from ._types import identifier, utc_now, utc_timestamp


class UserAccount(Base):
    """统一用户账号 ORM 模型，关联管理员/员工/客户/学生身份。"""
    __tablename__ = "user_account"
    __table_args__ = (
        UniqueConstraint("username", name="uq_user_username"),
        UniqueConstraint("employee_id", name="uq_user_employee"),
        UniqueConstraint("customer_id", name="uq_user_customer"),
        UniqueConstraint("student_id", name="uq_user_student"),
        CheckConstraint(
            "(identity_type = 'admin' AND employee_id IS NULL AND customer_id IS NULL AND student_id IS NULL) OR "
            "(identity_type = 'employee' AND employee_id IS NOT NULL AND customer_id IS NULL AND student_id IS NULL) OR "
            "(identity_type = 'customer' AND employee_id IS NULL AND customer_id IS NOT NULL AND student_id IS NULL) OR "
            "(identity_type = 'student' AND employee_id IS NULL AND customer_id IS NULL AND student_id IS NOT NULL)",
            name="ck_user_identity_link",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        identifier, primary_key=True, autoincrement=True, comment="统一用户主键"
    )
    username: Mapped[str] = mapped_column(String(64).with_variant(mysql.VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255).with_variant(mysql.VARCHAR(255, collation="utf8mb4_bin"), "mysql"), nullable=False)
    identity_type: Mapped[str] = mapped_column(String(20).with_variant(mysql.VARCHAR(20, collation="utf8mb4_bin"), "mysql"), nullable=False)
    employee_id: Mapped[int | None] = mapped_column(
        identifier,
        ForeignKey("employee.employee_id", ondelete="RESTRICT", onupdate="RESTRICT"),
    )
    customer_id: Mapped[int | None] = mapped_column(
        identifier,
        ForeignKey("customer_profile.customer_id", ondelete="RESTRICT", onupdate="RESTRICT"),
    )
    student_id: Mapped[int | None] = mapped_column(
        identifier,
        ForeignKey("student_profile.student_id", ondelete="RESTRICT", onupdate="RESTRICT"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now, server_default=utc_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql"), nullable=False, default=utc_now,
        server_default=utc_timestamp(), onupdate=utc_now, server_onupdate=FetchedValue()
    )
