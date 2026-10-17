"""学生提交与查询工单；人工处理、分派、解决由企业模块负责。"""
from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, insert, update
from app.models import common as shared
from app.models.student.student_types import utcnow
from app.core.common.response import BusinessException
from app.schemas.student.student import as_utc
from app.services.student.student_policy import ticket_cycle

from app.clients.student.student_ticket_dify import StudentTicketDifyError
from app.config import settings as student_ticket_settings
from app.repositories.student.student_schema import require_student_schema
from app.repositories.student.student_ticket_repository import StudentTicketRepository
from app.schemas.student.student_ticket import TicketReceipt
from app.services.student.student_common import (StudentBusinessError as LeaveError, StudentBusinessService, digest, utc_naive)


class StudentTicketService(StudentBusinessService):
    def __init__(self, db, workflow=None, config=None):
        self.repository = StudentTicketRepository(db)
        self.workflow = workflow
        self.config = config or student_ticket_settings

    def _department(self, student_id, *, lock=False):
        student = self.repository.get_student(student_id)
        department_id = student["department_id"]
        department = self.repository.get_department(department_id, lock=lock)
        if not department or department["status"] != "active":
            raise LeaveError(409, "投诉受理部门不存在或已停用，请联系维护学生档案和部门配置")
        return department_id

    def submit(self, account, request_key, payload):
        repository = self.repository
        operation_key = digest(["student", account.student_id, "student.ticket.submit", request_key])
        parameters_hash = digest(payload.model_dump())
        try:
            require_student_schema(repository.db, "ticket")
            student_id = self._student(account)
            receipt = self._replay(operation_key, parameters_hash)
            if receipt is not None:
                repository.rollback()
                return receipt
            self._department(student_id)
            repository.rollback()  # Dify请求不占用数据库事务和行锁。
            analysis = None
            try:
                analysis = self.workflow.summarize(student_id, payload) if self.workflow else None
            except StudentTicketDifyError:
                pass  # 如实保存原文，ai_summary=NULL；不伪造本地模型结果。
            if self._student(account, lock=True) != student_id:
                raise LeaveError(403, "账号关联发生变化，请重新提交")
            receipt = self._replay(operation_key, parameters_hash)
            if receipt is not None:
                repository.rollback()
                return receipt
            department_id = self._department(student_id, lock=True)
            now = utc_naive(datetime.now(timezone.utc))
            from .student_policy import ticket_cycle
            cycle = ticket_cycle(payload.ticket_type,'normal',now,1)
            response_due=datetime.fromisoformat(cycle['response_due_at'].rstrip('Z'))
            resolution_due=datetime.fromisoformat(cycle['resolution_due_at'].rstrip('Z'))
            ticket_no = "ST" + uuid.uuid4().hex[:30]
            repository.create_operation(dict(
                operation_key=operation_key, student_id=student_id, action_code="student.ticket.submit",
                entity_type="service_ticket", request_key=request_key, parameters_hash=parameters_hash,
                operation_status="processing", row_version=1, created_at=now, updated_at=now,
            ))
            ticket_id = repository.create_ticket(dict(
                ticket_no=ticket_no, student_id=student_id, ticket_type=payload.ticket_type,
                category_code=payload.category_code, content=payload.content,
                ai_summary=analysis.summary if analysis else None,
                priority="normal", employee_id=None, handling_department_id=department_id,
                status="open", response_due_at=response_due, resolution_due_at=resolution_due,
                reopen_count=0, row_version=1, created_at=now, updated_at=now,
            ))
            repository.create_record(dict(
                ticket_id=ticket_id, record_type="submitted", student_id=student_id,
                content="学生已提交，等待受理部门分派。", visibility="student_visible", to_status="open",
                cycle_no=1, record_key=f"student.ticket.submitted:{operation_key}", created_at=now,
            ))
            # 使用回执模型统一时间格式后再存JSON，确保第一次与重试完全一致。
            receipt = TicketReceipt(
                ticket_id=ticket_id, ticket_no=ticket_no, status="open", category_code=payload.category_code,
                handling_department_id=department_id, row_version=1,
                ai_status="available" if analysis else "unavailable", ai_analysis=analysis,
                response_due_at=response_due, resolution_due_at=resolution_due,
            ).model_dump(mode="json")
            repository.complete_operation(operation_key, dict(
                entity_id=ticket_id, operation_status="succeeded", result_reference=receipt,
                after_data={"status": "open", "handling_department_id": department_id,
                            "ai_status": receipt["ai_status"], "ai_analysis": receipt["ai_analysis"], "cycle_policy":cycle},
                updated_at=now, finished_at=now,
            ))
            from .student_service import StudentService
            from app.models.common import employee
            from sqlalchemy import select
            managers=repository.db.execute(select(employee).where(employee.c.department_id==department_id,employee.c.status=='active')).mappings().all()
            for manager in managers:
                if 'manager' in (manager['role_codes'] or []):
                    StudentService(repository.db).notify('service_ticket',ticket_id,'enterprise.ticket.unassigned','有学生反馈待分派',employee_id=manager['employee_id'])
            repository.commit()
            return receipt
        except IntegrityError:
            repository.rollback()
            try:
                if self._student(account) != student_id:
                    raise LeaveError(403, "账号关联发生变化，请重新提交")
                receipt = self._replay(operation_key, parameters_hash)
                if receipt is not None:
                    return receipt
                raise LeaveError(409, "工单发生关联或重复冲突，请运行共享表检查并核对资料") from None
            finally:
                repository.rollback()
        except Exception:
            repository.rollback()
            raise

    def list_own(self, account, limit, before_id=None):
        student_id = self._student(account)
        rows = self.repository.list_owned(student_id, limit, before_id)
        return {"items": rows[:limit], "next_before_id": rows[limit-1]["ticket_id"] if len(rows) > limit else None}

    def detail(self, account, ticket_id):
        student_id = self._student(account)
        row = self.repository.get_owned_ticket(student_id, ticket_id)
        if row is None:
            raise LeaveError(404, "工单不存在或无权访问")
        return row

    def records(self, account, ticket_id, limit, after_id=0):
        self.detail(account, ticket_id)
        rows = self.repository.list_visible_records(ticket_id, limit, after_id)
        return {"items": rows[:limit], "next_after_id": rows[limit-1]["ticket_record_id"] if len(rows) > limit else None}

    def _ticket_record(self, entity_id, actor, opkey, kind, content, status, cycle):
        from .student_service import StudentService
        service = StudentService(self.repository.db)
        service.db.execute(
            insert(shared.service_ticket_record).values(
                ticket_id=entity_id,
                student_id=actor.actor_id,
                record_type=kind,
                content=content,
                visibility="student_visible",
                to_status=status,
                cycle_no=cycle,
                record_key=opkey,
                created_at=utcnow(),
            )
        )

    def reply(self, actor, key, entity_id, body):
        from .student_service import StudentService
        service = StudentService(self.repository.db)
        def apply(opkey):
            t = shared.service_ticket
            row = service._load(t, entity_id, actor)
            if row["status"] == "closed":
                raise BusinessException("工单已关闭", 409)
            version = service._version_update(t, row, body.expected_version, {})
            self._ticket_record(
                entity_id,
                actor,
                opkey,
                "student_reply",
                body.content,
                row["status"],
                row["reopen_count"] + 1,
            )
            if row['employee_id']:
                service.notify('service_ticket',entity_id,'enterprise.ticket.student_reply','学生补充了反馈内容',employee_id=row['employee_id'],version=version)
            return (
                {"ticket_id": entity_id, "row_version": version},
                entity_id,
                {"row_version": version},
            )

        return service._write(
            actor, "ticket.reply", key, [entity_id, body.model_dump()], apply
        )

    def confirm(self, actor, key, entity_id, body):
        from .student_service import StudentService
        service = StudentService(self.repository.db)
        def apply(opkey):
            t = shared.service_ticket
            row = service._load(t, entity_id, actor)
            if row["status"] != "awaiting_student":
                raise BusinessException("工单尚未进入学生确认阶段", 409)
            now = utcnow()
            status = "closed" if body.resolved else "reopened"
            values = {"status": status, "closed_at": now if body.resolved else None}
            if not body.resolved:
                from .student_policy import ticket_cycle
                cycle=ticket_cycle(row['ticket_type'],row['priority'],now,row['reopen_count']+2)
                values.update(
                    reopen_count=row["reopen_count"] + 1,
                                        resolved_at=None,
                    solution=None,
                    satisfaction_score=None,
                    resolution_due_at=datetime.fromisoformat(cycle["resolution_due_at"].rstrip("Z")),
                )
            version = service._version_update(t, row, body.expected_version, values)
            if not body.resolved:
                service.db.execute(update(shared.operation_log).where(shared.operation_log.c.operation_key==opkey).values(before_data={'cycle_policy':cycle}))
            self._ticket_record(
                entity_id,
                actor,
                opkey,
                "confirm" if body.resolved else "reopen",
                body.comment,
                status,
                row["reopen_count"] + (1 if body.resolved else 2),
            )
            if row["employee_id"]:
                service.notify(
                    "service_ticket",
                    entity_id,
                    "ticket." + status,
                    "学生已反馈处理结果",
                    employee_id=row["employee_id"],
                    version=version,
                )
            return (
                {
                    "ticket_id": entity_id,
                    "process_status": status,
                    "row_version": version,
                },
                entity_id,
                {"status": status},
            )

        return service._write(
            actor, "ticket.confirm", key, [entity_id, body.model_dump()], apply
        )

    def rate(self, actor, key, entity_id, body):
        from .student_service import StudentService
        service = StudentService(self.repository.db)
        def apply(opkey):
            t = shared.service_ticket
            row = service._load(t, entity_id, actor)
            if row["status"] != "closed":
                raise BusinessException("请先确认工单已解决，再评价", 409)
            version = service._version_update(
                t,
                row,
                body.expected_version,
                {"satisfaction_score": body.satisfaction_score},
            )
            self._ticket_record(
                entity_id,
                actor,
                opkey,
                "rating",
                str(body.satisfaction_score),
                "closed",
                row["reopen_count"] + 1,
            )
            return (
                {"ticket_id": entity_id, "row_version": version},
                entity_id,
                {"satisfaction_score": body.satisfaction_score},
            )

        return service._write(
            actor, "ticket.rate", key, [entity_id, body.model_dump()], apply
        )
