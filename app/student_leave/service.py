"""只处理提交请假，不签发、解析或校验登录 JWT。"""
from datetime import datetime, timezone
import hashlib
import json

from sqlalchemy import insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from . import tables as t


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
    def __init__(self, db):
        self.db = db

    def _student(self, account):
        # account 来自组长依赖；这里仅做学生业务身份与档案检查。
        if account.identity_type != "student" or not account.student_id:
            raise LeaveError(403, "此功能仅限学生本人")
        row = self.db.execute(select(t.student_profile).where(
            t.student_profile.c.student_id == account.student_id
        ).with_for_update()).mappings().first()
        if not row or row["is_archived"] or row["status"] in (
            "disabled", "inactive", "withdrawn", "suspended"
        ):
            raise LeaveError(403, "学生档案不可用")
        return account.student_id

    def _teacher(self, student_id, now):
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

    def _replay(self, operation_key, parameters_hash):
        row = self.db.execute(select(t.operation_log).where(
            t.operation_log.c.operation_key == operation_key
        )).mappings().first()
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
        try:
            student_id = self._student(account)
            receipt = self._replay(operation_key, parameters_hash)
            if receipt is not None:
                self.db.rollback()
                return receipt
            now = utc_naive(datetime.now(timezone.utc))
            reviewer_id = self._teacher(student_id, now)
            self.db.execute(insert(t.operation_log).values(
                operation_key=operation_key, student_id=student_id,
                action_code="student.leave.submit", entity_type="student_admin_service",
                request_key=request_key, parameters_hash=parameters_hash,
                operation_status="processing", row_version=1, created_at=now, updated_at=now,
            ))
            created = self.db.execute(insert(t.student_admin_service).values(
                student_id=student_id, apply_type="leave", apply_content=payload.leave_content,
                approval_status="pending", edu_related_data={"leave_type": payload.leave_type},
                leave_start_at=start, leave_end_at=end, reviewer_id=reviewer_id,
                request_key=request_key, request_hash=parameters_hash, row_version=1,
                created_at=now, updated_at=now,
            ))
            apply_id = created.inserted_primary_key[0]
            if reviewer_id is not None:
                self.db.execute(insert(t.business_notification).values(
                    entity_type="student_admin_service", entity_id=apply_id,
                    event_code="student.leave.submitted", employee_id=reviewer_id,
                    channel="in_app", title="有新的学生请假待审批",
                    content="请在授权的请假待办中查看并处理。",
                    dedupe_key=f"student.leave.submitted:{apply_id}:{reviewer_id}:in_app",
                    delivery_status="pending", attempt_count=0, row_version=1,
                    created_at=now, updated_at=now,
                ))
            receipt = {
                "apply_id": apply_id, "approval_status": "pending", "reviewer_id": reviewer_id,
                "row_version": 1, "assignment_pending": reviewer_id is None,
                "notification_queued": reviewer_id is not None,
            }
            self.db.execute(update(t.operation_log).where(
                t.operation_log.c.operation_key == operation_key
            ).values(
                entity_id=apply_id, operation_status="succeeded", result_reference=receipt,
                after_data={"approval_status": "pending", "reviewer_id": reviewer_id},
                updated_at=now, finished_at=now,
            ))
            self.db.commit()
            return receipt
        except IntegrityError:
            self.db.rollback()
            try:
                self._student(account)
                receipt = self._replay(operation_key, parameters_hash)
                if receipt is not None:
                    return receipt
                raise LeaveError(409, "请假记录发生关联或重复冲突，请核对后重试") from None
            finally:
                self.db.rollback()
        except Exception:
            self.db.rollback()
            raise
