"""按事件前缀消费站内通知；五分钟补扫、60秒租约、24小时督办。"""
from datetime import timedelta
from uuid import uuid4
from app.core.common.response import BusinessException
from sqlalchemy import select, update, and_, or_, insert
from app.config import settings
from app.models import common as t
from app.models.student.student_conversation import turns
from app.core.student.student_auth import Principal
from app.services.student.student_service import StudentService, events, reminders, warnings, reminder_generation, utcnow, digest, notification_key
from app.services.student.student_policy import ROUND_SECONDS, NOTIFICATION_RETRY_MINUTES

class StudentTasks:
    def __init__(self, session_factory, sender=None):
        self.sessions=session_factory
        self.sender=sender or self.send

    @staticmethod
    def send(notification):
        if notification['channel'] != 'in_app':
            raise ValueError('本期仅启用站内发布')

    @staticmethod
    def current(db, n):
        service=StudentService(db)
        if n['student_id'] is not None:
            try:
                service.student_record(n['student_id'])
            except Exception:
                return False
        else:
            employee=db.execute(select(t.employee).where(t.employee.c.employee_id==n['employee_id'])).mappings().first()
            if not employee or employee['status']!='active':
                return False
        kind=n['entity_type']
        if n['event_code'].endswith('.transferred'):
            field='reviewer_id' if kind=='student_admin_service' else 'follower_id'
            return bool(db.execute(select(t.operation_log.c.operation_log_id).where(t.operation_log.c.entity_id==n['entity_id'],t.operation_log.c.action_code.in_(['leave.assign','warning.assign']),t.operation_log.c.before_data[field].as_integer()==n['employee_id'],t.operation_log.c.operation_status=='succeeded')).first())
        if kind=='student_academic_reminder':
            row=db.execute(select(reminders).where(reminders.c.id==n['entity_id'])).mappings().first()
            if not row or row['status']!='queued' or row['student_id']!=n['student_id']:
                return False
            event=db.execute(select(events).where(events.c.id==row['academic_event_id'])).mappings().first()
            return bool(event and event['event_status']=='active' and event['event_version']==row['event_version'] and n['event_code']=='student.academic.reminder' and n['dedupe_key']==notification_key('student_academic_reminder',row['id'],'student.academic.reminder',row['student_id'],None,reminder_generation(row)))
        if kind=='mental_warning':
            row=db.execute(select(warnings).where(warnings.c.id==n['entity_id'])).mappings().first()
            if not row:
                return False
            if '.takeover.' in n['event_code']:
                return row['follower_status']!='closed' and row['student_id'] in settings.STUDENT_WARNING_ASSIGNMENT_SCOPES.get(n['employee_id'],[]) and n['employee_id'] in settings.STUDENT_WARNING_ASSIGNER_IDS
            return row['follower_status']!='closed' and row['follower_id']==n['employee_id'] and service.bound(n['employee_id'],row['student_id'])
        if kind in ('leave','student_admin_service'):
            row=db.execute(select(t.student_admin_service).where(t.student_admin_service.c.id==n['entity_id'])).mappings().first()
            if not row:
                return False
            if n['student_id'] is not None:
                return row['student_id']==n['student_id'] and n['event_code']=='student.leave.'+row['approval_status']
            if '.takeover.' in n['event_code']:
                student=service.student_record(row['student_id'])
                return row['approval_status']=='pending' and 'manager' in (employee['role_codes'] or []) and employee['department_id']==student['department_id']
            return (row['approval_status']=='pending' or (row['approval_status']=='cancelled' and n['event_code']=='student.leave.cancelled')) and row['reviewer_id']==n['employee_id'] and service.bound(n['employee_id'],row['student_id'])
        if kind in ('ticket','service_ticket'):
            row=db.execute(select(t.service_ticket).where(t.service_ticket.c.ticket_id==n['entity_id'])).mappings().first()
            if not row:
                return False
            if n['student_id'] is not None:
                return row['student_id']==n['student_id']
            b=t.student_staff_binding
            relation=db.execute(select(b.c.binding_id).where(b.c.student_id==row['student_id'],b.c.employee_id==n['employee_id'],b.c.relation_type.in_(['class_teacher','service_advisor']),b.c.status=='active',b.c.valid_from<=utcnow(),or_(b.c.valid_to.is_(None),b.c.valid_to>utcnow()))).first()
            return row['employee_id']==n['employee_id'] and employee['department_id']==row['handling_department_id'] and 'teacher' in (employee['role_codes'] or []) and bool(relation)
        return False

    def prepare(self,limit=100):
        count=0
        with self.sessions() as db:
            service=StudentService(db)
            candidates=db.execute(select(reminders.c.id,reminders.c.academic_event_id,reminders.c.student_id).where(reminders.c.status=='pending',reminders.c.notify_at<=utcnow()).order_by(reminders.c.academic_event_id,reminders.c.id).limit(limit)).all()
            for c in candidates:
                try:
                    service.lock_business_prefix(c.student_id)
                except BusinessException:
                    db.rollback()
                    continue
                event=db.execute(select(events).where(events.c.id==c.academic_event_id).with_for_update()).mappings().first()
                row=db.execute(select(reminders).where(reminders.c.id==c.id).with_for_update()).mappings().first()
                if not row or row['status']!='pending' or row['notify_at']>utcnow():
                    db.rollback()
                    continue
                if not event or event['event_status']!='active' or event['event_version']!=row['event_version'] or event['due_at']<=utcnow():
                    db.execute(update(reminders).where(reminders.c.id==row['id']).values(status='cancelled',updated_at=row['updated_at']))
                else:
                    db.execute(update(reminders).where(reminders.c.id==row['id']).values(status='queued',updated_at=row['updated_at']))
                    generation=reminder_generation(row)
                    service.notify('student_academic_reminder',row['id'],'academic.reminder','你有学业节点即将到期',student_id=row['student_id'],version=generation)
                    count+=1
                db.commit()
        return count

    def discover_assignments(self,limit=100):
        """不自动替换负责人；只生成受控接管待办与本轮最小通知。"""
        count=0
        with self.sessions() as db:
            from app.services.student.student_assignments import StudentAssignments
            service=StudentAssignments(db)
            # 资格恢复/已办结后结束旧督办代次，下一次失效另建代次；普通业务版本不重置轮次。
            active=db.execute(select(t.operation_log).where(t.operation_log.c.action_code=='takeover.discover',t.operation_log.c.finished_at.is_(None))).mappings().all()
            for entry in active:
                table=t.student_admin_service if entry['entity_type']=='student_admin_service' else warnings
                owner=table.c.reviewer_id if table is t.student_admin_service else table.c.follower_id
                row=db.execute(select(table).where(table.c.id==entry['entity_id'])).mappings().first()
                live=bool(row and (row['approval_status']=='pending' if table is t.student_admin_service else row['follower_status']!='closed'))
                valid=bool(db.scalar(select(service.valid_owner_condition(table,owner)).where(table.c.id==entry['entity_id']))) if row else False
                if not live or valid:
                    db.execute(update(t.operation_log).where(t.operation_log.c.operation_log_id==entry['operation_log_id']).values(finished_at=utcnow(),updated_at=utcnow(),row_version=t.operation_log.c.row_version+1))
            db.commit()
            for kind,table,owner in [('leave',t.student_admin_service,t.student_admin_service.c.reviewer_id),('warning',warnings,warnings.c.follower_id)]:
                conditions=[table.c.approval_status=='pending',table.c.apply_type=='leave'] if kind=='leave' else [table.c.follower_status!='closed']
                candidates=db.execute(select(table).where(*conditions,~service.valid_owner_condition(table,owner)).order_by(table.c.id).limit(limit)).mappings().all()
                for row in candidates:
                    try:
                        service.lock_business_prefix(row['student_id'])
                    except BusinessException:
                        db.rollback()
                        continue
                    current=db.execute(select(table).where(table.c.id==row['id'],*conditions,~service.valid_owner_condition(table,owner)).with_for_update()).mappings().first()
                    if not current:
                        db.rollback()
                        continue
                    op=db.execute(select(t.operation_log).where(t.operation_log.c.action_code=='takeover.discover',t.operation_log.c.entity_type==table.name,t.operation_log.c.entity_id==row['id'],t.operation_log.c.finished_at.is_(None)).order_by(t.operation_log.c.operation_log_id).with_for_update()).mappings().first()
                    now=utcnow()
                    if not op:
                        operation_key=digest(['student.takeover',kind,row['id'],uuid4().hex])
                        db.execute(insert(t.operation_log).values(operation_key=operation_key,service_code='student_tasks',action_code='takeover.discover',entity_type=table.name,entity_id=row['id'],request_key=operation_key,parameters_hash=digest([kind,row['id']]),operation_status='succeeded',after_data={'generation':operation_key,'baseline':now.isoformat()},row_version=1,created_at=now,updated_at=now))
                        baseline=now
                    else:
                        operation_key=op['operation_key']
                        baseline=op['created_at']
                    round_no=max(0,int((now-baseline).total_seconds()//ROUND_SECONDS))
                    if kind=='leave':
                        student=service.student_record(row['student_id'])
                        recipients=[r['employee_id'] for r in db.execute(select(t.employee).where(t.employee.c.department_id==student['department_id'],t.employee.c.status=='active')).mappings() if 'manager' in (r['role_codes'] or [])]
                    else:
                        recipients=[eid for eid in settings.STUDENT_WARNING_ASSIGNER_IDS if row['student_id'] in settings.STUDENT_WARNING_ASSIGNMENT_SCOPES.get(eid,[])]
                    for eid in sorted(set(recipients)):
                        service.notify(table.name,row['id'],f'{kind}.takeover.{round_no}','有事项需要分派负责人',employee_id=eid,version=f'{operation_key}:{round_no}')
                    db.commit()
                    count+=1
        return count

    def dispatch(self,limit=100):
        n=t.business_notification
        now=utcnow()
        with self.sessions() as db:
            candidates=db.execute(select(n).where(n.c.event_code.like('student.%'),or_(and_(n.c.delivery_status.in_(['pending','failed']),or_(n.c.next_retry_at.is_(None),n.c.next_retry_at<=now)),and_(n.c.delivery_status=='sending',n.c.lease_until<now))).order_by(n.c.notification_id).limit(limit)).mappings().all()
        counts={'sent':0,'failed':0,'skipped':0}
        for snapshot in candidates:
            with self.sessions() as db:
                version=snapshot['row_version']+1
                changed=db.execute(update(n).where(n.c.notification_id==snapshot['notification_id'],n.c.row_version==snapshot['row_version']).values(delivery_status='sending',row_version=version,lease_until=utcnow()+timedelta(seconds=settings.STUDENT_NOTIFICATION_LEASE_SECONDS),updated_at=utcnow()))
                db.commit()
                if changed.rowcount!=1:
                    continue
                # 取得部门总锁序后，再按节点→提醒→通知排序锁定并最终复验。
                kind=snapshot['entity_type']
                service=StudentService(db)
                row=None
                if kind=='student_academic_reminder':
                    row=db.execute(select(reminders).where(reminders.c.id==snapshot['entity_id'])).mappings().first()
                    if row:
                        service.lock_business_prefix(row['student_id'])
                        db.execute(select(events.c.id).where(events.c.id==row['academic_event_id']).with_for_update()).all()
                        db.execute(select(reminders.c.id).where(reminders.c.id==row['id']).with_for_update()).all()
                elif kind in ('leave','student_admin_service','mental_warning','ticket','service_ticket'):
                    table={'leave':t.student_admin_service,'student_admin_service':t.student_admin_service,'mental_warning':warnings,'ticket':t.service_ticket,'service_ticket':t.service_ticket}[kind]
                    owner=db.scalar(select(table.c.student_id).where(next(iter(table.primary_key.columns))==snapshot['entity_id']))
                    if owner:
                        service.lock_business_prefix(owner)
                        db.execute(select(next(iter(table.primary_key.columns))).where(next(iter(table.primary_key.columns))==snapshot['entity_id']).with_for_update()).all()
                latest=db.execute(select(n).where(n.c.notification_id==snapshot['notification_id'],n.c.row_version==version,n.c.delivery_status=='sending').with_for_update()).mappings().first()
                if not latest:
                    db.rollback()
                    continue
                if not self.current(db,latest):
                    db.execute(update(n).where(n.c.notification_id==latest['notification_id']).values(delivery_status='dead_letter',last_error_code='BUSINESS_CHANGED',lease_until=None,row_version=version+1))
                    db.commit()
                    counts['skipped']+=1
                    continue
                try:
                    self.sender(dict(latest))
                    db.execute(update(n).where(n.c.notification_id==latest['notification_id'],n.c.row_version==version).values(delivery_status='sent',sent_at=utcnow(),lease_until=None,last_error_code=None,attempt_count=latest['attempt_count']+1,row_version=version+1,updated_at=utcnow()))
                    if row:
                        db.execute(update(reminders).where(reminders.c.id==row['id'],reminders.c.event_version==row['event_version'],reminders.c.updated_at==row['updated_at'],reminders.c.status=='queued').values(status='sent',sent_at=utcnow(),updated_at=row['updated_at']))
                    db.commit()
                    counts['sent']+=1
                except Exception:
                    db.rollback()
                    attempt=latest['attempt_count']+1
                    delay=NOTIFICATION_RETRY_MINUTES[min(attempt-1,len(NOTIFICATION_RETRY_MINUTES)-1)]
                    db.execute(update(n).where(n.c.notification_id==latest['notification_id'],n.c.row_version==version,n.c.delivery_status=='sending').values(delivery_status='dead_letter' if attempt>=settings.STUDENT_NOTIFICATION_MAX_ATTEMPTS else 'failed',attempt_count=attempt,next_retry_at=utcnow()+timedelta(minutes=delay),last_error_code='DELIVERY_FAILED',lease_until=None,row_version=version+1,updated_at=utcnow()))
                    db.commit()
                    counts['failed']+=1
        return counts

    def pending_model_results(self):
        """恢复时仅列出待核实轮次；不发送模型请求，也不删除会话历史。"""
        with self.sessions() as db:
            chat=[{'kind':'chat',**dict(r)} for r in db.execute(select(turns.c.id,turns.c.session_id,turns.c.student_id,turns.c.created_at).where(turns.c.result.is_(None)).order_by(turns.c.id)).mappings()]
            monitor=[{'kind':'mental',**dict(r)} for r in db.execute(select(t.operation_log.c.operation_log_id,t.operation_log.c.student_id,t.operation_log.c.created_at).where(t.operation_log.c.action_code=='mental.model',t.operation_log.c.operation_status=='pending_external')).mappings()]
            return chat+monitor

    def run_once(self):
        return {'reminders_queued':self.prepare(),'assignments_checked':self.discover_assignments(),**self.dispatch()}
