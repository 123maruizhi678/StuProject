"""本地联调的固定查询适配器；只读参数化SQL，不生成、不执行AI SQL。"""

from datetime import datetime
from sqlalchemy import select, func
from app.core.response import BusinessException
from app.models import student_shared as shared
from app.services.student_clients import StudentQueryClient, QUERY_FIELDS
from app.services.student_service import (
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
                or row["follower_id"] not in (None, actor_id)
                or (
                    not service.bound(actor_id, student_id)
                    and actor_id != service.fallback_teacher()
                )
            ):
                raise BusinessException("无权查看该预警", 403)
            rows, total = [dict(row)], 1
        else:
            tables = {
                "leave": shared.student_leave_request,
                "tickets": shared.service_ticket,
                "ticket_records": shared.service_ticket_record,
                "academic": events,
                "progress": progress,
                "reminders": reminders,
                "notifications": shared.business_notification,
            }
            table = tables[scene]
            source, columns = table, [
                table.c[name] for name in sorted(QUERY_FIELDS[scene])
            ]
            conditions = [table.c.student_id == subject["id"]]
            if scene == "ticket_records":
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
                    "leave": "leave_request_id",
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
                    .order_by(pk.desc())
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
        result = super().query(*args, **kwargs)
        return {**result, "query_backend": "local_fixed_sql"}
