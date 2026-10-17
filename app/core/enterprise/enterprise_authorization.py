"""有效员工逐动作授权；对象范围必须另外进入固定查询。"""
from dataclasses import dataclass
from datetime import datetime
from fastapi import Depends
from sqlalchemy import select, and_,or_,true
from app.core.auth import get_current_account
from app.core.response import BusinessException
from app.database import get_db
from app.models import common as t

ROLE_ACTIONS={
 'employee':{'access','daily.read','daily.write_own','organization.read','knowledge.read','todo.read_own','notification.read_own','command','query'},
 'consultant':{'customer.read','customer.create','customer.update','customer.status','customer.followup','customer.archive','progress.write'},
 'manager':{'customer.read','customer.create','customer.update','customer.status','customer.followup','customer.archive','customer.assign','daily.read','ticket.read','ticket.assign','progress.write'},
 'teacher':{'student.read','score.read','ticket.read','ticket.handle'},
 'academic':{'student.read','score.read','score.write','score.void','academic.write'},
 'admin':{'organization.manage','employee.manage','role.manage','binding.manage','knowledge.manage','knowledge.publish','audit.read','student.read'},
}
def error(code,message): raise BusinessException(message,code)

@dataclass(frozen=True)
class EmployeeContext:
    user_id:int
    employee_id:int
    department_id:int
    roles:frozenset
    identity_type:str='employee'
    @property
    def is_admin(self):return self.identity_type=='admin' or 'admin' in self.roles
    def can(self,action):
        action=action.removeprefix('enterprise.')
        if self.is_admin:return action in set().union(*ROLE_ACTIONS.values())
        return any(action in ROLE_ACTIONS.get(role,set()) for role in self.roles|{'employee'})
    def require(self,action):
        if not self.can(action): error(403,'没有此业务动作权限')
    def permissions(self):
        if self.is_admin:return sorted('enterprise.'+a for a in set().union(*ROLE_ACTIONS.values()))
        return sorted({'enterprise.'+a for r in self.roles|{'employee'} for a in ROLE_ACTIONS.get(r,set())})

def context_for(db,account,*,lock=False):
    if account.identity_type=='admin':
        from app.core.common.system_admin import admin_actor
        row=admin_actor(db,account.user_id)
        return EmployeeContext(account.user_id,row['employee_id'] if row else None,row['department_id'] if row else None,frozenset({'employee','admin'}),'admin')
    if account.identity_type!='employee' or not account.employee_id:error(403,'仅限有效员工访问')
    query=select(t.employee).where(t.employee.c.employee_id==account.employee_id)
    if lock: query=query.with_for_update()
    row=db.execute(query).mappings().first()
    if not row or row['status']!='active':error(403,'员工已失效')
    department_query=select(t.org_department.c.status).where(t.org_department.c.department_id==row['department_id'])
    if lock:department_query=department_query.with_for_update()
    department=db.execute(department_query).scalar_one_or_none()
    if department!='active':error(403,'所属部门不可用')
    roles=row['role_codes']
    if not isinstance(roles,list) or any(not isinstance(r,str) for r in roles):error(403,'员工角色无效')
    return EmployeeContext(account.user_id,row['employee_id'],row['department_id'],frozenset(roles))

def current_employee(account=Depends(get_current_account),db=Depends(get_db)):
    return context_for(db,account)

def valid_binding(ctx,relation_types,student_column,course_column=None):
    b=t.student_staff_binding
    now=datetime.utcnow()
    conditions=[b.c.student_id==student_column,b.c.employee_id==ctx.employee_id,
      b.c.relation_type.in_(relation_types),b.c.status=='active',b.c.valid_from<=now,
      or_(b.c.valid_to.is_(None),b.c.valid_to>now)]
    if course_column is not None:conditions += [b.c.course_scope_code.is_not(None),b.c.course_scope_code==course_column]
    return select(b.c.binding_id).where(*conditions).exists()

def scope(ctx,resource,table):
    if ctx.is_admin:
        if resource=='notification':
            return and_(table.c.channel=='in_app',table.c.event_code.like('enterprise.%'),table.c.delivery_status=='sent')
        return true()
    if resource=='course':return table.c.course_id>0 if ctx.can('score.read') else table.c.course_id<0
    if resource=='enrollment':return scope(ctx,'score',table)
    if resource=='academic':
        return valid_binding(ctx,['score_editor'] if 'academic' in ctx.roles else ['class_teacher'],table.c.student_id) if ctx.can('student.read') else table.c.id<0
    if resource=='progress':
        st=t.student_profile;c=t.customer_profile
        return select(st.c.student_id).join(c,c.c.customer_id==st.c.customer_id).where(st.c.student_id==table.c.student_id,scope(ctx,'customer',c)).exists()
    if resource in ('customer','followup'):
        c=t.customer_profile
        allowed=[]
        if 'consultant' in ctx.roles:allowed.append(c.c.employee_id==ctx.employee_id)
        if 'manager' in ctx.roles:allowed.append(c.c.department_id==ctx.department_id)
        predicate=or_(*allowed) if allowed else c.c.customer_id<0
        return predicate if resource=='customer' else select(c.c.customer_id).where(c.c.customer_id==table.c.customer_id,predicate).exists()
    if resource=='daily':return or_(table.c.employee_id==ctx.employee_id,and_('manager' in ctx.roles,table.c.department_id_at_submit==ctx.department_id))
    if resource in ('score','student'):
        col=table.c.student_id
        clauses=[]
        if 'teacher' in ctx.roles:clauses.append(valid_binding(ctx,['class_teacher'] if resource=='score' else ['class_teacher','service_advisor'],col))
        if 'academic' in ctx.roles:clauses.append(valid_binding(ctx,['score_editor'],col,table.c.course_code if resource=='score' else None))
        if resource=='student' and 'admin' in ctx.roles:clauses.append(table.c.department_id==ctx.department_id)
        return or_(*clauses) if clauses else col<0
    if resource=='ticket':
        allowed=[]
        if 'manager' in ctx.roles:allowed.append(table.c.handling_department_id==ctx.department_id)
        if 'teacher' in ctx.roles:allowed.append(and_(table.c.employee_id==ctx.employee_id,table.c.handling_department_id==ctx.department_id,valid_binding(ctx,['class_teacher','service_advisor'],table.c.student_id)))
        return or_(*allowed) if allowed else table.c.ticket_id<0
    if resource=='knowledge':
        now=datetime.utcnow()
        return and_(table.c.status=='published',table.c.index_status=='ready',table.c.effective_from<=now,
          or_(table.c.expires_at.is_(None),table.c.expires_at>now),or_(table.c.access_department_id.is_(None),table.c.access_department_id==ctx.department_id))
    if resource=='notification':
        from app.services.enterprise.enterprise_notification import visibility
        return visibility(ctx)
    if resource=='audit':return and_(table.c.action_code.like('enterprise.%'),table.c.employee_id==ctx.employee_id)
    if resource=='binding':
        ctx.require('binding.manage')
        return select(t.student_profile.c.student_id).where(t.student_profile.c.student_id==table.c.student_id,t.student_profile.c.department_id==ctx.department_id).exists()
    return table.c.department_id==ctx.department_id if resource=='employee' else table.c.department_id>0
