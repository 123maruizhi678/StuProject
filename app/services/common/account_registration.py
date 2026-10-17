"""平台管理员开户固定服务：档案、职位角色、账号和脱敏审计同事务提交。"""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from uuid import uuid4
from sqlalchemy import select,insert,update,func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models import common as t
from app.core.common.response import BusinessException
from app.core.common.authorization import permissions_for
from app.core.common.position_roles import roles_for_position,position_catalog
from app.core.common.phone_protection import phone_fields
from app.services.common.auth_service import hash_password
from app.core.common.system_admin import is_system_admin,ensure_admin_actor
from app.repositories.enterprise.enterprise_repository import digest

DEFAULT_REGISTRATION_PASSWORD='123456'
ACTION='auth.account.register'
PROFILE_TABLES={'employee':(t.employee,'employee_id'),'student':(t.student_profile,'student_id'),'customer':(t.customer_profile,'customer_id')}

def invalid(message,code=400):raise BusinessException(message,code)

def registration_options(db):
    departments=db.execute(select(t.org_department.c.department_id,t.org_department.c.department_name).where(t.org_department.c.status=='active').order_by(t.org_department.c.department_id)).mappings()
    return {'identity_types':['admin','employee','student','customer'],'positions':dict(position_catalog()),'departments':[dict(d) for d in departments],'initial_password':DEFAULT_REGISTRATION_PASSWORD,'today_beijing':datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()}

