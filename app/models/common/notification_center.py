"""公共公告及逐账号已读记录；通过独立迁移创建，不改业务通知表。"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text, CheckConstraint
from app.database import Base
from ._types import identifier, utc_now

platform_announcement = Table(
    "platform_announcement", Base.metadata,
    Column("announcement_id", identifier, primary_key=True, autoincrement=True),
    Column("title", String(200), nullable=False),
    Column("content", Text, nullable=False),
    Column("status", String(20), nullable=False, default="draft"),
    Column("pinned", Boolean, nullable=False, default=False),
    Column("published_at", DateTime, nullable=True),
    Column("expires_at", DateTime, nullable=True),
    Column("author_user_id", identifier, ForeignKey("user_account.user_id"), nullable=False),
    Column("created_at", DateTime, nullable=False, default=utc_now),
    Column("updated_at", DateTime, nullable=False, default=utc_now),
    Column("row_version", Integer, nullable=False, default=1),
    CheckConstraint("status IN ('draft','published','withdrawn')", name="ck_platform_announcement_status"),
    CheckConstraint("row_version >= 1", name="ck_platform_announcement_version"),
    mysql_engine="InnoDB", mysql_charset="utf8mb4",
)

platform_notification_read = Table(
    "platform_notification_read", Base.metadata,
    Column("user_id", identifier, ForeignKey("user_account.user_id"), primary_key=True),
    Column("message_key", String(96), primary_key=True),
    Column("read_at", DateTime, nullable=False, default=utc_now),
    mysql_engine="InnoDB", mysql_charset="utf8mb4",
)
