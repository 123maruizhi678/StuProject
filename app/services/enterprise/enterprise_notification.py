"""单表通知生产、当前权限可见性与幂等已读。"""
from datetime import datetime
from sqlalchemy import insert,select,update,or_,and_
from sqlalchemy.exc import IntegrityError
from app.models import common as t
from app.models import enterprise as own
from app.core.enterprise.enterprise_authorization import scope,error
from app.repositories.enterprise.enterprise_repository import digest

def enqueue(db,*,event,entity_type,entity_id,version,title,employee_id=None,student_id=None):
    if (employee_id is None)==(student_id is None):raise ValueError('通知接收人必须二选一')
    key=event+':'+digest([entity_type,entity_id,version,employee_id,student_id,'in_app'])
    if db.scalar(select(t.business_notification.c.notification_id).where(t.business_notification.c.dedupe_key==key)):return
    try:
        with db.begin_nested():
            db.execute(insert(t.business_notification).values(entity_type=entity_type,entity_id=entity_id,event_code=event,employee_id=employee_id,student_id=student_id,channel='in_app',title=title,content='请在当前授权的业务工作台查看并办理。',dedupe_key=key,delivery_status='pending',attempt_count=0,row_version=1,created_at=datetime.utcnow(),updated_at=datetime.utcnow()))
    except IntegrityError:
        # 并发扫描相同轮次只吸收唯一键重放；其他外键或数据错误继续使主事务回滚。
        if not db.scalar(select(t.business_notification.c.notification_id).where(t.business_notification.c.dedupe_key==key).with_for_update()):raise

def visibility(ctx):
    n=t.business_notification;clauses=[]
    if ctx.is_admin:return and_(n.c.channel=='in_app',n.c.event_code.like('enterprise.%'),n.c.delivery_status=='sent')
    for entity,resource,table,pk in [('customer_profile','customer',t.customer_profile,'customer_id'),('customer_followup','followup',own.customer_followup,'followup_id'),('service_ticket','ticket',t.service_ticket,'ticket_id'),('employee_daily_report','daily',own.employee_daily_report,'daily_report_id')]:
        clauses.append(and_(n.c.entity_type==entity,select(table.c[pk]).where(table.c[pk]==n.c.entity_id,scope(ctx,resource,table)).exists()))
    return and_(n.c.employee_id==ctx.employee_id,n.c.channel=='in_app',n.c.event_code.like('enterprise.%'),n.c.delivery_status=='sent',or_(*clauses))

def mark_read(repo,notification_id):
    repo.ctx.require('notification.read_own');n=t.business_notification
    row=repo.db.execute(select(n).where(n.c.notification_id==notification_id,visibility(repo.ctx))).mappings().first()
    if not row:error(404,'消息不存在或不可见')
    if row['read_at'] is None:
        repo.db.execute(update(n).where(n.c.notification_id==notification_id,n.c.read_at.is_(None)).values(read_at=datetime.utcnow(),row_version=n.c.row_version+1))
        repo.db.commit()
    return {'notification_id':notification_id,'read_at':row['read_at'] or repo.db.scalar(select(n.c.read_at).where(n.c.notification_id==notification_id))}
