"""公共通知中心：只汇总本人可见消息；公告与已读状态独立于各业务流程。"""
import re
from datetime import datetime, timezone
from sqlalchemy import and_, or_, select, insert, update
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models import common as t
from app.core.common.navigation import account_access


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def public(row):
    return {key: value.isoformat(timespec="milliseconds") + "Z" if isinstance(value, datetime) else value
            for key, value in dict(row).items()}


def active_announcements():
    a = t.platform_announcement
    instant = now()
    return and_(a.c.status == "published", a.c.published_at <= instant,
                or_(a.c.expires_at.is_(None), a.c.expires_at > instant))


def receipts(db, account):
    r = t.platform_notification_read
    return dict(db.execute(select(r.c.message_key, r.c.read_at).where(r.c.user_id == account.user_id)).all())


def announcement_list(db, account, manage=False):
    a = t.platform_announcement
    statement = select(a)
    if not manage:
        statement = statement.where(active_announcements())
    rows = db.execute(statement.order_by(a.c.pinned.desc(), a.c.published_at.desc(), a.c.announcement_id.desc())).mappings().all()
    read = receipts(db, account)
    items = []
    for row in rows:
        item = {key: row[key] for key in ("announcement_id", "title", "content", "status", "pinned", "published_at", "expires_at", "created_at", "row_version")}
        item.update(key=f"announcement:{row['announcement_id']}", read_at=read.get(f"announcement:{row['announcement_id']}"))
        items.append(public(item))
    return {"items": items, "total": len(items), "unread_count": sum(item["read_at"] is None for item in items)}


def save_announcement(db, account, payload, announcement_id=None):
    a = t.platform_announcement
    values = payload.model_dump(exclude={"expected_version"})
    values["updated_at"] = now()
    if values["status"] == "published" and values["published_at"] is None:
        values["published_at"] = now()
    if values["expires_at"] and values["published_at"] and values["expires_at"] <= values["published_at"]:
        raise HTTPException(422, "结束时间必须晚于发布时间")
    if announcement_id is None:
        announcement_id = db.execute(insert(a).values(**values, author_user_id=account.user_id)).inserted_primary_key[0]
    else:
        if payload.expected_version is None:
            raise HTTPException(422, "编辑公告须提供当前版本")
        result = db.execute(update(a).where(a.c.announcement_id == announcement_id,
            a.c.row_version == payload.expected_version).values(**values, row_version=a.c.row_version + 1))
        if result.rowcount != 1:
            raise HTTPException(409, "公告已被更新或不存在，请刷新后重试")
    db.commit()
    return public(db.execute(select(a).where(a.c.announcement_id == announcement_id)).mappings().one())


def category(row):
    text = (row["event_code"] + " " + row["entity_type"]).lower()
    if any(word in text for word in ("ticket", "reply", "response")):
        return "reply"
    if any(word in text for word in ("leave", "approval", "status", "progress", "review")):
        return "status"
    return "important"


def own_business_rows(db, account):
    n = t.business_notification
    if account.identity_type == "student":
        owner = n.c.student_id == account.student_id
        context = None
    elif account.identity_type in ("employee", "admin"):
        from app.core.enterprise.enterprise_authorization import context_for
        context = context_for(db, account)
        if context.employee_id is None:
            return []
        owner = n.c.employee_id == context.employee_id
    else:
        # 现有业务表没有客户接收人字段，不以学生或员工消息冒充客户消息。
        return []
    candidates = db.execute(select(n).where(owner, n.c.channel == "in_app", n.c.delivery_status == "sent")
        .order_by(n.c.created_at.desc(), n.c.notification_id.desc())).mappings().all()
    if not candidates:
        return []
    if account.identity_type == "student":
        return candidates
    from app.services.enterprise.enterprise_notification import visibility
    enterprise_ids = set(db.scalars(select(n.c.notification_id).where(owner, visibility(context))))
    if account.identity_type == "admin":
        return [row for row in candidates if row["notification_id"] in enterprise_ids]
    from app.core.student.student_auth import Principal
    from app.core.student.student_permissions import employee_permissions
    from app.services.student.student_notifications import visible
    actor = Principal("employee", actor_id=context.employee_id,
        scopes=tuple(employee_permissions(db, context.employee_id)), user_id=account.user_id)
    return [row for row in candidates if row["notification_id"] in enterprise_ids or
            (account.identity_type == "employee" and row["event_code"].startswith("student.") and visible(db, row, actor))]


