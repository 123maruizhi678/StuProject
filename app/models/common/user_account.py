"""统一账号唯一 ORM，使用既有 MySQL 表，不在应用启动时建表。"""
from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.mysql import DATETIME, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class UserAccount(Base):
    __tablename__ = "user_account"
    __table_args__ = (
        CheckConstraint(
            "(identity_type = 'admin' AND employee_id IS NULL AND customer_id IS NULL AND student_id IS NULL) OR "
            "(identity_type = 'employee' AND employee_id IS NOT NULL AND customer_id IS NULL AND student_id IS NULL) OR "
            "(identity_type = 'customer' AND employee_id IS NULL AND customer_id IS NOT NULL AND student_id IS NULL) OR "
            "(identity_type = 'student' AND employee_id IS NULL AND customer_id IS NULL AND student_id IS NOT NULL)",
            name="ck_user_identity_link",
        ),
    )
    user_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64).with_variant(VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255).with_variant(VARCHAR(255, collation="utf8mb4_bin"), "mysql"), nullable=False)
    identity_type: Mapped[str] = mapped_column(String(20).with_variant(VARCHAR(20, collation="utf8mb4_bin"), "mysql"), nullable=False)
    employee_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("employee.employee_id", ondelete="RESTRICT", onupdate="RESTRICT"), unique=True)
    customer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("customer_profile.customer_id", ondelete="RESTRICT", onupdate="RESTRICT"), unique=True)
    student_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("student_profile.student_id", ondelete="RESTRICT", onupdate="RESTRICT"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), onupdate=func.now())
