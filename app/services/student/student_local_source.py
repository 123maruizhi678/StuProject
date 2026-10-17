"""本地教务/CRM为当前权威；维护动作由真人角色、绑定及版本授权。"""
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import insert, select, update
from app.core.common.response import BusinessException
from app.models import common as t
from app.services.student.student_service import StudentService, events, progress, utcnow, next_setting_time, public_row


from app.schemas.student.student_local_source import LocalAcademic, LocalProgress

class LocalStudentSource(StudentService):
    def authorize(self,actor,student_id,kind):
        if actor.actor_type!='employee':
            raise BusinessException('需要本地维护人员身份',403)
        employee=self.db.execute(select(t.employee).where(t.employee.c.employee_id==actor.actor_id)).mappings().first()
        student=self.student_record(student_id)
        role,permission=('academic','student.academic.maintain') if kind=='academic' else ('consultant','student.progress.maintain')
        roles=set(employee['role_codes'] or []) if employee else set()
        permitted_role=bool({'consultant','manager'} & roles) if kind=='progress' else 'academic' in roles
        if not employee or employee['status']!='active' or permission not in actor.scopes or not permitted_role:
            raise BusinessException('缺少本地维护动作权限',403)
        if employee['department_id']!=student['department_id']:
            raise BusinessException('学生不在本人维护范围',404)
        if kind=='academic':
            b=t.student_staff_binding
            binding=self.db.execute(select(b.c.binding_id).where(b.c.student_id==student_id,b.c.employee_id==actor.actor_id,b.c.relation_type=='score_editor',b.c.status=='active',b.c.valid_from<=utcnow(),__import__('sqlalchemy').or_(b.c.valid_to.is_(None),b.c.valid_to>utcnow()))).first()
            if not binding:
                raise BusinessException('缺少该学生有效教务绑定',403)
        else:
            c=t.customer_profile
            customer=self.db.execute(select(c.c.customer_id).where(c.c.customer_id==student['customer_id'],__import__('sqlalchemy').or_(c.c.employee_id==actor.actor_id,__import__('sqlalchemy').and_('manager' in roles,c.c.department_id==employee['department_id'])),c.c.is_archived.is_(False))).first()
            if not customer:
                raise BusinessException('缺少该学生对应客户的负责关系',403)

    def maintain(self,actor,key,student_id,kind,body):
        self.authorize(actor,student_id,kind)
        def apply(_):
            self.lock_business_prefix(student_id,[actor.actor_id])
            self.authorize(actor,student_id,kind)
            now=utcnow()
            table=events if kind=='academic' else progress
            row=self._load(table,body.id,lock=True) if body.id else None
            if row and (row['student_id']!=student_id or row['source_system']!='local'):
                raise BusinessException('对象不属于本地权威范围',404)
            if kind=='academic':
                if row and body.expected_version!=row['event_version']:
                    raise BusinessException('节点版本冲突',409)
                values=body.model_dump(exclude={'id','expected_version','external_event_id','source_updated_at'})
                from app.schemas.student.student import as_utc
                values['due_at']=as_utc(body.due_at)
                values.update(source_system='local',source_updated_at=now,synced_at=None,updated_at=now)
                version=row['event_version']+1 if row else 1
                if row:
                    self.db.execute(update(events).where(events.c.id==row['id'],events.c.event_version==body.expected_version).values(**values,event_version=version))
                    from .student_sync import StudentSyncService
                    StudentSyncService(self.db)._replan(row['id'],values['due_at'],values['event_status'],version)
                    entity_id=row['id']
                else:
                    if body.expected_version is not None:
                        raise BusinessException('新增节点不能指定旧版本',400)
                    entity_id=self.db.execute(insert(events).values(**values,student_id=student_id,external_event_id='local:'+uuid4().hex,event_version=1,created_at=now)).inserted_primary_key[0]
                receipt={'id':entity_id,'event_version':version}
            else:
                from app.schemas.student.student import as_utc
                if row and (body.expected_updated_at is None or as_utc(body.expected_updated_at)!=row['updated_at']):
                    raise BusinessException('进度版本冲突',409)
                values=body.model_dump(exclude={'id','expected_updated_at','source_updated_at'})
                changed_at=next_setting_time(row)
                values.update(source_system='local',source_updated_at=changed_at,synced_at=None,updated_at=changed_at)
                if row:
                    if (row['external_application_id'],row['stage_code'])!=(body.external_application_id,body.stage_code):
                        raise BusinessException('修改不能更换申请或阶段标识',400)
                    self.db.execute(update(progress).where(progress.c.id==row['id'],progress.c.updated_at==as_utc(body.expected_updated_at)).values(**values))
                    entity_id=row['id']
                else:
                    entity_id=self.db.execute(insert(progress).values(**values,student_id=student_id,created_at=now)).inserted_primary_key[0]
                receipt=public_row({'id':entity_id,'updated_at':changed_at})
            return receipt,entity_id,receipt
        return self._write(actor,'local.'+kind,key,[student_id,body.model_dump(mode='json')],apply)
