"""本地联调的固定查询适配器；只读参数化SQL，不生成、不执行AI SQL。"""

from datetime import datetime
from sqlalchemy import select, func
from app.core.common.response import BusinessException
from app.models import common as shared
from app.clients.student.student_clients import StudentQueryClient, QUERY_FIELDS
from app.services.student.student_service import (
    StudentService,
    events,
    progress,
    reminders,
    warnings,
    public_time,
)


class LocalStudentQueryClient(StudentQueryClient):
    def __init__(self, db):
        self.db = db

    def _request(self, payload):
        scene, subject, filters = (
            payload["scenario"],
            payload["subject"],
            payload["filters"],
        )
        if scene == "mental_warning":
            actor_id, student_id = subject["id"], filters["student_id"]
            service = StudentService(self.db)
            row = service._load(warnings, filters["warning_id"], lock=False)
            if (
                row["student_id"] != student_id
                or row["follower_id"] != actor_id
                or (
                    not service.bound(actor_id, student_id)
                    and actor_id != service.fallback_teacher()
                )
            ):
                raise BusinessException("记录不存在", 404)
            rows, total = [dict(row)], 1
        else:
            tables = {
                "scores": shared.student_score,
                "leave": shared.student_admin_service,
                "tickets": shared.service_ticket,
                "ticket_records": shared.service_ticket_record,
                "academic": events,
                "progress": progress,
                "reminders": reminders,
                "notifications": shared.business_notification,
            }
            table = tables[scene]
            source, columns = table, [
                (table.c.id.label("apply_id") if scene=="leave" and name=="apply_id" else table.c.edu_related_data["leave_type"].as_string().label("leave_type") if scene=="leave" and name=="leave_type" else table.c[name]) for name in sorted(QUERY_FIELDS[scene])
            ]
            conditions = [table.c.student_id == subject["id"]]
            if scene == "scores":
                conditions += [table.c.status == "valid"]
            elif scene == "leave":
                conditions += [table.c.apply_type == "leave"]
                if filters.get("approval_status"):
                    conditions.append(table.c.approval_status==filters["approval_status"])
            elif scene == "ticket_records":
                ticket = shared.service_ticket
                source = table.join(ticket, table.c.ticket_id == ticket.c.ticket_id)
                columns = [c for c in columns if c.name != "student_id"] + [
                    ticket.c.student_id
                ]
                conditions = [
                    ticket.c.student_id == subject["id"],
                    table.c.visibility == "student_visible",
                ]
            elif scene == "notifications":
                conditions += [
                    table.c.delivery_status == "sent",
                    table.c.channel == "in_app",
                ]
            entity_id = filters.get("entity_id")
            if entity_id is not None:
                column = {
                    "leave": "id",
                    "scores": "score_id",
                    "tickets": "ticket_id",
                    "ticket_records": "ticket_id",
                    "notifications": "notification_id",
                }.get(scene, "id")
                conditions.append(table.c[column] == entity_id)
            total = self.db.scalar(
                select(func.count()).select_from(source).where(*conditions)
            )
            pk = next(iter(table.primary_key.columns))
            rows = [
                dict(row)
                for row in self.db.execute(
                    select(*columns)
                    .select_from(source)
                    .where(*conditions)
                    .order_by(*([table.c.term_code, table.c.course_code, table.c.score_id] if scene == "scores" else [pk.desc()]))
                    .limit(payload["limit"])
                    .offset(payload["offset"])
                ).mappings()
            ]
        rows = [
            {
                k: public_time(v) if isinstance(v, datetime) else v
                for k, v in row.items()
            }
            for row in rows
        ]
        return {
            "code": 0,
            "data": {
                "contract_version": "student-v1",
                "subject_id": subject["id"],
                "scenario": scene,
                "rows": rows,
                "total": total,
            },
        }

    def query(self, *args, **kwargs):
        actor, scene = args[:2]
        if scene == 'courses':
            from app.models.enterprise import enterprise_course as course, enterprise_student_course as enrollment
            limit, offset = kwargs.get('limit', 20), kwargs.get('offset', 0)
            source = enrollment.join(course, enrollment.c.course_code == course.c.course_code)
            conditions = [enrollment.c.student_id == actor.actor_id, enrollment.c.status == 'active', course.c.status == 'active']
            rows = self.db.execute(select(enrollment.c.course_code, course.c.course_name,
                enrollment.c.term_code, enrollment.c.status).select_from(source).where(*conditions)
                .order_by(enrollment.c.term_code, enrollment.c.course_code).limit(limit).offset(offset)).mappings()
            return {'items': [dict(row) for row in rows],
                    'total': self.db.scalar(select(func.count()).select_from(source).where(*conditions)),
                    'limit': limit, 'offset': offset, 'query_backend': 'local_fixed_sql'}
        result = super().query(*args, **kwargs)
        return {**result, "query_backend": "local_fixed_sql"}
