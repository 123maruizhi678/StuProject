"""学生业务固定写入规则；所有变更、幂等回执和通知在同一数据库事务中保存。"""

import hashlib
import json
from datetime import timedelta, datetime
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import select, insert, update, and_, or_
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.core.response import BusinessException
from app.core.student_auth import Principal
from app.models import student_shared as shared
from app.models.student import (
    MentalHealthProfile,
    MentalWarning,
    StudentAcademicEvent,
    StudentAcademicReminder,
    StudentApplicationProgress,
)
from app.models.student_types import utcnow
from app.schemas.student import as_utc

profiles = MentalHealthProfile.__table__
warnings = MentalWarning.__table__
events = StudentAcademicEvent.__table__
reminders = StudentAcademicReminder.__table__
progress = StudentApplicationProgress.__table__


def digest(value):
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def reminder_generation(row):
    # DATETIME(6)更新时间是提醒设置代次；任务状态更新必须保留该时间。
    return digest([row["id"], row["updated_at"].isoformat(timespec="microseconds")])[
        :16
    ]


def next_setting_time(row=None):
    now = utcnow()
    return max(now, row["updated_at"] + timedelta(microseconds=1)) if row else now


def row_id(table):
    return next(iter(table.primary_key.columns))


def public_time(value):
    return value.isoformat(timespec="milliseconds") + "Z" if value else None


def public_row(row):
    return {k: public_time(v) if isinstance(v, datetime) else v for k, v in row.items()}


