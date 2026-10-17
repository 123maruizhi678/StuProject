"""学生仓储公共操作：主档、审计幂等、通知及事务；不包含请假或工单规则。"""
from sqlalchemy import insert, select, update
from app.models import common as t


class StudentRepository:
    def __init__(self, db):
        self.db = db

    def get_student(self, student_id, *, lock=False):
        query = select(t.student_profile).where(t.student_profile.c.student_id == student_id)
        if lock:
            query = query.with_for_update()
        return self.db.execute(query).mappings().first()

    def find_operation(self, operation_key):
        return self.db.execute(select(t.operation_log).where(
            t.operation_log.c.operation_key == operation_key
        )).mappings().first()

    def create_operation(self, values):
        self.db.execute(insert(t.operation_log).values(**values))

    def queue_notification(self, values):
        self.db.execute(insert(t.business_notification).values(**values))

    def complete_operation(self, operation_key, values):
        self.db.execute(update(t.operation_log).where(
            t.operation_log.c.operation_key == operation_key
        ).values(**values))

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()
