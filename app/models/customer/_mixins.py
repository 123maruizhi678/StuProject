"""研判表的时间字段；使用共享 UTC 默认值，不创建第二个 ORM Base。"""
from sqlalchemy import Column, DateTime
from app.models.common._types import utc_now, utc_timestamp


class TimestampMixin:
    created_at = Column(DateTime, nullable=False, default=utc_now, server_default=utc_timestamp())
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now, server_default=utc_timestamp())
