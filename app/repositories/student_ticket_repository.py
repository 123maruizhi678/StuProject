"""本人工单固定查询和写入；任何模型文本均作为数据参数处理。"""
from sqlalchemy import insert, select

from app.models import student_leave as shared
from app.models import student_ticket as t
from app.repositories.student_leave_repository import StudentLeaveRepository


class StudentTicketRepository(StudentLeaveRepository):
    def get_department(self, department_id, *, lock=False):
        query = select(shared.org_department).where(shared.org_department.c.department_id == department_id)
        if lock:
            query = query.with_for_update()
        return self.db.execute(query).mappings().first()

    def create_ticket(self, values):
        return self.db.execute(insert(t.service_ticket).values(**values)).inserted_primary_key[0]

    def create_record(self, values):
        self.db.execute(insert(t.service_ticket_record).values(**values))

    def get_owned_ticket(self, student_id, ticket_id):
        return self.db.execute(select(t.service_ticket).where(
            t.service_ticket.c.ticket_id == ticket_id,
            t.service_ticket.c.student_id == student_id,
        )).mappings().first()

    def list_owned(self, student_id, limit, before_id=None):
        query = select(t.service_ticket).where(t.service_ticket.c.student_id == student_id)
        if before_id is not None:
            query = query.where(t.service_ticket.c.ticket_id < before_id)
        return self.db.execute(query.order_by(t.service_ticket.c.ticket_id.desc()).limit(limit + 1)).mappings().all()

    def list_visible_records(self, ticket_id, limit, after_id=0):
        return self.db.execute(select(t.service_ticket_record).where(
            t.service_ticket_record.c.ticket_id == ticket_id,
            t.service_ticket_record.c.visibility == "student_visible",
            t.service_ticket_record.c.ticket_record_id > after_id,
        ).order_by(t.service_ticket_record.c.ticket_record_id).limit(limit + 1)).mappings().all()