class StudentService:
    def __init__(self, db):
        self.db = db

    def student(self, actor):
        if actor.actor_type != "student":
            raise BusinessException("此操作仅限学生本人", 403)
        return self.student_record(actor.actor_id)

    def student_record(self, student_id):
        row = (
            self.db.execute(
                select(shared.student_profile).where(
                    shared.student_profile.c.student_id == student_id
                )
            )
            .mappings()
            .first()
        )
        if (
            not row
            or row["is_archived"]
            or row["status"] in ("disabled", "inactive", "withdrawn", "suspended")
        ):
            raise BusinessException("学生身份不可用", 403)
        return row

    def employee(self, actor):
        if actor.actor_type != "employee":
            raise BusinessException("需要员工身份", 403)
        row = (
            self.db.execute(
                select(shared.employee).where(
                    shared.employee.c.employee_id == actor.actor_id
                )
            )
            .mappings()
            .first()
        )
        if (
            not row
            or row["status"] != "active"
            or "teacher" not in (row["role_codes"] or [])
        ):
            raise BusinessException("需要有效的老师权限", 403)
        return row

    def bound(self, employee_id, student_id):
        t = shared.student_staff_binding
        now = utcnow()
        return (
            self.db.execute(
                select(t.c.binding_id).where(
                    t.c.student_id == student_id,
                    t.c.employee_id == employee_id,
                    t.c.relation_type == "class_teacher",
                    t.c.status == "active",
                    t.c.valid_from <= now,
                    or_(t.c.valid_to.is_(None), t.c.valid_to > now),
                )
            ).first()
            is not None
        )

    def responsible_teacher(self, student_id, relation="class_teacher"):
        t, e = shared.student_staff_binding, shared.employee
        now = utcnow()
        rows = self.db.execute(
            select(t.c.employee_id, e.c.role_codes)
            .join(e, t.c.employee_id == e.c.employee_id)
            .where(
                t.c.student_id == student_id,
                t.c.relation_type == relation,
                t.c.status == "active",
                e.c.status == "active",
                t.c.valid_from <= now,
                or_(t.c.valid_to.is_(None), t.c.valid_to > now),
            )
            .order_by(t.c.is_primary.desc(), t.c.binding_id)
        ).mappings()
        for row in rows:
            if "teacher" in (row["role_codes"] or []) or relation == "service_advisor":
                return row["employee_id"]
        return None

    def fallback_teacher(self):
        if settings.STUDENT_FALLBACK_EMPLOYEE_ID is None:
            return None
        e = shared.employee
        row = (
            self.db.execute(
                select(e.c.employee_id, e.c.role_codes).where(
                    e.c.employee_id == settings.STUDENT_FALLBACK_EMPLOYEE_ID,
                    e.c.status == "active",
                )
            )
            .mappings()
            .first()
        )
        return (
            row["employee_id"]
            if row and "teacher" in (row["role_codes"] or [])
            else None
        )

    def _load(self, table, entity_id, actor=None, *, lock=True):
        statement = select(table).where(row_id(table) == entity_id)
        if lock:
            statement = statement.with_for_update()
        row = self.db.execute(statement).mappings().first()
        if not row or (actor is not None and row["student_id"] != actor.actor_id):
            raise BusinessException("记录不存在", 404)
        return row

    def _version_update(self, table, row, expected, values):
        version_column = (
            table.c.version if "version" in table.c else table.c.row_version
        )
        if row[version_column.name] != expected:
            raise BusinessException("数据已更新，请刷新后重试", 409)
        values = {**values, version_column.name: expected + 1, "updated_at": utcnow()}
        result = self.db.execute(
            update(table)
            .where(row_id(table) == row[row_id(table).name], version_column == expected)
            .values(**values)
        )
        if result.rowcount != 1:
            raise BusinessException("并发更新冲突，请刷新后重试", 409)
        return expected + 1

    def notify(
        self,
        entity_type,
        entity_id,
        event,
        title,
        *,
        student_id=None,
        employee_id=None,
        version=1
    ):
        if (student_id is None) == (employee_id is None):
            raise ValueError("通知必须且只能指定一种接收人")
        event = "student." + event
        key = digest(
            [entity_type, entity_id, event, student_id, employee_id, version, "in_app"]
        )
        t = shared.business_notification
        if self.db.execute(
            select(t.c.notification_id).where(t.c.dedupe_key == key)
        ).first():
            return
        self.db.execute(
            insert(t).values(
                entity_type=entity_type,
                entity_id=entity_id,
                event_code=event,
                student_id=student_id,
                employee_id=employee_id,
                channel="in_app",
                title=title,
                content="请进入对应业务查看详情。",
                dedupe_key=key,
                delivery_status="pending",
                attempt_count=0,
                row_version=1,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
        )

    def _write(self, actor, action, key, parameters, handler):
        """唯一操作键处理并发重试；失败时业务和通知一起回滚。"""
        op = shared.operation_log
        operation_key = digest(
            [actor.key, "action.confirm" if key.startswith("confirm:") else action, key]
        )
        parameter_hash = digest([action, parameters])

        def replay(row):
            if row["parameters_hash"] != parameter_hash:
                raise BusinessException("相同请求键不能用于不同内容", 409)
            if row["operation_status"] != "succeeded":
                raise BusinessException("请求正在处理或需要核实", 409)
            return row["result_reference"]

        try:
            if action in (
                "mental.ack",
                "mental.follow",
                "mental.close",
                "leave.decide",
                "employee.notification.read",
            ):
                self.employee(actor)
            elif action in ("academic.sync", "progress.sync"):
                actor.require_scope("student:sync")
            else:
                self.student(actor)
            existing = (
                self.db.execute(select(op).where(op.c.operation_key == operation_key))
                .mappings()
                .first()
            )
            if existing:
                result = replay(existing)
                self.db.rollback()
                return result
            result = self.db.execute(
                insert(op).values(
                    operation_key=operation_key,
                    student_id=(
                        actor.actor_id if actor.actor_type == "student" else None
                    ),
                    employee_id=(
                        actor.actor_id if actor.actor_type == "employee" else None
                    ),
                    service_code=(
                        actor.service_code if actor.actor_type == "service" else None
                    ),
                    action_code=action,
                    entity_type=action.split(".")[0],
                    request_key=key,
                    parameters_hash=parameter_hash,
                    operation_status="processing",
                    row_version=1,
                    created_at=utcnow(),
                    updated_at=utcnow(),
                )
            )
            op_id = result.inserted_primary_key[0]
            receipt, entity_id, audit = handler(operation_key)
            self.db.execute(
                update(op)
                .where(op.c.operation_log_id == op_id)
                .values(
                    entity_id=entity_id,
                    after_data=audit,
                    result_reference=receipt,
                    operation_status="succeeded",
                    finished_at=utcnow(),
                    updated_at=utcnow(),
                )
            )
            self.db.commit()
            return receipt
        except IntegrityError:
            self.db.rollback()
            existing = (
                self.db.execute(select(op).where(op.c.operation_key == operation_key))
                .mappings()
                .first()
            )
            if existing:
                try:
                    return replay(existing)
                finally:
                    self.db.rollback()
            raise BusinessException(
                "数据发生重复或关联冲突，请核对后重试", 409
            ) from None
        except Exception:
            self.db.rollback()
            raise

    def submit_leave(self, actor, key, body):
        def apply(_):
            teacher = self.responsible_teacher(actor.actor_id)
            now = utcnow()
            t = shared.student_leave_request
            result = self.db.execute(
                insert(t).values(
                    request_no="L" + uuid4().hex[:30],
                    student_id=actor.actor_id,
                    leave_type=body.leave_type,
                    start_at=as_utc(body.leave_start_at),
                    end_at=as_utc(body.leave_end_at),
                    reason=body.leave_content,
                    approver_employee_id=teacher,
                    status="submitted",
                    submitted_at=now,
                    created_at=now,
                    updated_at=now,
                    row_version=1,
                )
            )
            entity_id = result.inserted_primary_key[0]
            if teacher:
                self.notify(
                    "leave",
                    entity_id,
                    "leave.submitted",
                    "有学生请假待审批",
                    employee_id=teacher,
                )
            receipt = {
                "apply_id": entity_id,
                "approval_status": "submitted",
                "row_version": 1,
                "assignment_pending": teacher is None,
            }
            return (
                receipt,
                entity_id,
                {"status": "submitted", "approver_employee_id": teacher},
            )

        return self._write(
            actor, "leave.submit", key, body.model_dump(mode="json"), apply
        )

    def withdraw_leave(self, actor, key, entity_id, expected):
        def apply(_):
            t = shared.student_leave_request
            row = self._load(t, entity_id, actor)
            if row["status"] != "submitted":
                raise BusinessException("仅待审批的请假可以撤回", 409)
            version = self._version_update(t, row, expected, {"status": "withdrawn"})
            receipt = {
                "apply_id": entity_id,
                "approval_status": "withdrawn",
                "row_version": version,
            }
            return receipt, entity_id, {"status": "withdrawn", "row_version": version}

        return self._write(actor, "leave.withdraw", key, [entity_id, expected], apply)

    def leave_for_teacher(self, actor, entity_id, *, lock=False):
        self.employee(actor)
        row = self._load(shared.student_leave_request, entity_id, lock=lock)
        if row["approver_employee_id"] != actor.actor_id or not self.bound(
            actor.actor_id, row["student_id"]
        ):
            raise BusinessException("无权处理该请假", 403)
        return row

    def decide_leave(self, actor, key, entity_id, body):
        # 在幂等回放前也验证当前责任关系，失效的员工不继续获取业务回执。
        self.leave_for_teacher(actor, entity_id)

        def apply(_):
            row = self.leave_for_teacher(actor, entity_id, lock=True)
            if row["status"] != "submitted":
                raise BusinessException("仅待审批的请假可以审批", 409)
            version = self._version_update(
                shared.student_leave_request,
                row,
                body.expected_version,
                {
                    "status": body.decision,
                    "decision_employee_id": actor.actor_id,
                    "decision_at": utcnow(),
                    "decision_comment": body.comment or None,
                },
            )
            self.notify(
                "leave",
                entity_id,
                "leave." + body.decision,
                "你的请假已有审批结果",
                student_id=row["student_id"],
                version=version,
            )
            receipt = {
                "apply_id": entity_id,
                "approval_status": body.decision,
                "row_version": version,
            }
            return (
                receipt,
                entity_id,
                {
                    **receipt,
                    "decision_employee_id": actor.actor_id,
                    "decision_comment": body.comment,
                },
            )

        return self._write(
            actor, "leave.decide", key, [entity_id, body.model_dump()], apply
        )

    def teacher_binding_condition(self, actor, student_column):
        b, now = shared.student_staff_binding, utcnow()
        return (
            select(b.c.binding_id)
            .where(
                b.c.student_id == student_column,
                b.c.employee_id == actor.actor_id,
                b.c.relation_type == "class_teacher",
                b.c.status == "active",
                b.c.valid_from <= now,
                or_(b.c.valid_to.is_(None), b.c.valid_to > now),
            )
            .exists()
        )

    def teacher_leaves(self, actor, status=None, limit=20, offset=0):
        from sqlalchemy import func

        self.employee(actor)
        t = shared.student_leave_request
        where = [
            t.c.approver_employee_id == actor.actor_id,
            self.teacher_binding_condition(actor, t.c.student_id),
        ]
        if status:
            where.append(t.c.status == status)
        total = self.db.scalar(select(func.count()).select_from(t).where(*where))
        rows = (
            self.db.execute(
                select(t)
                .where(*where)
                .order_by(t.c.submitted_at.desc(), t.c.leave_request_id.desc())
                .limit(limit)
                .offset(offset)
            )
            .mappings()
            .all()
        )
        return {
            "items": [public_row(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def teacher_warnings(self, actor, status=None, limit=20, offset=0):
        from sqlalchemy import func

        self.employee(actor)
        relationship = self.teacher_binding_condition(actor, warnings.c.student_id)
        if actor.actor_id == self.fallback_teacher():
            from sqlalchemy import true

            relationship = true()
        where = [
            relationship,
            or_(
                warnings.c.follower_id.is_(None),
                warnings.c.follower_id == actor.actor_id,
            ),
        ]
        if status:
            where.append(warnings.c.follower_status == status)
        total = self.db.scalar(select(func.count()).select_from(warnings).where(*where))
        rows = (
            self.db.execute(
                select(warnings)
                .where(*where)
                .order_by(warnings.c.created_at.desc(), warnings.c.id.desc())
                .limit(limit)
                .offset(offset)
            )
            .mappings()
            .all()
        )
        result = []
        for row in rows:
            item = dict(row)
            item["row_version"] = item.pop("version")
            result.append(public_row(item))
        return {"items": result, "total": total, "limit": limit, "offset": offset}

    def submit_ticket(self, actor, key, body, summary=None):
        def apply(opkey):
            student = self.student(actor)
            now = utcnow()
            teacher = self.responsible_teacher(
                actor.actor_id, "service_advisor"
            ) or self.responsible_teacher(actor.actor_id)
            t = shared.service_ticket
            result = self.db.execute(
                insert(t).values(
                    ticket_no="T" + uuid4().hex[:30],
                    student_id=actor.actor_id,
                    ticket_type=body.feedback_type,
                    category_code=summary.category if summary else "other",
                    content=body.complaint_content,
                    ai_summary=summary.summary if summary else None,
                    priority="normal",
                    employee_id=teacher,
                    handling_department_id=student["department_id"],
                    status="assigned" if teacher else "open",
                    response_due_at=now
                    + timedelta(hours=settings.STUDENT_TICKET_RESPONSE_HOURS),
                    resolution_due_at=now
                    + timedelta(hours=settings.STUDENT_TICKET_RESOLUTION_HOURS),
                    reopen_count=0,
                    row_version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            entity_id = result.inserted_primary_key[0]
            self._ticket_record(
                entity_id,
                actor,
                opkey,
                "submitted",
                body.complaint_content,
                "assigned" if teacher else "open",
                1,
            )
            if teacher:
                self.notify(
                    "ticket",
                    entity_id,
                    "ticket.submitted",
                    "有学生反馈待处理",
                    employee_id=teacher,
                )
            receipt = {
                "ticket_id": entity_id,
                "process_status": "assigned" if teacher else "open",
                "row_version": 1,
                "summary_available": summary is not None,
            }
            return (
                receipt,
                entity_id,
                {"status": receipt["process_status"], "row_version": 1},
            )

        return self._write(
            actor, "ticket.submit", key, body.model_dump(mode="json"), apply
        )

    def _ticket_record(self, entity_id, actor, opkey, kind, content, status, cycle):
        self.db.execute(
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

    def ticket_reply(self, actor, key, entity_id, body):
        def apply(opkey):
            t = shared.service_ticket
            row = self._load(t, entity_id, actor)
            if row["status"] == "closed":
                raise BusinessException("工单已关闭", 409)
            version = self._version_update(t, row, body.expected_version, {})
            self._ticket_record(
                entity_id,
                actor,
                opkey,
                "student_reply",
                body.content,
                row["status"],
                row["reopen_count"] + 1,
            )
            return (
                {"ticket_id": entity_id, "row_version": version},
                entity_id,
                {"row_version": version},
            )

        return self._write(
            actor, "ticket.reply", key, [entity_id, body.model_dump()], apply
        )

    def confirm_ticket(self, actor, key, entity_id, body):
        def apply(opkey):
            t = shared.service_ticket
            row = self._load(t, entity_id, actor)
            if row["status"] != "awaiting_student":
                raise BusinessException("工单尚未进入学生确认阶段", 409)
            now = utcnow()
            status = "closed" if body.resolved else "reopened"
            values = {"status": status, "closed_at": now if body.resolved else None}
            if not body.resolved:
                values.update(
                    reopen_count=row["reopen_count"] + 1,
                    first_response_at=None,
                    resolved_at=None,
                    solution=None,
                    satisfaction_score=None,
                    response_due_at=now
                    + timedelta(hours=settings.STUDENT_TICKET_RESPONSE_HOURS),
                    resolution_due_at=now
                    + timedelta(hours=settings.STUDENT_TICKET_RESOLUTION_HOURS),
                )
            version = self._version_update(t, row, body.expected_version, values)
            self._ticket_record(
                entity_id,
                actor,
                opkey,
                "confirm" if body.resolved else "reopen",
                body.content,
                status,
                row["reopen_count"] + (1 if body.resolved else 2),
            )
            if row["employee_id"]:
                self.notify(
                    "ticket",
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

        return self._write(
            actor, "ticket.confirm", key, [entity_id, body.model_dump()], apply
        )

    def rate_ticket(self, actor, key, entity_id, body):
        def apply(opkey):
            t = shared.service_ticket
            row = self._load(t, entity_id, actor)
            if row["status"] != "closed":
                raise BusinessException("请先确认工单已解决，再评价", 409)
            version = self._version_update(
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

        return self._write(
            actor, "ticket.rate", key, [entity_id, body.model_dump()], apply
        )

    def record_mental(self, actor, key, text, assessment):
        def apply(_):
            now = utcnow()
            result = self.db.execute(
                insert(profiles).values(
                    student_id=actor.actor_id,
                    emotion_tag=assessment.emotion_tag,
                    emotion_score=assessment.emotion_score,
                    risk_level=assessment.risk_level,
                    observed_at=now,
                    source_event_id=digest([actor.key, key]),
                    analysis_version=settings.STUDENT_ANALYSIS_VERSION,
                    created_at=now,
                )
            )
            profile_id = result.inserted_primary_key[0]
            if assessment.risk_level in ("high", "critical"):
                teacher = (
                    self.responsible_teacher(actor.actor_id) or self.fallback_teacher()
                )
                result = self.db.execute(
                    insert(warnings).values(
                        student_id=actor.actor_id,
                        profile_id=profile_id,
                        trigger_reason=assessment.trigger_reason,
                        risk_level=assessment.risk_level,
                        follower_status="pending",
                        follower_id=teacher,
                        version=1,
                        created_at=now,
                        updated_at=now,
                    )
                )
                warning_id = result.inserted_primary_key[0]
                if teacher:
                    self.notify(
                        "mental_warning",
                        warning_id,
                        "mental.created",
                        "有学生关怀事项需要及时处理",
                        employee_id=teacher,
                    )
            # 学生回执不包含预警原因、老师笔记或内部处理ID。
            receipt = {
                "assessment_saved": True,
                "support_required": assessment.risk_level in ("high", "critical"),
            }
            return receipt, profile_id, {"assessment_id": profile_id}

        return self._write(
            actor, "mental.record", key, {"text_hash": digest(text)}, apply
        )

    def handle_warning(self, actor, key, entity_id, kind, body):
        self.employee(actor)
        authorized = self._load(warnings, entity_id)
        if (
            not self.bound(actor.actor_id, authorized["student_id"])
            and actor.actor_id != self.fallback_teacher()
        ) or authorized["follower_id"] not in (None, actor.actor_id):
            raise BusinessException("无权处理该预警", 403)

        def apply(_):
            row = self._load(warnings, entity_id)
            is_fallback = actor.actor_id == self.fallback_teacher()
            if (
                not self.bound(actor.actor_id, row["student_id"])
                and not is_fallback
                or row["follower_id"] not in (None, actor.actor_id)
            ):
                raise BusinessException("无权处理该预警", 403)
            if kind == "ack" and row["follower_status"] != "pending":
                raise BusinessException("预警已被接手或关闭", 409)
            if kind in ("follow", "close") and row["follower_status"] != "processing":
                raise BusinessException("请先接手待处理预警", 409)
            values = {"follower_id": actor.actor_id}
            if kind == "ack":
                values.update(follower_status="processing", acknowledged_at=utcnow())
            elif kind == "close":
                values.update(
                    follower_status="closed",
                    closed_at=utcnow(),
                    handling_result=body.note,
                )
            version = self._version_update(warnings, row, body.expected_version, values)
            # 专属处置备注仅进入受限操作记录，不写应用日志和学生响应。
            self.db.execute(
                update(shared.operation_log)
                .where(
                    shared.operation_log.c.operation_key
                    == digest([actor.key, "mental." + kind, key])
                )
                .values(change_reason=body.note)
            )
            return (
                {"warning_id": entity_id, "row_version": version},
                entity_id,
                {"status": values.get("follower_status", "processing")},
            )

        return self._write(
            actor, "mental." + kind, key, [entity_id, body.model_dump()], apply
        )

    def set_reminder(self, actor, key, body):
        def apply(_):
            event = self._load(events, body.academic_event_id, actor)
            notify_at = event["due_at"] - timedelta(minutes=body.lead_minutes)
            if event["event_status"] != "active" or notify_at <= utcnow():
                raise BusinessException("节点已取消或提醒时间已过", 409)
            row = (
                self.db.execute(
                    select(reminders)
                    .where(
                        reminders.c.student_id == actor.actor_id,
                        reminders.c.academic_event_id == body.academic_event_id,
                        reminders.c.lead_minutes == body.lead_minutes,
                    )
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            values = dict(
                student_id=actor.actor_id,
                academic_event_id=body.academic_event_id,
                lead_minutes=body.lead_minutes,
                notify_at=notify_at,
                event_version=event["event_version"],
                status="pending",
                sent_at=None,
                updated_at=next_setting_time(row),
            )
            if row:
                if (
                    row["status"] != "cancelled"
                    and row["event_version"] == event["event_version"]
                ):
                    return (
                        {"reminder_id": row["id"], "status": row["status"]},
                        row["id"],
                        {"status": row["status"]},
                    )
                self.db.execute(
                    update(reminders)
                    .where(reminders.c.id == row["id"])
                    .values(**values)
                )
                entity_id = row["id"]
            else:
                result = self.db.execute(
                    insert(reminders).values(**values, created_at=utcnow())
                )
                entity_id = result.inserted_primary_key[0]
            return (
                {"reminder_id": entity_id, "status": "pending"},
                entity_id,
                {"status": "pending"},
            )

        return self._write(actor, "reminder.set", key, body.model_dump(), apply)

    def cancel_reminder(self, actor, key, entity_id):
        def apply(_):
            row = self._load(reminders, entity_id, actor)
            self.db.execute(
                update(reminders)
                .where(reminders.c.id == entity_id)
                .values(status="cancelled", updated_at=next_setting_time(row))
            )
            n = shared.business_notification
            self.db.execute(
                update(n)
                .where(
                    n.c.entity_type == "academic_reminder",
                    n.c.entity_id == entity_id,
                    n.c.delivery_status.in_(["pending", "failed", "sending"]),
                )
                .values(
                    delivery_status="dead_letter",
                    last_error_code="REMINDER_CANCELLED",
                    row_version=n.c.row_version + 1,
                )
            )
            return (
                {"reminder_id": entity_id, "status": "cancelled"},
                entity_id,
                {"status": "cancelled"},
            )

        return self._write(actor, "reminder.cancel", key, [entity_id], apply)

    def teacher_notifications(self, actor, limit=20, offset=0):
        from sqlalchemy import func

        self.employee(actor)
        n = shared.business_notification
        where = [
            n.c.employee_id == actor.actor_id,
            n.c.event_code.like("student.%"),
            n.c.channel == "in_app",
            n.c.delivery_status == "sent",
        ]
        columns = [
            n.c[name]
            for name in (
                "notification_id",
                "entity_type",
                "entity_id",
                "event_code",
                "title",
                "content",
                "sent_at",
                "read_at",
            )
        ]
        rows = self.db.execute(
            select(*columns)
            .where(*where)
            .order_by(n.c.notification_id.desc())
            .limit(limit)
            .offset(offset)
        ).mappings()
        return {
            "items": [public_row(row) for row in rows],
            "total": self.db.scalar(select(func.count()).select_from(n).where(*where)),
            "limit": limit,
            "offset": offset,
        }

    def read_teacher_notification(self, actor, key, entity_id):
        self.employee(actor)

        def apply(_):
            n = shared.business_notification
            row = self._load(n, entity_id)
            if (
                row["employee_id"] != actor.actor_id
                or not row["event_code"].startswith("student.")
                or row["channel"] != "in_app"
            ):
                raise BusinessException("记录不存在", 404)
            if row["delivery_status"] != "sent":
                raise BusinessException("通知尚未送达", 409)
            if row["read_at"] is None:
                self.db.execute(
                    update(n)
                    .where(n.c.notification_id == entity_id)
                    .values(read_at=utcnow(), row_version=n.c.row_version + 1)
                )
            return (
                {"notification_id": entity_id, "read": True},
                entity_id,
                {"read": True},
            )

        return self._write(actor, "employee.notification.read", key, [entity_id], apply)

    def read_notification(self, actor, key, entity_id):
        def apply(_):
            n = shared.business_notification
            row = self._load(n, entity_id, actor)
            if row["delivery_status"] != "sent":
                raise BusinessException("通知尚未送达", 409)
            if row["read_at"] is None:
                self.db.execute(
                    update(n)
                    .where(n.c.notification_id == entity_id)
                    .values(
                        read_at=utcnow(),
                        updated_at=utcnow(),
                        row_version=n.c.row_version + 1,
                    )
                )
            return (
                {"notification_id": entity_id, "read": True},
                entity_id,
                {"read": True},
            )

        return self._write(actor, "notification.read", key, [entity_id], apply)
