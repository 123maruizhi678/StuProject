"""学生请假业务：可信身份、Dify分析、分派与原子写入。"""
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.repositories.student.student_leave_repository import StudentLeaveRepository
from app.repositories.student.student_schema import require_student_schema
from app.clients.student.student_leave_dify import StudentLeaveDifyError


from app.services.student.student_common import (StudentBusinessService, StudentBusinessError as LeaveError, digest, utc_naive)


class StudentLeaveService(StudentBusinessService):
    def __init__(self, db, workflow):
        self.repository = StudentLeaveRepository(db)
        self.workflow = workflow

    def submit(self, account, request_key, payload):
        start, end = utc_naive(payload.leave_start_at), utc_naive(payload.leave_end_at)
        parameters_hash = digest({
            "leave_content": payload.leave_content, "leave_type": payload.leave_type,
            "leave_start_at": start.isoformat(), "leave_end_at": end.isoformat(),
        })
        if payload.generate_ai_summary:
            parameters_hash = digest([parameters_hash, "generate_ai_summary"])
        operation_key = digest(["student", account.student_id, "student.leave.submit", request_key])
        repository = self.repository
        try:
            require_student_schema(repository.db, "leave")
            student_id = self._student(account)
            receipt = self._replay(operation_key, parameters_hash)
            repository.rollback()  # 结束预检读事务；不持有数据库锁等待大模型。
            if receipt is not None:
                return receipt
            analysis, ai_status = None, "not_requested"
            if payload.generate_ai_summary:
                try:
                    analysis = self.workflow.analyze_leave(student_id, payload)
                    ai_status = "available"
                except StudentLeaveDifyError:
                    ai_status = "unavailable"  # AI 增强失败，仍保留原始请假申请。

            # 外部调用之后重新校验档案与幂等，防止期间账号变化或并发重试。
            if self._student(account, lock=True) != student_id:
                raise LeaveError(403, "账号关联发生变化，请重新提交")
            receipt = self._replay(operation_key, parameters_hash)
            if receipt is not None:
                repository.rollback()
                return receipt
            now = utc_naive(datetime.now(timezone.utc))
            reviewer_id = repository.find_teacher(student_id, now)
            repository.create_operation(dict(
                operation_key=operation_key, student_id=student_id,
                action_code="student.leave.submit", entity_type="student_admin_service",
                request_key=request_key, parameters_hash=parameters_hash,
                operation_status="processing", row_version=1, created_at=now, updated_at=now,
            ))
            apply_id = repository.create_application(dict(
                student_id=student_id, apply_type="leave", apply_content=payload.leave_content,
                approval_status="pending",
                edu_related_data={"leave_type": payload.leave_type, "ai_status": ai_status,
                                  "ai_analysis": analysis.model_dump() if analysis else None},
                leave_start_at=start, leave_end_at=end, reviewer_id=reviewer_id,
                request_key=request_key, request_hash=parameters_hash, row_version=1,
                created_at=now, updated_at=now,
            ))
            if reviewer_id is not None:
                from .student_service import StudentService
                StudentService(repository.db).notify('student_admin_service',apply_id,'leave.submitted','有新的学生请假待审批',employee_id=reviewer_id,version=1)
            receipt = dict(
                apply_id=apply_id, approval_status="pending", reviewer_id=reviewer_id,
                row_version=1, assignment_pending=reviewer_id is None,
                notification_queued=reviewer_id is not None, ai_status=ai_status,
                ai_analysis=analysis.model_dump() if analysis else None,
            )
            repository.complete_operation(operation_key, dict(
                entity_id=apply_id, operation_status="succeeded", result_reference=receipt,
                after_data={"approval_status": "pending", "reviewer_id": reviewer_id,
                            "ai_status": ai_status,
                            "workflow_run_id": analysis.workflow_run_id if analysis else None},
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
                raise LeaveError(409, "请假记录发生关联或重复冲突，请核对后重试") from None
            finally:
                repository.rollback()
        except Exception:
            repository.rollback()
            raise

    def decide(self, actor, key, apply_id, body):
        """企业表单和智能指令复用同一固定审批实现。"""
        from .student_service import StudentService
        return StudentService(self.repository.db)._decide_leave(actor,key,apply_id,body)
