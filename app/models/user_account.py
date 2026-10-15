"""统一登录账号 ORM 模型，对应 scripts/sql/all.sql 中的 user_account。"""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserAccount(Base):
    """统一用户账号 ORM 模型，关联管理员/员工/客户/学生身份。"""
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

    user_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="统一用户主键"
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    identity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    employee_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("employee.employee_id", ondelete="RESTRICT", onupdate="RESTRICT"),
        unique=True,
    )
    customer_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("customer_profile.customer_id", ondelete="RESTRICT", onupdate="RESTRICT"),
        unique=True,
    )
    student_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("student_profile.student_id", ondelete="RESTRICT", onupdate="RESTRICT"),
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