class AccountRegistrationService:
    def __init__(self,db,operator):self.db,self.operator_id=db,operator.user_id

    def _department(self,department_id):
        row=self.db.execute(select(t.org_department).where(t.org_department.c.department_id==department_id).with_for_update()).mappings().first()
        if not row or row['status']!='active':invalid('所属部门不存在或已停用',403)

    def _profile(self,payload):
        identity=payload.identity_type
        if identity=='admin':return None,None,[],None
        table,pk=PROFILE_TABLES[identity]
        object_id=getattr(payload,pk)
        before=None
        now=datetime.now(timezone.utc).replace(tzinfo=None)
        if object_id is not None:
            preliminary=self.db.execute(select(table.c.department_id).where(table.c[pk]==object_id)).scalar_one_or_none()
            if preliminary is None:invalid('关联档案不存在',404)
            self._department(preliminary)
            row=self.db.execute(select(table).where(table.c[pk]==object_id).with_for_update()).mappings().first()
            if not row:invalid('关联档案不存在',404)
            before=dict(row)
            if row['department_id']!=preliminary:invalid('档案所属部门已变化，请重试',409)
            if self.db.scalar(select(t.UserAccount.user_id).where(getattr(t.UserAccount,pk)==object_id)):invalid('该档案已经绑定登录账户',409)
            if identity in ('student','customer') and row['is_archived']:invalid('已归档档案不能注册',403)
            if identity in ('student','employee') and row['status']!='active':invalid('档案状态无效，不能注册',403)
            roles=roles_for_position(row['position_title']) if identity=='employee' else []
            values={}
            if identity=='employee' and list(row['role_codes'])!=roles:values['role_codes']=roles
            if identity=='student' and row['login_provider'] is None and row['login_subject'] is None:
                values.update(login_provider='local',login_subject=payload.username)
            if values:
                self.db.execute(update(table).where(table.c[pk]==object_id,table.c.row_version==row['row_version']).values(**values,row_version=row['row_version']+1,updated_at=now))
            return object_id,row['department_id'],roles,{'profile_id':object_id,'role_codes':row.get('role_codes')}

        values=payload.profile.model_dump(exclude_none=True)
        self._department(values['department_id'])
        roles=[]
        if identity=='employee':
            roles=roles_for_position(values['position_title'])
            values.setdefault('joined_date',datetime.now(ZoneInfo('Asia/Shanghai')).date())
            values.update(login_provider='local',login_subject=payload.username,role_codes=roles,status='active')
        elif identity=='student':
            if values.get('customer_id'):
                customer=self.db.execute(select(t.customer_profile).where(t.customer_profile.c.customer_id==values['customer_id']).with_for_update()).mappings().first()
                if not customer or customer['is_archived'] or customer['department_id']!=values['department_id']:invalid('学生关联客户必须有效且属于同一部门')
            values.update(status='active',is_archived=False,login_provider='local',login_subject=payload.username)
        else:
            if values.get('employee_id'):
                employee=self.db.execute(select(t.employee).where(t.employee.c.employee_id==values['employee_id']).with_for_update()).mappings().first()
                if not employee or employee['status']!='active' or employee['department_id']!=values['department_id'] or not ({'consultant','admin'}&set(employee['role_codes'])):invalid('客户负责人必须为同部门有效顾问或管理员')
            if 'phone' in values:values.update(phone_fields(values.pop('phone')))
            values.update(customer_no='CUS'+uuid4().hex[:20],status='new',source_channel='admin_registration',authority_source='local',is_archived=False,status_changed_at=now)
        values.update(row_version=1,created_at=now,updated_at=now)
        object_id=self.db.execute(insert(table).values(**values)).inserted_primary_key[0]
        return object_id,values['department_id'],roles,None

    def register(self,payload,key):
        if not key or not 8<=len(key)<=128 or any(ord(c)<33 or ord(c)>126 for c in key):invalid('Idempotency-Key须为8至128位可见ASCII字符')
        parameters=payload.model_dump(mode='json',exclude_none=True)
        opkey=digest([self.operator_id,ACTION,key]);parameter_hash=digest(parameters)
        try:
            # 持有真实管理员账户行锁，角色撤销与开户不会交错生效。
            operator=self.db.scalar(select(t.UserAccount).where(t.UserAccount.user_id==self.operator_id).with_for_update().execution_options(populate_existing=True))
            if operator is None:raise HTTPException(401,'账户已失效')
            if not is_system_admin(self.db,operator,lock=True):raise HTTPException(403,'仅平台管理员可管理注册账户')
            existing=self.db.execute(select(t.operation_log).where(t.operation_log.c.operation_key==opkey)).mappings().first()
            if existing:
                if existing['parameters_hash']!=parameter_hash:invalid('相同幂等键不能提交不同注册内容',409)
                if existing['operation_status']!='succeeded':invalid('注册仍在处理中',409)
                result=existing['result_reference'];self.db.rollback();return result
            if self.db.scalar(select(t.UserAccount.user_id).where(t.UserAccount.username==payload.username)):invalid('用户名已存在',409)
            profile_id,department_id,roles,before=self._profile(payload)
            account=t.UserAccount(username=payload.username,password_hash=hash_password(DEFAULT_REGISTRATION_PASSWORD),identity_type=payload.identity_type)
            if payload.identity_type!='admin':setattr(account,PROFILE_TABLES[payload.identity_type][1],profile_id)
            self.db.add(account);self.db.flush()
            if account.identity_type=='admin':ensure_admin_actor(self.db,account)
            result={'user_id':account.user_id,'username':account.username,'identity_type':account.identity_type,'employee_id':account.employee_id,'student_id':account.student_id,'customer_id':account.customer_id,'department_id':department_id,'role_codes':roles,'permissions':sorted(permissions_for(account.identity_type))}
            if account.identity_type=='employee':
                from app.core.enterprise.enterprise_authorization import EmployeeContext
                result['enterprise_permissions']=EmployeeContext(account.user_id,account.employee_id,department_id,frozenset(roles)).permissions()
            now=datetime.now(timezone.utc).replace(tzinfo=None)
            self.db.execute(insert(t.operation_log).values(operation_key=opkey,service_code='auth.account.registration',action_code=ACTION,entity_type='user_account',entity_id=account.user_id,request_key=key,parameters_hash=parameter_hash,before_data={'operator_user_id':operator.user_id,'profile_before':before},after_data={'operator_user_id':operator.user_id,'created_account':result},result_reference=result,operation_status='succeeded',change_reason='平台管理员统一开户，密码采用系统固定初始值的Argon2哈希；审计不记录密码。',finished_at=now,row_version=1))
            self.db.commit()
            return result
        except IntegrityError:
            self.db.rollback();invalid('用户名、工号、学号或档案绑定发生重复冲突，请检查后重试',409)
        except Exception:
            self.db.rollback();raise

def list_registered_accounts(db,limit=20,offset=0):
    columns=[t.UserAccount.user_id,t.UserAccount.username,t.UserAccount.identity_type,t.UserAccount.employee_id,t.UserAccount.student_id,t.UserAccount.customer_id,t.UserAccount.created_at]
    rows=db.execute(select(*columns).order_by(t.UserAccount.user_id.desc()).limit(limit).offset(offset)).mappings()
    return {'items':[dict(row) for row in rows],'total':db.scalar(select(func.count()).select_from(t.UserAccount)),'limit':limit,'offset':offset}
