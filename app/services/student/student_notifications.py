"""站内通知的当前可见范围；已读与业务办结分别处理。"""
from sqlalchemy import select
from app.models import common as t
from app.core.common.response import BusinessException
from .student_service import StudentService, public_row, warnings, reminders


def visible(db, notification, actor):
    if notification['channel']!='in_app' or notification['delivery_status']!='sent':
        return False
    owner='student_id' if actor.actor_type=='student' else 'employee_id'
    if notification[owner]!=actor.actor_id:
        return False
    service=StudentService(db)
    if actor.actor_type=='student':
        service.student(actor)
        return True
    employee=db.execute(select(t.employee).where(t.employee.c.employee_id==actor.actor_id)).mappings().first()
    if not employee or employee['status']!='active':
        return False
    kind, entity=notification['entity_type'],notification['entity_id']
    table = {'leave':t.student_admin_service,'student_admin_service':t.student_admin_service,
             'mental_warning':warnings,'student_academic_reminder':reminders,
             'ticket':t.service_ticket,'service_ticket':t.service_ticket}.get(kind)
    if table is None:
        return False
    row=db.execute(select(table).where(next(iter(table.primary_key.columns))==entity)).mappings().first()
    if not row:
        return False
    if kind=='mental_warning':
        if '.takeover.' in notification['event_code']:
            return actor.actor_id in __import__('app.config',fromlist=['settings']).settings.STUDENT_WARNING_ASSIGNER_IDS and row['student_id'] in __import__('app.config',fromlist=['settings']).settings.STUDENT_WARNING_ASSIGNMENT_SCOPES.get(actor.actor_id,[])
        return bool(row['follower_id']==actor.actor_id and service.bound(actor.actor_id,row['student_id']) and 'student.warning.read' in actor.scopes)
    if kind in ('leave','student_admin_service'):
        return bool(row['reviewer_id']==actor.actor_id and service.bound(actor.actor_id,row['student_id']) and 'student.admin_service.review' in actor.scopes)
    return False


def list_own(db, actor, limit=20, offset=0, unread=None):
    column=t.business_notification.c.student_id if actor.actor_type=='student' else t.business_notification.c.employee_id
    statement=select(t.business_notification).where(column==actor.actor_id,t.business_notification.c.channel=='in_app',t.business_notification.c.delivery_status=='sent')
    if actor.actor_type=='employee':
        statement=statement.where(t.business_notification.c.event_code.like('student.%'))
    candidates=db.execute(statement.order_by(t.business_notification.c.notification_id.desc())).mappings().all()
    rows=[r for r in candidates if visible(db,r,actor)]
    unread_count=sum(r['read_at'] is None for r in rows)
    if unread is not None:
        rows=[r for r in rows if (r['read_at'] is None)==unread]
    fields=('notification_id','entity_type','entity_id','event_code','title','content','sent_at','read_at','created_at')
    return {'items':[public_row({k:r[k] for k in fields}) for r in rows[offset:offset+limit]],'total':len(rows),'limit':limit,'offset':offset,'unread_count':unread_count}


def detail(db,actor,entity_id):
    row=db.execute(select(t.business_notification).where(t.business_notification.c.notification_id==entity_id)).mappings().first()
    if not row or not visible(db,row,actor):
        raise BusinessException('通知不存在',404)
    return public_row({k:row[k] for k in ('notification_id','entity_type','entity_id','event_code','title','content','sent_at','read_at','created_at')})
