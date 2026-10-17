"""企业工单动作：分派、人工回应和给方案；学生保留关闭／重开权。"""
from datetime import datetime
from sqlalchemy import insert,select,and_,or_
from app.models import common as t
from app.core.enterprise.enterprise_authorization import error
from app.repositories.enterprise.enterprise_repository import public,digest

class TicketService:
    def __init__(self,repo):self.repo=repo
    def teacher(self,employee_id,row):
        db=self.repo.db;now=datetime.utcnow();e=t.employee;b=t.student_staff_binding
        employee=db.execute(select(e).where(e.c.employee_id==employee_id)).mappings().first()
        if employee and employee['status']=='active' and 'admin' in employee['role_codes']:return
        if not employee or employee['status']!='active' or employee['department_id']!=row['handling_department_id'] or 'teacher' not in employee['role_codes']:error(403,'处理人须为本部门有效老师')
        binding=db.scalar(select(b.c.binding_id).where(b.c.employee_id==employee_id,b.c.student_id==row['student_id'],b.c.relation_type.in_(['class_teacher','service_advisor']),b.c.status=='active',b.c.valid_from<=now,or_(b.c.valid_to.is_(None),b.c.valid_to>now)).limit(1))
        if not binding:error(403,'处理人缺少有效学生服务关系')
    def mutate(self,verb,ticket_id,key,params):
        action='ticket.assign' if verb=='assign' else 'ticket.handle';self.repo.ctx.require(action)
        def check(lock=False):
            row=self.repo.one('ticket',ticket_id,lock=lock)
            if verb!='assign' and not self.repo.ctx.is_admin:
                self.teacher(self.repo.ctx.employee_id,row)
                if row['employee_id']!=self.repo.ctx.employee_id:error(403,'仅当前处理人可办理')
            return row
        def work():
            row=check(True);now=datetime.utcnow();ctx=self.repo.ctx
            from app.services.enterprise.enterprise_ticket_policy import existing_cycle_snapshot
            snapshot=existing_cycle_snapshot(self.repo.db,row)
            if row['status']=='closed':error(409,'已关闭工单不可由企业变更')
            if verb=='assign':
                self.teacher(params['employee_id'],row)
                values={'employee_id':params['employee_id'],'status':'awaiting_student' if row['status']=='awaiting_student' else 'assigned'}
            elif verb=='resolve':
                if row['status'] not in ('assigned','processing','reopened'):error(409,'当前状态不能给出方案')
                values={'status':'awaiting_student','solution':params['content'],'resolved_at':now}
            else:
                if row['status'] not in ('assigned','processing','reopened','awaiting_student'):error(409,'当前状态不能回应')
                values={'status':'processing'} if row['status']!='awaiting_student' else {}
            visible=verb=='resolve' or (verb=='followup' and params.get('visibility')=='student_visible')
            if visible and row['first_response_at'] is None:values['first_response_at']=now
            result=self.repo.version_update('ticket',row,params.get('expected_version'),values)
            self.repo.db.execute(insert(t.service_ticket_record).values(ticket_id=ticket_id,record_type={'assign':'assign','resolve':'resolve','followup':'reply'}[verb],employee_id=ctx.employee_id,content=params.get('content') or params['reason'],visibility='student_visible' if visible else 'internal',to_status=result['status'],cycle_no=row['reopen_count']+1,record_key=digest([ticket_id,verb,key]),sla_snapshot={**snapshot,'event_at':now.isoformat(),'event':verb},created_at=now))
            from app.services.enterprise.enterprise_notification import enqueue
            if visible:enqueue(self.repo.db,event='student.ticket.awaiting_student' if verb=='resolve' else 'student.ticket.reply',entity_type='service_ticket',entity_id=ticket_id,student_id=row['student_id'],version=result['row_version'],title='工单处理有新进展')
            elif verb=='assign':enqueue(self.repo.db,event='enterprise.ticket.assigned',entity_type='service_ticket',entity_id=ticket_id,employee_id=params['employee_id'],version=result['row_version'],title='收到工单分派')
            return public(result),row,'service_ticket',ticket_id
        return self.repo.operation('enterprise.'+action,key,{'verb':verb,'id':ticket_id,**params},work,lambda:check())
