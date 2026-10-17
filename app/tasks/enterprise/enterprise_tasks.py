"""企业事件唯一消费与跟进／工单扫描；不会执行审批或学生投递。"""
from datetime import datetime,timedelta
from sqlalchemy import select,update,or_,and_
from app.models import common as t
from app.models.enterprise import customer_followup
from app.core.enterprise.enterprise_authorization import context_for,scope
from app.core.response import BusinessException
from app.services.enterprise.enterprise_notification import enqueue
from app.services.enterprise.enterprise_ticket_policy import policy

def publish_one(db,now=None):
    now=now or datetime.utcnow();now=now.replace(microsecond=now.microsecond//1000*1000);n=t.business_notification
    row=db.execute(select(n).where(n.c.event_code.like('enterprise.%'),n.c.channel=='in_app',or_(and_(n.c.delivery_status.in_(['pending','failed']),or_(n.c.next_retry_at.is_(None),n.c.next_retry_at<=now)),and_(n.c.delivery_status=='sending',n.c.lease_until<now))).order_by(n.c.notification_id).with_for_update(skip_locked=True).limit(1)).mappings().first()
    if row is None:db.rollback();return False
    lease=max(now+timedelta(seconds=policy()['notification_lease_seconds']),(row['lease_until'] or now)+timedelta(milliseconds=1));nid=row['notification_id']
    db.execute(update(n).where(n.c.notification_id==nid).values(delivery_status='sending',lease_until=lease,attempt_count=n.c.attempt_count+1));db.commit()
    state='sent';values={};error=None
    try:
        account=db.scalar(select(t.UserAccount).where(t.UserAccount.employee_id==row['employee_id']))
        if account is None:raise BusinessException('接收人失效',403)
        ctx=context_for(db,account)
        entities={'customer_profile':('customer',t.customer_profile,'customer_id'),'customer_followup':('followup',customer_followup,'followup_id'),'service_ticket':('ticket',t.service_ticket,'ticket_id')}
        if row['entity_type'] not in entities:raise BusinessException('未知企业通知实体',404)
        resource,table,pk=entities[row['entity_type']]
        if not db.scalar(select(table.c[pk]).where(table.c[pk]==row['entity_id'],scope(ctx,resource,table))):raise BusinessException('对象已不可见',403)
        if resource=='followup':
            current=db.execute(select(table).where(table.c[pk]==row['entity_id'])).mappings().one()
            owner=db.scalar(select(t.customer_profile.c.employee_id).where(t.customer_profile.c.customer_id==current['customer_id']))
            if owner!=row['employee_id']:raise BusinessException('客户已更换负责人',409)
            if current['followup_status']!='pending' or not current['next_followup_at'] or current['next_followup_at']>now:raise BusinessException('安排已失效',409)
            from app.repositories.enterprise.enterprise_repository import digest
            op=current['schedule_operation_id']
            base=current['schedule_base_at'] or current['next_followup_at']
            round_no=int((row['created_at']-base).total_seconds()//(policy()['reminder_round_hours']*3600))
            expected=row['event_code']+':'+digest(['customer_followup',current['followup_id'],[op,base.isoformat(),round_no],row['employee_id'],None,'in_app'])
            if row['dedupe_key']!=expected:raise BusinessException('安排代次已失效',409)
        if resource=='ticket' and row['event_code']=='enterprise.ticket.overdue':
            current=db.execute(select(table).where(table.c[pk]==row['entity_id'])).mappings().one()
            due=current['response_due_at'] if current['first_response_at'] is None else (current['resolution_due_at'] if current['status']!='awaiting_student' else None)
            if current['status']=='closed' or due is None or due>=now:raise BusinessException('工单催办已失效',409)
            from app.repositories.enterprise.enterprise_repository import digest
            round_no=int((row['created_at']-due).total_seconds()//(policy()['reminder_round_hours']*3600))
            expected=row['event_code']+':'+digest(['service_ticket',current['ticket_id'],[current['reopen_count'],due.isoformat(),round_no],row['employee_id'],None,'in_app'])
            if expected!=row['dedupe_key']:raise BusinessException('工单轮次已变化',409)
    except BusinessException:state='dead_letter';error='RECIPIENT_OR_EVENT_STALE'
    except Exception:
        attempt=row['attempt_count']+1
        delays=policy()['retry_minutes']
        if attempt>len(delays):state='dead_letter'
        else:state='failed';values['next_retry_at']=now+timedelta(minutes=delays[attempt-1])
        error='TEMPORARY_PUBLISH_FAILURE'
    values.update(delivery_status=state,last_error_code=error,updated_at=now,row_version=n.c.row_version+1)
    if state=='sent':values['sent_at']=now
    db.execute(update(n).where(n.c.notification_id==nid,n.c.delivery_status=='sending',n.c.lease_until==lease).values(**values));db.commit();return True

def scan(db,now=None):
    now=now or datetime.utcnow();count=0
    rows=db.execute(select(customer_followup,t.customer_profile.c.employee_id.label('recipient')).join(t.customer_profile,t.customer_profile.c.customer_id==customer_followup.c.customer_id).where(customer_followup.c.followup_status=='pending',customer_followup.c.next_followup_at<=now,t.customer_profile.c.is_archived==False)).mappings().all()
    for row in rows:
        if not row['recipient']:continue
        base=row['schedule_base_at'] or row['next_followup_at']
        round_no=int((now-base).total_seconds()//(policy()['reminder_round_hours']*3600))
        # 代次为安排时间及产生该版本的成功审计ID；仅跟进创建／改期服务写入。
        op=row['schedule_operation_id']
        if op is None:continue
        enqueue(db,event='enterprise.followup.due',entity_type='customer_followup',entity_id=row['followup_id'],employee_id=row['recipient'],version=[op,base.isoformat(),round_no],title='客户跟进计划已到期');count+=1
    tickets=db.execute(select(t.service_ticket).where(t.service_ticket.c.status!='closed')).mappings().all()
    for row in tickets:
        due=row['response_due_at'] if row['first_response_at'] is None else (row['resolution_due_at'] if row['status']!='awaiting_student' else None)
        if due is None or now<=due:continue
        employees=db.execute(select(t.employee).where(t.employee.c.department_id==row['handling_department_id'],t.employee.c.status=='active')).mappings().all()
        recipients={e['employee_id'] for e in employees if 'manager' in e['role_codes'] or e['employee_id']==row['employee_id']}
        for employee_id in recipients:
            enqueue(db,event='enterprise.ticket.overdue',entity_type='service_ticket',entity_id=row['ticket_id'],employee_id=employee_id,version=[row['reopen_count'],due.isoformat(),int((now-due).total_seconds()//(policy()['reminder_round_hours']*3600))],title='工单已超过处理时限');count+=1
    db.commit();return count
