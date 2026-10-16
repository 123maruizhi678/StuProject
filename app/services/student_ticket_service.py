"""学生提交与查询工单；人工处理、分派、解决由企业模块负责。"""
from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy.exc import IntegrityError

from app.clients.student_ticket_dify import StudentTicketDifyError
from app.config import student_ticket_settings
from app.repositories.student_schema import require_student_schema
from app.repositories.student_ticket_repository import StudentTicketRepository
from app.schemas.student_ticket import TicketReceipt
from app.services.student_common import (StudentBusinessError as LeaveError, StudentBusinessService, digest, utc_naive)


class StudentTicketService(StudentBusinessService):
    def __init__(self, db, workflow=None, config=None):
        self.repository = StudentTicketRepository(db)
        self.workflow = workflow
        self.config = config or student_ticket_settings

    def _department(self, student_id, *, lock=False):
        student = self.repository.get_student(student_id)
        department_id = self.config.STUDENT_TICKET_DEPARTMENT_ID or student["department_id"]
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
                analysis = self.workflow.summarize(student_id, payload)
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
            response_due = now + timedelta(hours=self.config.STUDENT_TICKET_RESPONSE_HOURS)
            resolution_due = now + timedelta(hours=max(self.config.STUDENT_TICKET_RESOLUTION_HOURS,
                                                      self.config.STUDENT_TICKET_RESPONSE_HOURS))
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
                            "ai_status": receipt["ai_status"], "ai_analysis": receipt["ai_analysis"]},
                updated_at=now, finished_at=now,
            ))
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
