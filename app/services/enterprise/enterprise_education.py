"""企业本地教务与CRM固定服务；共享节点改期时同事务重排已有学生提醒。"""
from datetime import datetime,timedelta
from uuid import uuid4
from sqlalchemy import select,insert,update
from app.models import common as t
from app.models import enterprise as own
from app.repositories.enterprise.enterprise_repository import RESOURCES,public
from app.core.enterprise.enterprise_authorization import error,valid_binding,scope
from app.services.enterprise.enterprise_customer import utc
from app.services.enterprise.enterprise_score import ScoreService

class EducationService:
    def __init__(self,repo):self.repo=repo
    def authorize(self,resource,values):
        ctx=self.repo.ctx;db=self.repo.db
        if resource=='course':return ctx.require('academic.write')
        st=t.student_profile
        if ctx.is_admin:
            if not db.scalar(select(st.c.student_id).where(st.c.student_id==values['student_id'],st.c.is_archived==False,st.c.status=='active')):error(400,'学生不存在、已停用或已归档')
            return
        if resource=='enrollment':return ScoreService(self.repo).authorized(values['student_id'],values['course_code'])
        if resource=='academic':
            ctx.require('academic.write')
            predicate=valid_binding(ctx,['score_editor'],st.c.student_id)
        else:
            ctx.require('progress.write')
            predicate=select(t.customer_profile.c.customer_id).where(t.customer_profile.c.customer_id==st.c.customer_id,scope(ctx,'customer',t.customer_profile)).exists()
        if not db.scalar(select(st.c.student_id).where(st.c.student_id==values['student_id'],st.c.is_archived==False,predicate)):error(403,'缺少该学生的明确业务授权')
    def mutate(self,resource,verb,key,params,object_id=None):
        action='progress.write' if resource=='progress' else 'academic.write';self.repo.ctx.require(action)
        def check(lock=False):
            row=self.repo.one(resource,object_id,lock=lock);self.authorize(resource,row);return row
        def work():
            db=self.repo.db;table,pk=RESOURCES[resource];now=datetime.utcnow()
            before=check(True) if object_id else None
            values={k:v for k,v in params.items() if k not in ('expected_version','expected_event_version','reason')}
            self.authorize(resource,before or values)
            if before and resource in ('academic','progress') and before['source_system']!='local':error(409,'外部来源事实不能通过本地维护接口修改')
            if resource=='enrollment' and not db.scalar(select(own.enterprise_course.c.course_id).where(own.enterprise_course.c.course_code==(before or values)['course_code'],own.enterprise_course.c.status=='active')):error(400,'课程不存在或已停用')
            if 'due_at' in values:values['due_at']=utc(values['due_at'])
            if resource in ('academic','progress'):
                values['source_updated_at']=now
                if not before:
                    values.update(source_system='local',synced_at=None)
                    values['external_event_id' if resource=='academic' else 'external_application_id']='local:'+uuid4().hex
            if resource=='academic':
                changed=True
                values['event_version']=(before['event_version'] if before else 0)+1
                if before and changed:
                    merged={**before,**values};rem=t.student_academic_reminder
                    reminders=db.execute(select(rem).where(rem.c.academic_event_id==object_id).order_by(rem.c.id).with_for_update()).mappings().all()
                    for row in reminders:
                        # 投递状态不推进设置代次；此处是真实节点重排，保留已取消设置。
                        generation=max(now,row['updated_at']+timedelta(microseconds=1))
                        db.execute(update(rem).where(rem.c.id==row['id']).values(notify_at=merged['due_at']-timedelta(minutes=row['lead_minutes']),event_version=merged['event_version'],status='cancelled' if merged['event_status']=='cancelled' or row['status']=='cancelled' else 'pending',sent_at=None,updated_at=generation))
            if before:
                if resource=='academic':
                    expected=params.get('expected_event_version')
                    if before['event_version']!=expected:error(409,'学业节点版本已变化')
                    updated=db.execute(update(table).where(table.c.id==object_id,table.c.event_version==expected).values(**values,updated_at=now))
                    if updated.rowcount!=1:error(409,'学业节点并发修改冲突')
                    result={**before,**values,'updated_at':now}
                else:result=self.repo.version_update(resource,before,params.get('expected_version'),values)
                rid=object_id
            else:
                values.update(created_at=now,updated_at=now)
                if resource!='academic':values['row_version']=1
                if resource in ('course','enrollment'):values['status']='active'
                if resource=='academic':values.update(event_status='active',source_timezone='Asia/Shanghai')
                rid=db.execute(insert(table).values(**values)).inserted_primary_key[0];result={**values,pk:rid}
            return public(result),before,table.name,rid
        return self.repo.operation('enterprise.'+action,key,{'resource':resource,'verb':verb,'id':object_id,**params},work,lambda:check() if object_id else self.authorize(resource,params))
