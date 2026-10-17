"""站内通知的固定查询与写入；不提交、回滚或发送外部消息。"""
from datetime import datetime

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.models.common import business_notification as notifications


def recipient_condition(*, employee_id=None, student_id=None):
    if (employee_id is not None) == (student_id is not None):
        raise ValueError("通知接收人必须且只能是一个员工或学生")
    column, value = (
        (notifications.c.employee_id, employee_id)
        if employee_id is not None else (notifications.c.student_id, student_id)
    )
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("通知接收人必须是有效的内部ID")
    return column == value


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_dedupe_key(self, dedupe_key: str):
        return self.db.execute(select(notifications).where(
            notifications.c.dedupe_key == dedupe_key
        )).mappings().first()

    def enqueue(self, values: dict):
        recipient_condition(employee_id=values.get("employee_id"), student_id=values.get("student_id"))
        result = self.db.execute(insert(notifications).values(**values))
        return result.inserted_primary_key[0]

    def list_for_recipient(self, *, employee_id=None, student_id=None, limit=50):
        if not 1 <= limit <= 200:
            raise ValueError("通知查询数量必须在1至200之间")
        condition = recipient_condition(employee_id=employee_id, student_id=student_id)
        return self.db.execute(select(notifications).where(
            condition, notifications.c.channel == "in_app", notifications.c.delivery_status == "sent",
        ).order_by(
            notifications.c.created_at.desc(), notifications.c.notification_id.desc()
        ).limit(limit)).mappings().all()

    def mark_read(self, notification_id: int, now: datetime, *, employee_id=None, student_id=None):
        condition = recipient_condition(employee_id=employee_id, student_id=student_id)
        result = self.db.execute(update(notifications).where(
            notifications.c.notification_id == notification_id,
            condition, notifications.c.read_at.is_(None),
            notifications.c.channel == "in_app", notifications.c.delivery_status == "sent",
        ).values(read_at=now, updated_at=now, row_version=notifications.c.row_version + 1))
        return result.rowcount == 1
