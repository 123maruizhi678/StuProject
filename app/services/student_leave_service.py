"""学生请假业务：可信身份、Dify分析、分派与原子写入。"""
from datetime import datetime, timezone
import hashlib
import json

from sqlalchemy.exc import IntegrityError

from app.repositories.student_leave_repository import StudentLeaveRepository


class LeaveError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


def digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def utc_naive(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class StudentLeaveService:
    def __init__(self, db, workflow):
        self.repository = StudentLeaveRepository(db)
        self.workflow = workflow

    def _student(self, account, *, lock=False):
        if account.identity_type != "student" or not account.student_id:
            raise LeaveError(403, "此功能仅限学生本人")
        row = self.repository.get_student(account.student_id, lock=lock)
        if not row or row["is_archived"] or row["status"] in (
            "disabled", "inactive", "withdrawn", "suspended"
        ):
            raise LeaveError(403, "学生档案不可用")
        return account.student_id

    def _replay(self, operation_key, parameters_hash):
        row = self.repository.find_operation(operation_key)
        if row is None:
            return None
        if row["parameters_hash"] != parameters_hash:
            raise LeaveError(409, "同一幂等键不能提交不同的请假内容")
        if row["operation_status"] != "succeeded":
            raise LeaveError(409, "请求正在处理，请稍后核实")
        return row["result_reference"]

    def submit(self, account, request_key, payload):
        start, end = utc_naive(payload.leave_start_at), utc_naive(payload.leave_end_at)
        parameters_hash = digest({
            "leave_content": payload.leave_content, "leave_type": payload.leave_type,
            "leave_start_at": start.isoformat(), "leave_end_at": end.isoformat(),
        })
        operation_key = digest(["student", account.student_id, "student.leave.submit", request_key])
        repository = self.repository
        try:
            student_id = self._student(account)
            receipt = self._replay(operation_key, parameters_hash)
            repository.rollback()  # 结束预检读事务；不持有数据库锁等待大模型。
            if receipt is not None:
                return receipt
            analysis = self.workflow.analyze_leave(student_id, payload)

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
                edu_related_data={"leave_type": payload.leave_type, "ai_analysis": analysis.model_dump()},
                leave_start_at=start, leave_end_at=end, reviewer_id=reviewer_id,
                request_key=request_key, request_hash=parameters_hash, row_version=1,
                created_at=now, updated_at=now,
            ))
            if reviewer_id is not None:
                repository.queue_notification(dict(
                    entity_type="student_admin_service", entity_id=apply_id,
                    event_code="student.leave.submitted", employee_id=reviewer_id,
                    channel="in_app", title="有新的学生请假待审批",
                    content="请在授权的请假待办中查看并处理。",
                    dedupe_key=f"student.leave.submitted:{apply_id}:{reviewer_id}:in_app",
                    delivery_status="pending", attempt_count=0, row_version=1,
                    created_at=now, updated_at=now,
                ))
            receipt = dict(
                apply_id=apply_id, approval_status="pending", reviewer_id=reviewer_id,
                row_version=1, assignment_pending=reviewer_id is None,
                notification_queued=reviewer_id is not None, ai_analysis=analysis.model_dump(),
            )
            repository.complete_operation(operation_key, dict(
                entity_id=apply_id, operation_status="succeeded", result_reference=receipt,
                after_data={"approval_status": "pending", "reviewer_id": reviewer_id,
                            "workflow_run_id": analysis.workflow_run_id},
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
