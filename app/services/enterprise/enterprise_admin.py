"""企业配置动作，普通业务写入不能顺带变更角色和关系。"""
from datetime import datetime
from sqlalchemy import insert,select,and_,or_
from app.models import common as t
from app.repositories.enterprise.enterprise_repository import RESOURCES,public
from app.core.enterprise.enterprise_authorization import error
from app.services.enterprise.enterprise_customer import utc
from app.core.common.position_roles import roles_for_position

class AdminService:
    def __init__(self,repo):self.repo=repo
    def get(self,resource,object_id,lock=False):
        table,pk=RESOURCES[resource];q=select(table).where(table.c[pk]==object_id)
        if lock:q=q.with_for_update()
        row=self.repo.db.execute(q).mappings().first()
        if not row:error(404,'配置对象不存在')
        return dict(row)
    def mutate(self,resource,verb,key,params,object_id=None):
        action={'department':'organization.manage','employee':'employee.manage','binding':'binding.manage'}[resource]
        if verb=='roles':action='role.manage'
        self.repo.ctx.require(action)
        def work():
            now=datetime.utcnow();values=dict(params);expected=values.pop('expected_version',None);values.pop('reason',None)
            table,pk=RESOURCES[resource];before=None
            if object_id:
                if resource=='binding':
                    preliminary=self.get(resource,object_id)
                    self.repo.db.execute(select(t.student_profile.c.student_id).where(t.student_profile.c.student_id==preliminary['student_id']).with_for_update()).first()
                before=self.get(resource,object_id,True)
            if resource=='department':
                parent=values.get('parent_department_id')
                seen={object_id}
                while parent:
                    if parent in seen:error(409,'部门层级不能成环')
                    seen.add(parent);parent=self.get('department',parent,True)['parent_department_id']
                if verb=='disable':
                    if not params.get('reason'):error(400,'停用原因必填')
                    for dep,cond in [(t.employee,t.employee.c.department_id==object_id),(t.customer_profile,t.customer_profile.c.department_id==object_id),(t.student_profile,t.student_profile.c.department_id==object_id),(t.org_department,t.org_department.c.parent_department_id==object_id)]:
                        if self.repo.db.execute(select(dep).where(cond).limit(1)).first():error(409,'部门仍有员工、子部门或业务关联')
                    values={'status':'disabled'}
                elif verb=='create':values['status']='active'
            if resource=='employee':
                if verb=='create':
                    if self.get('department',values['department_id'])['status']!='active':error(400,'部门不可用')
                    values.update(role_codes=roles_for_position(values['position_title']) if values.get('position_title') else ['employee'],status='active')
                if verb=='update' and 'position_title' in values and values['position_title']!=before['position_title']:
                    self.repo.ctx.require('role.manage')
                    if object_id==self.repo.ctx.employee_id:error(403,'不能通过职位变更修改自身授权')
                    values['role_codes']=roles_for_position(values['position_title'])
                if verb=='roles':
                    if object_id==self.repo.ctx.employee_id:error(403,'不能通过本接口修改自身角色')
                    mapped=roles_for_position(before['position_title'])
                    if set(values['role_codes'])!=set(mapped):error(409,'业务角色由职位映射决定，请通过受控职位变更调整权限')
                    values={'role_codes':list(dict.fromkeys(values['role_codes']))}
                if values.get('status')=='left' and not values.get('left_date'):error(400,'离职日期必填')
            if resource=='binding':
                if verb=='create':
                    self.get('student',values['student_id']);self.get('employee',values['employee_id'])
                    values['valid_from']=utc(values['valid_from']);values['valid_to']=utc(values.get('valid_to'));values['status']='active'
                elif verb=='disable':values={'status':'disabled','is_primary':False}
                elif 'valid_to' in values:values['valid_to']=utc(values['valid_to'])
                merged={**(before or {}),**values}
                self.repo.db.execute(select(t.student_profile.c.student_id).where(t.student_profile.c.student_id==merged['student_id']).with_for_update()).first()
                if merged.get('valid_to') and merged['valid_to']<=merged['valid_from']:error(400,'关系期限无效')
                if merged['relation_type']=='score_editor' and not merged.get('course_scope_code'):error(400,'成绩人员须指定课程授权')
                if merged.get('is_primary') and merged['relation_type']=='class_teacher' and merged['status']=='active':
                    b=t.student_staff_binding
                    existing=self.repo.db.scalar(select(b.c.binding_id).where(b.c.student_id==merged['student_id'],b.c.binding_id!=(object_id or 0),b.c.relation_type=='class_teacher',b.c.status=='active',b.c.is_primary==True,b.c.valid_from<=(merged.get('valid_to') or datetime.max),or_(b.c.valid_to.is_(None),b.c.valid_to>merged['valid_from'])).limit(1))
                    if existing:error(409,'该学生已有时间重叠的有效主班主任')
            if object_id:
                result=self.repo.version_update(resource,before,expected,values);rid=object_id
            else:
                values.update(row_version=1,created_at=now,updated_at=now)
                rid=self.repo.db.execute(insert(table).values(**values)).inserted_primary_key[0];result={**values,pk:rid}
            return public(result),before,table.name,rid
        return self.repo.operation('enterprise.'+action,key,{'verb':verb,'resource':resource,'id':object_id,**params},work,lambda:self.repo.ctx.require(action))
