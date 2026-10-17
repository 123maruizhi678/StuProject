"""学生请假读写；只使用固定SQLAlchemy表和参数。"""
from sqlalchemy import insert, or_, select, update

from app.models import common as t
from .student_repository import StudentRepository

class StudentLeaveRepository(StudentRepository):

    def find_teacher(self, student_id, now):
        b, e = t.student_staff_binding, t.employee
        rows = self.db.execute(select(b.c.employee_id, e.c.role_codes).join(
            e, e.c.employee_id == b.c.employee_id
        ).where(
            b.c.student_id == student_id, b.c.relation_type == "class_teacher",
            b.c.status == "active", e.c.status == "active", b.c.valid_from <= now,
            b.c.is_primary.is_(True),
            e.c.department_id == select(t.student_profile.c.department_id).where(t.student_profile.c.student_id==student_id).scalar_subquery(),
            or_(b.c.valid_to.is_(None), b.c.valid_to > now),
        ).order_by(b.c.is_primary.desc(), b.c.binding_id)).mappings()
        for row in rows:
            if isinstance(row["role_codes"], list) and "teacher" in row["role_codes"]:
                return row["employee_id"]
        return None

    def create_application(self, values):
        result = self.db.execute(insert(t.student_admin_service).values(**values))
        return result.inserted_primary_key[0]
