"""学生请假读写；只使用固定SQLAlchemy表和参数。"""
from sqlalchemy import insert, or_, select

from app.models import common as t
from app.repositories.common.notification_repository import NotificationRepository
from app.repositories.common.operation_log_repository import OperationLogRepository


class StudentLeaveRepository:
    def __init__(self, db):
        self.db = db
        self.notifications = NotificationRepository(db)
        self.operations = OperationLogRepository(db)

    def get_student(self, student_id, *, lock=False):
        query = select(t.student_profile).where(t.student_profile.c.student_id == student_id)
        if lock:
            query = query.with_for_update()
        return self.db.execute(query).mappings().first()

    def find_operation(self, operation_key):
        return self.operations.find_by_key(operation_key)

    def find_teacher(self, student_id, now):
        b, e = t.student_staff_binding, t.employee
        rows = self.db.execute(select(b.c.employee_id, e.c.role_codes).join(
            e, e.c.employee_id == b.c.employee_id
        ).where(
            b.c.student_id == student_id, b.c.relation_type == "class_teacher",
            b.c.status == "active", e.c.status == "active", b.c.valid_from <= now,
            or_(b.c.valid_to.is_(None), b.c.valid_to > now),
        ).order_by(b.c.is_primary.desc(), b.c.binding_id)).mappings()
        for row in rows:
            if isinstance(row["role_codes"], list) and "teacher" in row["role_codes"]:
                return row["employee_id"]
        return None

    def create_operation(self, values):
        return self.operations.create(values)

    def create_application(self, values):
        result = self.db.execute(insert(t.student_admin_service).values(**values))
        return result.inserted_primary_key[0]

    def queue_notification(self, values):
        return self.notifications.enqueue(values)

    def complete_operation(self, operation_key, values):
        if not self.operations.complete(operation_key, values):
            raise RuntimeError("请假审计回执状态发生冲突")

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()
