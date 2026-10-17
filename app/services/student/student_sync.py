"""教务和CRM最新快照同步；按来源时间防旧数据覆盖，节点改期同时重排提醒。"""

from datetime import timedelta
from sqlalchemy import select, insert, update
from app.core.common.response import BusinessException
from app.config import settings
from app.models import common as shared
from app.models.student.student_types import utcnow
from app.services.student.student_service import (
    StudentService,
    events,
    reminders,
    progress,
    next_setting_time,
)
from app.schemas.student.student import as_utc


class StudentSyncService(StudentService):
    def academic(self, actor, key, body):
        actor.require_scope("student:sync")
        if body.source_system == "local" or body.source_system not in settings.STUDENT_SYNC_ALLOWED_SOURCES or body.student_id not in settings.STUDENT_SYNC_ALLOWED_STUDENT_IDS:
            raise BusinessException("同步来源或学生范围未授权",403)

        def apply(_):
            self.lock_business_prefix(body.student_id)
            self.student_record(body.student_id)
            seen, changed, ignored = set(), 0, 0
            for item in sorted(body.records,key=lambda item: getattr(item,"external_event_id",getattr(item,"external_application_id",""))):
                if item.external_event_id in seen:
                    raise BusinessException("同一批次包含重复节点", 400)
                seen.add(item.external_event_id)
                row = (
                    self.db.execute(
                        select(events)
                        .where(
                            events.c.student_id == body.student_id,
                            events.c.source_system == body.source_system,
                            events.c.external_event_id == item.external_event_id,
                        )
                        .with_for_update()
                    )
                    .mappings()
                    .first()
                )
                source_time = as_utc(item.source_updated_at)
                if (
                    row
                    and row["source_updated_at"]
                    and source_time < row["source_updated_at"]
                ):
                    ignored += 1
                    continue
                values = dict(
                    event_type=item.event_type,
                    title=item.title,
                    due_at=as_utc(item.due_at),
                    source_timezone=item.source_timezone,
                    event_status=item.event_status,
                    source_updated_at=source_time,
                    synced_at=utcnow(),
                    updated_at=utcnow(),
                )
                if row:
                    if source_time == row["source_updated_at"] and any(
                        row[k] != v
                        for k, v in values.items()
                        if k not in ("synced_at", "updated_at")
                    ):
                        raise BusinessException("同一来源版本出现不同节点内容", 409)
                    moved = (
                        row["due_at"] != values["due_at"]
                        or row["event_status"] != values["event_status"]
                    )
                    version = row["event_version"] + int(moved)
                    self.db.execute(
                        update(events)
                        .where(events.c.id == row["id"])
                        .values(**values, event_version=version)
                    )
                    if moved:
                        self._replan(
                            row["id"], values["due_at"], item.event_status, version
                        )
                else:
                    self.db.execute(
                        insert(events).values(
                            **values,
                            student_id=body.student_id,
                            source_system=body.source_system,
                            external_event_id=item.external_event_id,
                            event_version=1,
                            created_at=utcnow()
                        )
                    )
                changed += 1
            result = {"updated": changed, "ignored_stale": ignored}
            return result, body.student_id, result

        return self._write(
            actor, "academic.sync", key, body.model_dump(mode="json"), apply
        )

    def _replan(self, event_id, due_at, status, version):
        n = shared.business_notification
        for reminder in self.db.execute(
            select(reminders)
            .where(reminders.c.academic_event_id == event_id)
            .with_for_update()
        ).mappings():
            # 用户取消的订阅不因教务改期而自动重新打开。
            notify_at = due_at - timedelta(minutes=reminder["lead_minutes"])
            new_status = (
                "cancelled"
                if (
                    reminder["status"] == "cancelled"
                    or status == "cancelled"
                    or due_at <= utcnow()
                )
                else "pending"
            )
            self.db.execute(
                update(reminders)
                .where(reminders.c.id == reminder["id"])
                .values(
                    notify_at=notify_at,
                    event_version=version,
                    status=new_status,
                    sent_at=None,
                    updated_at=next_setting_time(reminder),
                )
            )
            self.db.execute(
                update(n)
                .where(
                    n.c.entity_type == "academic_reminder",
                    n.c.entity_id == reminder["id"],
                    n.c.delivery_status.in_(["pending", "sending", "failed"]),
                )
                .values(
                    delivery_status="dead_letter",
                    last_error_code="NODE_CHANGED",
                    row_version=n.c.row_version + 1,
                )
            )

    def application(self, actor, key, body):
        actor.require_scope("student:sync")

        def apply(_):
            self.student_record(body.student_id)
            seen, changed, ignored = set(), 0, 0
            for item in body.records:
                unique = (item.external_application_id, item.stage_code)
                if unique in seen:
                    raise BusinessException("同一批次包含重复申请阶段", 400)
                seen.add(unique)
                row = (
                    self.db.execute(
                        select(progress)
                        .where(
                            progress.c.student_id == body.student_id,
                            progress.c.source_system == body.source_system,
                            progress.c.external_application_id
                            == item.external_application_id,
                            progress.c.stage_code == item.stage_code,
                        )
                        .with_for_update()
                    )
                    .mappings()
                    .first()
                )
                source_time = as_utc(item.source_updated_at)
                if (
                    row
                    and row["source_updated_at"]
                    and source_time < row["source_updated_at"]
                ):
                    ignored += 1
                    continue
                values = dict(
                    application_name=item.application_name,
                    stage_status=item.stage_status,
                    detail=item.detail,
                    source_updated_at=source_time,
                    synced_at=utcnow(),
                    updated_at=utcnow(),
                )
                if row:
                    if source_time == row["source_updated_at"] and any(
                        row[k] != v
                        for k, v in values.items()
                        if k not in ("synced_at", "updated_at")
                    ):
                        raise BusinessException("同一来源版本出现不同进度内容", 409)
                    self.db.execute(
                        update(progress)
                        .where(progress.c.id == row["id"])
                        .values(**values)
                    )
                else:
                    self.db.execute(
                        insert(progress).values(
                            **values,
                            student_id=body.student_id,
                            source_system=body.source_system,
                            external_application_id=item.external_application_id,
                            stage_code=item.stage_code,
                            created_at=utcnow()
                        )
                    )
                changed += 1
            result = {"updated": changed, "ignored_stale": ignored}
            return result, body.student_id, result

        return self._write(
            actor, "progress.sync", key, body.model_dump(mode="json"), apply
        )
