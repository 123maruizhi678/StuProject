"""学生后台任务：准备并投递提醒/通知，使用数据库租约、重试和业务状态复核。"""

from datetime import timedelta
from sqlalchemy import select, update, or_, and_
from app.config import settings
from app.models import student_shared as shared
from app.models.student_types import utcnow
from app.services.student_service import (
    StudentService,
    events,
    reminders,
    warnings,
    reminder_generation,
)
from app.services.student_clients import request_json
from app.core.response import BusinessException


class StudentTasks:
    def __init__(self, session_factory, sender=None):
        self.sessions = session_factory
        self.sender = sender or self.send

    @staticmethod
    def send(notification):
        if notification["channel"] == "in_app":
            return  # 成功状态即表示消息进入本人站内收件列表。
        if notification["channel"] == "webhook":
            result = request_json(
                "POST",
                settings.STUDENT_NOTIFICATION_URL,
                settings.STUDENT_NOTIFICATION_TOKEN,
                payload={
                    k: notification[k]
                    for k in (
                        "notification_id",
                        "employee_id",
                        "student_id",
                        "title",
                        "content",
                        "event_code",
                    )
                },
            )
            if result.get("accepted") is not True:
                raise BusinessException("通知渠道未确认接收", 503)
            return
        raise BusinessException("通知渠道尚未支持", 503)

    def prepare(self, limit=100):
        count = 0
        with self.sessions() as db:
            service = StudentService(db)
            candidates = db.execute(
                select(reminders.c.id, reminders.c.academic_event_id)
                .where(
                    reminders.c.status == "pending", reminders.c.notify_at <= utcnow()
                )
                .order_by(reminders.c.notify_at)
                .limit(limit)
            ).all()
            for candidate in candidates:
                # 同步和提醒都先锁节点再锁设置，避免相反的锁顺序导致死锁。
                event = (
                    db.execute(
                        select(events)
                        .where(events.c.id == candidate.academic_event_id)
                        .with_for_update(skip_locked=True)
                    )
                    .mappings()
                    .first()
                )
                if not event:
                    continue
                row = (
                    db.execute(
                        select(reminders)
                        .where(reminders.c.id == candidate.id)
                        .with_for_update(skip_locked=True)
                    )
                    .mappings()
                    .first()
                )
                if not row or row["status"] != "pending" or row["notify_at"] > utcnow():
                    continue
                if (
                    event["event_status"] != "active"
                    or event["event_version"] != row["event_version"]
                ):
                    db.execute(
                        update(reminders)
                        .where(reminders.c.id == row["id"])
                        .values(status="cancelled", updated_at=row["updated_at"])
                    )
                    continue
                db.execute(
                    update(reminders)
                    .where(reminders.c.id == row["id"])
                    .values(status="queued", updated_at=row["updated_at"])
                )
                generation = reminder_generation(row)
                code = f"academic.due:{row['event_version']}:{generation}"
                service.notify(
                    "academic_reminder",
                    row["id"],
                    code,
                    "你有学业节点即将到期",
                    student_id=row["student_id"],
                    version=generation,
                )
                count += 1
            # 未绑定老师时先保留预警，后续任务持续尝试分派，不丢弃风险事件。
            unassigned = (
                db.execute(
                    select(warnings)
                    .where(
                        warnings.c.follower_id.is_(None),
                        warnings.c.follower_status == "pending",
                    )
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
                .mappings()
                .all()
            )
            for row in unassigned:
                teacher = (
                    service.responsible_teacher(row["student_id"])
                    or service.fallback_teacher()
                )
                if teacher:
                    db.execute(
                        update(warnings)
                        .where(
                            warnings.c.id == row["id"], warnings.c.follower_id.is_(None)
                        )
                        .values(
                            follower_id=teacher,
                            version=warnings.c.version + 1,
                            updated_at=utcnow(),
                        )
                    )
                    service.notify(
                        "mental_warning",
                        row["id"],
                        "mental.created",
                        "有学生关怀事项需要及时处理",
                        employee_id=teacher,
                    )
            leave = shared.student_leave_request
            waiting = (
                db.execute(
                    select(leave)
                    .where(
                        leave.c.approver_employee_id.is_(None),
                        leave.c.status == "submitted",
                    )
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
                .mappings()
                .all()
            )
            for row in waiting:
                teacher = service.responsible_teacher(row["student_id"])
                if teacher:
                    version = service._version_update(
                        leave,
                        row,
                        row["row_version"],
                        {"approver_employee_id": teacher},
                    )
                    service.notify(
                        "leave",
                        row["leave_request_id"],
                        "leave.submitted",
                        "有学生请假待审批",
                        employee_id=teacher,
                        version=version,
                    )
            db.commit()
        return count

    @staticmethod
    def current(db, notification):
        """投递前重新验证责任人和业务版本；通用通知记录不代表业务仍有效。"""
        service = StudentService(db)
        kind, entity_id = notification["entity_type"], notification["entity_id"]
        if kind == "academic_reminder":
            row = (
                db.execute(select(reminders).where(reminders.c.id == entity_id))
                .mappings()
                .first()
            )
            if (
                not row
                or row["status"] != "queued"
                or row["student_id"] != notification["student_id"]
            ):
                return False
            event = (
                db.execute(
                    select(events).where(events.c.id == row["academic_event_id"])
                )
                .mappings()
                .first()
            )
            return bool(
                event
                and event["event_status"] == "active"
                and event["event_version"] == row["event_version"]
                and notification["event_code"]
                == f"student.academic.due:{row['event_version']}:{reminder_generation(row)}"
            )
        if kind == "mental_warning":
            row = (
                db.execute(select(warnings).where(warnings.c.id == entity_id))
                .mappings()
                .first()
            )
            return bool(
                row
                and row["follower_status"] == "pending"
                and row["follower_id"] == notification["employee_id"]
                and (
                    service.bound(row["follower_id"], row["student_id"])
                    or row["follower_id"] == service.fallback_teacher()
                )
            )
        if kind == "leave":
            t = shared.student_leave_request
            row = (
                db.execute(select(t).where(t.c.leave_request_id == entity_id))
                .mappings()
                .first()
            )
            if notification["student_id"] is not None:
                return bool(
                    row
                    and row["student_id"] == notification["student_id"]
                    and row["status"] in ("approved", "rejected")
                    and notification["event_code"] == "student.leave." + row["status"]
                )
            return bool(
                row
                and row["status"] == "submitted"
                and row["approver_employee_id"] == notification["employee_id"]
                and service.bound(row["approver_employee_id"], row["student_id"])
            )
        if kind == "ticket":
            t = shared.service_ticket
            row = (
                db.execute(select(t).where(t.c.ticket_id == entity_id))
                .mappings()
                .first()
            )
            return bool(
                row
                and row["employee_id"] == notification["employee_id"]
                and row["status"] != "closed"
            )
        return False

    def dispatch(self, limit=100):
        n, now = shared.business_notification, utcnow()
        with self.sessions() as db:
            # 仅领取本模块产生的消息，不接管企业模块的公共通知任务。
            candidates = (
                db.execute(
                    select(n)
                    .where(
                        n.c.event_code.like("student.%"),
                        or_(
                            and_(
                                n.c.delivery_status.in_(["pending", "failed"]),
                                or_(
                                    n.c.next_retry_at.is_(None),
                                    n.c.next_retry_at <= now,
                                ),
                            ),
                            and_(
                                n.c.delivery_status == "sending", n.c.lease_until < now
                            ),
                        ),
                    )
                    .order_by(n.c.notification_id)
                    .limit(limit)
                )
                .mappings()
                .all()
            )
        sent, failed, skipped = 0, 0, 0
        for row in candidates:
            claim_version = row["row_version"] + 1
            with self.sessions() as db:
                claimed = db.execute(
                    update(n)
                    .where(
                        n.c.notification_id == row["notification_id"],
                        n.c.row_version == row["row_version"],
                    )
                    .values(
                        delivery_status="sending",
                        row_version=claim_version,
                        lease_until=utcnow()
                        + timedelta(
                            seconds=settings.STUDENT_NOTIFICATION_LEASE_SECONDS
                        ),
                        updated_at=utcnow(),
                    )
                )
                db.commit()
                if not claimed.rowcount:
                    continue
                latest = (
                    db.execute(
                        select(n).where(n.c.notification_id == row["notification_id"])
                    )
                    .mappings()
                    .one()
                )
                if not self.current(db, latest):
                    db.execute(
                        update(n)
                        .where(
                            n.c.notification_id == row["notification_id"],
                            n.c.row_version == claim_version,
                        )
                        .values(
                            delivery_status="dead_letter",
                            last_error_code="BUSINESS_CHANGED",
                            lease_until=None,
                            updated_at=utcnow(),
                        )
                    )
                    db.commit()
                    skipped += 1
                    continue
            try:
                self.sender(dict(latest))
                with self.sessions() as db:
                    changed = db.execute(
                        update(n)
                        .where(
                            n.c.notification_id == row["notification_id"],
                            n.c.row_version == claim_version,
                            n.c.delivery_status == "sending",
                        )
                        .values(
                            delivery_status="sent",
                            sent_at=utcnow(),
                            lease_until=None,
                            last_error_code=None,
                            attempt_count=row["attempt_count"] + 1,
                            row_version=claim_version + 1,
                            updated_at=utcnow(),
                        )
                    )
                    if changed.rowcount and row["entity_type"] == "academic_reminder":
                        current = (
                            db.execute(
                                select(reminders).where(
                                    reminders.c.id == row["entity_id"]
                                )
                            )
                            .mappings()
                            .first()
                        )
                        if (
                            current
                            and row["event_code"]
                            == f"student.academic.due:{current['event_version']}:{reminder_generation(current)}"
                        ):
                            db.execute(
                                update(reminders)
                                .where(
                                    reminders.c.id == row["entity_id"],
                                    reminders.c.status == "queued",
                                    reminders.c.updated_at == current["updated_at"],
                                )
                                .values(
                                    status="sent",
                                    sent_at=utcnow(),
                                    updated_at=current["updated_at"],
                                )
                            )
                    db.commit()
                    sent += int(bool(changed.rowcount))
            except Exception:
                attempt = row["attempt_count"] + 1
                with self.sessions() as db:
                    db.execute(
                        update(n)
                        .where(
                            n.c.notification_id == row["notification_id"],
                            n.c.row_version == claim_version,
                            n.c.delivery_status == "sending",
                        )
                        .values(
                            delivery_status=(
                                "dead_letter"
                                if attempt >= settings.STUDENT_NOTIFICATION_MAX_ATTEMPTS
                                else "failed"
                            ),
                            last_error_code="DELIVERY_FAILED",
                            attempt_count=attempt,
                            lease_until=None,
                            next_retry_at=utcnow()
                            + timedelta(seconds=min(900, 2 ** min(attempt, 9))),
                            row_version=claim_version + 1,
                            updated_at=utcnow(),
                        )
                    )
                    db.commit()
                failed += 1
        return {"sent": sent, "failed": failed, "skipped": skipped}

    def run_once(self):
        return {"reminders_queued": self.prepare(), **self.dispatch()}
