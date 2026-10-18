"""客户及跟进固定业务服务，不允许模型直接写库。"""
from datetime import datetime,timezone
from sqlalchemy import select,insert,update
from app.config import settings
from app.models import common as t
from app.models.enterprise import customer_followup
from app.core.enterprise.enterprise_authorization import error
from app.repositories.enterprise.enterprise_repository import EnterpriseRepository,public,RESOURCES,digest
from app.core.common.phone_protection import phone_fields
from app.services.common.customer_number import create_customer_profile

def utc(value):
    if value is None:return None
    if value.tzinfo is None:error(400,'时间必须包含时区偏移')
    return value.astimezone(timezone.utc).replace(tzinfo=None)
class CustomerService:
    def __init__(self,repo):self.repo=repo
    def mutate(self,verb,key,params,customer_id=None):
        action={'create':'customer.create','update':'customer.update','status':'customer.status','archive':'customer.archive','assign':'customer.assign'}[verb]
        self.repo.ctx.require(action)
        def work():
            ctx=self.repo.ctx;db=self.repo.db;now=datetime.utcnow();values=dict(params);expected=values.pop('expected_version',None);values.pop('reason',None)
            if verb=='create':
                owner=values.pop('employee_id',None) or ctx.employee_id
                if owner!=ctx.employee_id and 'manager' not in ctx.roles and not ctx.is_admin:error(403,'不能为其他顾问建档')
                owner_row=self.owner(owner)
                if 'phone' in values:values.update(phone_fields(values.pop('phone')))
                values.update(employee_id=owner,department_id=owner_row['department_id'] if ctx.is_admin else ctx.department_id,source_channel='local',status='new',authority_source='local',status_changed_at=now,is_archived=False,row_version=1,created_at=now,updated_at=now)
                result=create_customer_profile(db,values);cid=result['customer_id']
                return public(result),None,'customer_profile',cid
            row=self.repo.one('customer',customer_id,lock=True)
            if row['is_archived']:error(409,'已归档客户不可修改')
            if row['authority_source']!='local':error(409,'外部权威档案不能冒充本地修改')
            if verb=='update':
                if 'phone' in values:values.update(phone_fields(values.pop('phone')))
            elif verb=='status':
                if values['status']=='lost' and not values.get('lost_reason'):error(400,'流失原因必填')
                values['status_changed_at']=now
            elif verb=='archive':
                if not params.get('reason'):error(400,'归档原因必填')
                values={'is_archived':True}
            elif verb=='assign':
                target=self.owner(values['employee_id'])
                if ctx.is_admin:values['department_id']=target['department_id']
            result=self.repo.version_update('customer',row,expected,values)
            return public(result),row,'customer_profile',customer_id
        return self.repo.operation('enterprise.'+action,key,{'verb':verb,'id':customer_id,**params},work,lambda:self.repo.one('customer',customer_id) if customer_id else self.repo.ctx.require(action))
    def owner(self,employee_id):
        row=self.repo.db.execute(select(t.employee).where(t.employee.c.employee_id==employee_id)).mappings().first()
        if not row or row['status']!='active' or (not self.repo.ctx.is_admin and row['department_id']!=self.repo.ctx.department_id) or not ({'consultant','admin'}&set(row['role_codes'])):error(400,'负责人须为有效顾问或管理员，普通员工须限定本部门')
        return row
    def followup(self,customer_id,key,params,followup_id=None):
        self.repo.ctx.require('customer.followup')
        def work():
            ctx=self.repo.ctx;db=self.repo.db;now=datetime.utcnow()
            customer=self.repo.one('customer',customer_id,lock=True)
            generation=db.scalar(select(t.operation_log.c.operation_log_id).where(t.operation_log.c.operation_key==digest([ctx.user_id,'enterprise.customer.followup',key])))
            if customer['is_archived'] or customer['authority_source']!='local':error(409,'该客户不可写入跟进')
            if followup_id is None:
                values={**params,'customer_id':customer_id,'employee_id':ctx.employee_id,'row_version':1,'created_at':now,'updated_at':now}
                values['followup_at']=utc(values['followup_at']);values['next_followup_at']=utc(values.get('next_followup_at'))
                for field in ('followup_at','next_followup_at'):
                    if values[field]:values[field]=values[field].replace(microsecond=values[field].microsecond//1000*1000)
                if values['followup_at']>now:error(400,'跟进发生时间不能在未来')
                values['followup_status']='pending' if values['next_followup_at'] else 'none'
                values.update(schedule_operation_id=generation,schedule_base_at=values['next_followup_at'])
                fid=db.execute(insert(customer_followup).values(**values)).inserted_primary_key[0]
                db.execute(update(t.customer_profile).where(t.customer_profile.c.customer_id==customer_id).values(last_followup_at=values['followup_at'],row_version=customer['row_version']+1,updated_at=now))
                return public({**values,'followup_id':fid}),None,'customer_followup',fid
            row=self.repo.one('followup',followup_id,lock=True)
            if row['customer_id']!=customer_id:error(404,'跟进记录不存在')
            values={'followup_status':params['followup_status']}
            if params.get('next_followup_at'):values['next_followup_at']=utc(params['next_followup_at'])
            if values.get('next_followup_at'):values['next_followup_at']=values['next_followup_at'].replace(microsecond=values['next_followup_at'].microsecond//1000*1000)
            if values['followup_status']=='pending' and not values.get('next_followup_at',row['next_followup_at']):error(400,'须提供计划时间')
            values.update(schedule_operation_id=generation,schedule_base_at=values.get('next_followup_at',row['next_followup_at']))
            result=self.repo.version_update('followup',row,params.get('expected_version'),values)
            return public(result),row,'customer_followup',followup_id
        return self.repo.operation('enterprise.customer.followup',key,{'customer_id':customer_id,'followup_id':followup_id,**params},work,lambda:self.repo.one('customer',customer_id))