def personal_list(db, account, *, limit=20, offset=0, unread=False, kind=None, query=""):
    read = receipts(db, account)
    rows = []
    for row in own_business_rows(db, account):
        item = {key: row[key] for key in ("notification_id", "title", "content", "event_code", "entity_type", "entity_id", "created_at", "sent_at")}
        item.update(key=f"business:{row['notification_id']}", kind=category(row),
                    read_at=read.get(f"business:{row['notification_id']}") or row["read_at"])
        rows.append(item)
    unread_count = sum(row["read_at"] is None for row in rows)
    rows = [row for row in rows if (not unread or row["read_at"] is None) and
            (kind is None or row["kind"] == kind) and
            (not query or query.casefold() in (row["title"] + row["content"]).casefold())]
    return {"items": [public(row) for row in rows[offset:offset + limit]], "total": len(rows),
            "unread_count": unread_count, "limit": limit, "offset": offset}


def message_detail(db, account, key):
    match = re.fullmatch(r"(announcement|business):([1-9][0-9]{0,18})", key)
    if not match:
        raise HTTPException(404, "通知不存在或不可见")
    source, number = match[1], int(match[2])
    if source == "announcement":
        row = db.execute(select(t.platform_announcement).where(active_announcements(),
            t.platform_announcement.c.announcement_id == number)).mappings().first()
        if row:
            return public({"key": key, "title": row["title"], "content": row["content"], "kind": "announcement",
                "created_at": row["published_at"], "read_at": receipts(db, account).get(key), "related": None})
    else:
        row = next((row for row in own_business_rows(db, account) if row["notification_id"] == number), None)
        if row:
            route, selection = related_page(db, account, row)
            routes = account_access(db, account)["navigation"]["routes"]
            related = {"route": route, "selection": selection} if route in routes else None
            return public({"key": key, "title": row["title"], "content": row["content"], "kind": category(row),
                "created_at": row["sent_at"] or row["created_at"], "read_at": receipts(db, account).get(key) or row["read_at"], "related": related})
    raise HTTPException(404, "通知不存在或不可见")


def related_page(db, account, row):
    student = account.identity_type == "student"
    prefix = "/student/" if student else "/enterprise/"
    targets = {
        "leave": ("leave-detail.html", "apply_id"), "student_admin_service": ("leave-detail.html", "apply_id"),
        "ticket": ("ticket-detail.html", "ticket_id"), "service_ticket": ("ticket-detail.html", "ticket_id"),
        "customer_profile": ("customer-detail.html", "customer_id"), "customer_followup": ("followups.html", "followup_id"),
        "employee_daily_report": ("daily-report-detail.html", "report_id"),
        "mental_warning": ("warning-detail.html", "warning_id"),
        "student_academic_reminder": ("reminders.html", "reminder_id"),
        "student_application_progress": ("progress.html" if student else "application-progress.html", "progress_id"),
    }
    target = targets.get(row["entity_type"])
    if row["entity_type"] == "customer_followup":
        from app.models.enterprise import customer_followup
        customer_id = db.scalar(select(customer_followup.c.customer_id).where(customer_followup.c.followup_id == row["entity_id"]))
        return ("/enterprise/followups.html", {"customer_id": customer_id, "followup_id": row["entity_id"]}) if customer_id else (None, {})
    return (prefix + target[0], {target[1]: row["entity_id"]}) if target else (None, {})


def mark_read(db, account, key):
    message_detail(db, account, key)  # 每次更新前重新验证当前可见范围。
    r = t.platform_notification_read
    predicate = and_(r.c.user_id == account.user_id, r.c.message_key == key)
    if db.scalar(select(r.c.read_at).where(predicate)) is None:
        try:
            with db.begin_nested():
                db.execute(insert(r).values(user_id=account.user_id, message_key=key, read_at=now()))
        except IntegrityError:
            if db.scalar(select(r.c.read_at).where(predicate).with_for_update()) is None:
                raise
        db.commit()
    return public({"key": key, "read_at": db.scalar(select(r.c.read_at).where(predicate))})
