"""参数化查询、对象版本更新和可重放审计；不自动提交读操作。"""
from datetime import datetime,date
from decimal import Decimal
import hashlib,json
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select,insert,update,func
from sqlalchemy.exc import IntegrityError
from app.core.enterprise.enterprise_authorization import error,scope,context_for
from app.models import common as common
from app.models import enterprise as own

RESOURCES={
 'course':(own.enterprise_course,'course_id'),'enrollment':(own.enterprise_student_course,'enrollment_id'),
 'academic':(common.student_academic_event,'id'),'progress':(common.student_application_progress,'id'),
 'customer':(common.customer_profile,'customer_id'), 'followup':(own.customer_followup,'followup_id'),
 'daily':(own.employee_daily_report,'daily_report_id'),'score':(common.student_score,'score_id'),
 'student':(common.student_profile,'student_id'),'ticket':(common.service_ticket,'ticket_id'),
 'knowledge':(own.knowledge_entry,'knowledge_id'),'notification':(common.business_notification,'notification_id'),
 'employee':(common.employee,'employee_id'),'department':(common.org_department,'department_id'),
 'binding':(common.student_staff_binding,'binding_id'),'audit':(common.operation_log,'operation_log_id')}
HIDDEN={'password_hash','phone_ciphertext','phone_lookup_token','login_subject','login_provider','external_customer_id','before_data','after_data','parameters_hash','request_key','request_hash','result_reference'}
READ_FIELDS={'student':{'student_id','student_no','full_name','department_id','status'},'employee':{'employee_id','employee_no','full_name','department_id','position_title','work_email','status','row_version'}}

def digest(value):return hashlib.sha256(json.dumps(jsonable_encoder(value),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def public(row):return {k:v for k,v in dict(row).items() if k not in HIDDEN and not isinstance(v,bytes)}
def project(resource,row):return {k:v for k,v in public(row).items() if resource not in READ_FIELDS or k in READ_FIELDS[resource]}
def snapshot(row):return jsonable_encoder(public(row)) if row else None

class EnterpriseRepository:
    def __init__(self,db,ctx):self.db,self.ctx=db,ctx
    def one(self,resource,object_id,*,lock=False,extra=None):
        table,pk=RESOURCES[resource]
        q=select(table).where(table.c[pk]==object_id,scope(self.ctx,resource,table))
        if extra is not None:q=q.where(extra)
        if lock:q=q.with_for_update()
        row=self.db.execute(q).mappings().first()
        if not row:error(404,'对象不存在或不可见')
        return dict(row)
    def page(self,resource,limit=20,offset=0,*,extra=None):
        if not 1<=limit<=100 or offset<0:error(400,'分页参数无效')
        table,pk=RESOURCES[resource];where=scope(self.ctx,resource,table)
        if extra is not None:where=where&extra
        total=self.db.scalar(select(func.count()).select_from(table).where(where))
        rows=self.db.execute(select(table).where(where).order_by(table.c[pk].desc()).limit(limit).offset(offset)).mappings()
        return {'items':[project(resource,r) for r in rows],'total':total,'limit':limit,'offset':offset}
    def version_update(self,resource,row,expected,values):
        table,pk=RESOURCES[resource]
        if any(k not in table.c or (v is None and not table.c[k].nullable) for k,v in values.items()):error(400,'字段不存在或必填值为空')
        if expected is None or row['row_version']!=expected:error(409,'对象版本已改变')
        result=self.db.execute(update(table).where(table.c[pk]==row[pk],table.c.row_version==expected).values(**values,row_version=expected+1,updated_at=datetime.utcnow()))
        if result.rowcount!=1:error(409,'并发更新冲突')
        return {**row,**values,'row_version':expected+1}
    def operation(self,action,key,parameters,execute,recheck=None):
        if not key or not 8<=len(key)<=128 or any(ord(c)<33 or ord(c)>126 for c in key):error(400,'须提供8至128位可见ASCII幂等键')
        opkey=digest([self.ctx.user_id,action,key]);paramhash=digest(parameters);t=common.operation_log
        try:
            # 同员工的全部企业写请求先锁员工，保证同一操作者的请求占位与幂等顺序。
            account=self.db.get(common.UserAccount,self.ctx.user_id,populate_existing=True)
            if account is None:error(401,'账号已失效')
            # 最高管理员无账号employee_id外键；专用操作档案仅承载非空业务外键。
            if account.identity_type=='admin':
                self.db.execute(select(common.UserAccount.user_id).where(common.UserAccount.user_id==account.user_id).with_for_update()).first()
                from app.core.common.system_admin import ensure_admin_actor
                actor=ensure_admin_actor(self.db,account)
                actor_id=actor['employee_id']
            else:actor_id=account.employee_id
            # 统一锁前缀：部门 → 员工ID升序。目标员工也提前纳入，禁止转派时反向锁。
            dept=self.db.scalar(select(common.employee.c.department_id).where(common.employee.c.employee_id==actor_id))
            self.db.execute(select(common.org_department.c.department_id).where(common.org_department.c.department_id==dept).with_for_update()).first()
            ids=sorted({actor_id}|({parameters['employee_id']} if isinstance(parameters.get('employee_id'),int) else set()))
            self.db.execute(select(common.employee.c.employee_id).where(common.employee.c.employee_id.in_(ids)).order_by(common.employee.c.employee_id).with_for_update()).all()
            self.ctx=context_for(self.db,account,lock=True)
            self.ctx.require(action)
            existing=self.db.execute(select(t).where(t.c.operation_key==opkey)).mappings().first()
            if existing:
                if existing['parameters_hash']!=paramhash:error(409,'同一幂等键不能提交不同参数')
                if recheck:recheck()
                if existing['operation_status']!='succeeded':error(409,'操作仍在处理中')
                self.db.rollback();return existing['result_reference']
            now=datetime.utcnow()
            self.db.execute(insert(t).values(operation_key=opkey,employee_id=self.ctx.employee_id,action_code=action,entity_type='enterprise_operation',request_key=key,parameters_hash=paramhash,operation_status='processing',row_version=1,created_at=now,updated_at=now))
            result,before,entity_type,entity_id=execute()
            receipt=jsonable_encoder(result)
            self.db.execute(update(t).where(t.c.operation_key==opkey).values(operation_status='succeeded',entity_type=entity_type,entity_id=entity_id,before_data={'operator_user_id':self.ctx.user_id,'identity_type':self.ctx.identity_type,'record':snapshot(before)},after_data=receipt,result_reference=receipt,change_reason=parameters.get('reason'),finished_at=datetime.utcnow()))
            self.db.commit();return receipt
        except IntegrityError:
            self.db.rollback();error(409,'唯一约束或并发冲突，请使用原请求键核实结果')
        except Exception:self.db.rollback();raise
