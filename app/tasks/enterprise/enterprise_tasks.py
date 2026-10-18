"""企业提醒补扫及站内发布；只消费 enterprise.*，不修改业务事实。"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select, update

from app.core.enterprise.enterprise_authorization import EmployeeContext, scope
from app.models import common as t
from app.models.enterprise import customer_followup, employee_daily_report
from app.repositories.enterprise.enterprise_repository import digest
from app.services.enterprise.enterprise_notification import enqueue
from app.services.enterprise.enterprise_ticket_policy import policy


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _generation(row, deadline, now, *, followup=False):
    baseline = (row['schedule_base_at'] or deadline) if followup else deadline
    round_seconds = policy()['reminder_round_hours'] * 3600
    round_no = max(0, int((now - baseline).total_seconds() // round_seconds))
    generation = row['schedule_operation_id'] if followup else row['reopen_count']
    return [generation, baseline.isoformat(timespec='milliseconds'), round_no]


def _key(notification, generation):
    return notification['event_code'] + ':' + digest([
        notification['entity_type'], notification['entity_id'], generation,
        notification['employee_id'], None, 'in_app',
    ])


def _recipient(db, employee_id):
    """复用业务写入的部门→员工锁序；转部门中的快照留待下轮处理。"""
    if employee_id is None:
        return None
    department_id = db.scalar(select(t.employee.c.department_id).where(t.employee.c.employee_id == employee_id))
    department = db.scalar(select(t.org_department.c.status).where(
        t.org_department.c.department_id == department_id).with_for_update())
    employee = db.execute(select(t.employee).where(
        t.employee.c.employee_id == employee_id).with_for_update()).mappings().first()
    if not employee or employee['status'] != 'active' or department != 'active' or employee['department_id'] != department_id:
        return None
    roles = employee['role_codes']
    if not isinstance(roles, list) or any(not isinstance(role, str) for role in roles):
        return None
    return EmployeeContext(0, employee_id, department_id, frozenset(roles))


def _ticket_reminders(row, now):
    if row['status'] not in ('open', 'assigned', 'processing', 'reopened'):
        return
    if row['first_response_at'] is None and row['response_due_at'] <= now:
        yield 'enterprise.ticket.response_due', row['response_due_at'], '工单首次回应已到期'
    if row['resolved_at'] is None and row['resolution_due_at'] <= now:
        yield 'enterprise.ticket.resolution_due', row['resolution_due_at'], '工单处理已到期'


def scan(db, limit=100):
    """按安排代次与24小时轮次去重；limit为读取批次大小，逐对象提交。"""
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError('扫描上限须为正整数')
    now = _utcnow()
    count = 0

    def batches(query, pk):
        cursor = 0
        while True:
            rows = db.execute(query.where(pk > cursor).order_by(pk).limit(limit)).mappings().all()
            db.rollback()
            if not rows:
                return
            yield from rows
            cursor = rows[-1][pk.name]

    def queue(event, entity_type, row, pk, employee_id, generation, title):
        nonlocal count
        key = event + ':' + digest([entity_type, row[pk], generation, employee_id, None, 'in_app'])
        existed = db.scalar(select(t.business_notification.c.notification_id).where(
            t.business_notification.c.dedupe_key == key))
        enqueue(db, event=event, entity_type=entity_type, entity_id=row[pk],
                employee_id=employee_id, version=generation, title=title)
        if existed is None:
            count += 1

    try:
        # 一轮只在每条待办的当前业务代次内生成通知；旧代次交由发布前复核作废。
        candidates = select(customer_followup, t.customer_profile.c.employee_id.label('recipient_id')).join(
            t.customer_profile, t.customer_profile.c.customer_id == customer_followup.c.customer_id
        ).where(customer_followup.c.followup_status == 'pending',
                customer_followup.c.next_followup_at <= now,
                t.customer_profile.c.is_archived.is_(False),
                t.customer_profile.c.employee_id.is_not(None))
        for candidate in batches(candidates, customer_followup.c.followup_id):
            # 与业务服务一致：先锁客户，再锁跟进，防止与改期/转派交叉。
            ctx = _recipient(db, candidate['recipient_id'])
            customer = db.execute(select(t.customer_profile).where(
                t.customer_profile.c.customer_id == candidate['customer_id']).with_for_update()).mappings().first()
            row = db.execute(select(customer_followup).where(
                customer_followup.c.followup_id == candidate['followup_id']).with_for_update()).mappings().first()
            if (ctx and ctx.can('customer.read') and customer and not customer['is_archived']
                    and customer['employee_id'] == ctx.employee_id and row
                    and row['followup_status'] == 'pending' and row['next_followup_at'] and row['next_followup_at'] <= now
                    and db.scalar(select(customer_followup.c.followup_id).where(
                        customer_followup.c.followup_id == row['followup_id'], scope(ctx, 'followup', customer_followup)))):
                queue('enterprise.customer.followup_due', 'customer_followup', row, 'followup_id',
                      customer['employee_id'], _generation(row, row['next_followup_at'], now, followup=True), '客户跟进已到期')
            # 每个业务对象独立提交，避免跨对象累计不同部门的锁。
            db.commit()

        candidates = select(t.service_ticket).where(
            t.service_ticket.c.employee_id.is_not(None),
            t.service_ticket.c.status.in_(['open', 'assigned', 'processing', 'reopened']),
            or_(and_(t.service_ticket.c.first_response_at.is_(None), t.service_ticket.c.response_due_at <= now),
                and_(t.service_ticket.c.resolved_at.is_(None), t.service_ticket.c.resolution_due_at <= now)))
        for candidate in batches(candidates, t.service_ticket.c.ticket_id):
            ctx = _recipient(db, candidate['employee_id'])
            row = db.execute(select(t.service_ticket).where(
                t.service_ticket.c.ticket_id == candidate['ticket_id']).with_for_update()).mappings().first()
            if (ctx and ctx.can('ticket.read') and row and row['employee_id'] == ctx.employee_id
                    and db.scalar(select(t.service_ticket.c.ticket_id).where(
                        t.service_ticket.c.ticket_id == row['ticket_id'], scope(ctx, 'ticket', t.service_ticket)))):
                for event, deadline, title in _ticket_reminders(row, now):
                    queue(event, 'service_ticket', row, 'ticket_id', row['employee_id'],
                          _generation(row, deadline, now), title)
            db.commit()
        return count
    except Exception:
        db.rollback()
        raise


def _current(db, notification, now):
    """按部门→员工→业务对象顺序加锁，复验收件资格和提醒代次。"""
    if notification['channel'] != 'in_app' or notification['employee_id'] is None:
        return False
    employee_id = notification['employee_id']
    ctx = _recipient(db, employee_id)
    if ctx is None:
        return False
    kind, entity_id = notification['entity_type'], notification['entity_id']
    if kind == 'customer_followup':
        customer_id = db.scalar(select(customer_followup.c.customer_id).where(customer_followup.c.followup_id == entity_id))
        customer = db.execute(select(t.customer_profile).where(
            t.customer_profile.c.customer_id == customer_id).with_for_update()).mappings().first()
        if not customer or customer['is_archived'] or customer['employee_id'] != employee_id:
            return False
        table, pk, resource, permission = customer_followup, 'followup_id', 'followup', 'customer.read'
    else:
        spec = {
            'customer_profile': (t.customer_profile, 'customer_id', 'customer', 'customer.read'),
            'service_ticket': (t.service_ticket, 'ticket_id', 'ticket', 'ticket.read'),
            'employee_daily_report': (employee_daily_report, 'daily_report_id', 'daily', 'daily.read'),
        }.get(kind)
        if spec is None:
            return False
        table, pk, resource, permission = spec
    if not ctx.can(permission):
        return False
    row = db.execute(select(table).where(table.c[pk] == entity_id,
        scope(ctx, resource, table)).with_for_update()).mappings().first()
    if not row:
        return False
    if kind == 'customer_followup':
        if row['followup_status'] != 'pending' or not row['next_followup_at'] or row['next_followup_at'] > now:
            return False
        if notification['event_code'] == 'enterprise.customer.followup_due':
            return notification['dedupe_key'] == _key(notification, _generation(row, row['next_followup_at'], now, followup=True))
    elif kind == 'customer_profile':
        return not row['is_archived'] and row['employee_id'] == employee_id
    elif kind == 'service_ticket':
        if row['employee_id'] != employee_id or row['status'] in ('closed', 'awaiting_student'):
            return False
        if notification['event_code'] in ('enterprise.ticket.response_due', 'enterprise.ticket.resolution_due'):
            return any(event == notification['event_code'] and notification['dedupe_key'] == _key(
                notification, _generation(row, deadline, now)) for event, deadline, _ in _ticket_reminders(row, now))
        if notification['event_code'] == 'enterprise.ticket.assigned':
            return notification['dedupe_key'] == _key(notification, row['row_version'])
    elif kind == 'employee_daily_report':
        return row['status'] == 'submitted'
    return True


def _send(notification):
    # 本期站内发布只需原子切换 sent；不调用短信、邮件或模型。
    if notification['channel'] != 'in_app':
        raise ValueError('仅支持站内通知')


def _eligible(now):
    n = t.business_notification.c
    return and_(n.event_code.like('enterprise.%'), or_(
        and_(n.delivery_status.in_(['pending', 'failed']), or_(n.next_retry_at.is_(None), n.next_retry_at <= now)),
        and_(n.delivery_status == 'sending', or_(n.lease_until.is_(None), n.lease_until <= now)),
    ))


def publish_one(db):
    """领取并处理一条企业通知；可恢复过期租约，处理过返回True，无任务返回False。"""
    table = t.business_notification
    now = _utcnow()
    config = policy()
    retry_minutes = config['retry_minutes']
    max_attempts = len(retry_minutes) + 1
    try:
        row = db.execute(select(table).where(_eligible(now)).order_by(table.c.notification_id)
            .limit(1).with_for_update(skip_locked=True)).mappings().first()
        if row is None:
            db.rollback()
            return False
        snapshot = dict(row)
        version = snapshot['row_version'] + 1
        claimed = db.execute(update(table).where(table.c.notification_id == snapshot['notification_id'],
            table.c.row_version == snapshot['row_version'], _eligible(now)).values(
                delivery_status='sending', lease_until=now + timedelta(seconds=config['notification_lease_seconds']),
                attempt_count=min(snapshot['attempt_count'] + 1, max_attempts), row_version=version, updated_at=now))
        db.commit()
        if claimed.rowcount != 1:
            return True
    except Exception:
        db.rollback()
        raise

    def owned():
        return and_(table.c.notification_id == snapshot['notification_id'], table.c.row_version == version,
                    table.c.delivery_status == 'sending', table.c.lease_until > _utcnow())
    try:
        current = _current(db, snapshot, _utcnow()) if snapshot['attempt_count'] < max_attempts else False
        latest = db.execute(select(table).where(owned()).with_for_update()).mappings().first()
        if latest is None:
            db.rollback()
            return True
        values = {'lease_until': None, 'next_retry_at': None, 'row_version': version + 1, 'updated_at': _utcnow()}
        if snapshot['attempt_count'] >= max_attempts:
            values.update(delivery_status='dead_letter', last_error_code='MAX_ATTEMPTS')
        elif not current:
            values.update(delivery_status='dead_letter', last_error_code='BUSINESS_CHANGED')
        else:
            _send(dict(latest))
            values.update(delivery_status='sent', sent_at=_utcnow(), last_error_code=None)
        db.execute(update(table).where(owned()).values(**values))
        db.commit()
    except Exception:
        db.rollback()
        attempt = snapshot['attempt_count'] + 1
        terminal = attempt >= max_attempts
        db.execute(update(table).where(owned()).values(
            delivery_status='dead_letter' if terminal else 'failed',
            next_retry_at=None if terminal else _utcnow() + timedelta(minutes=retry_minutes[attempt - 1]),
            lease_until=None, last_error_code='DELIVERY_FAILED', row_version=version + 1, updated_at=_utcnow()))
        db.commit()
    return True
