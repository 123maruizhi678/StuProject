"""模型提取只生成签名预览，确认仅分派到固定白名单服务。"""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import jwt
from pydantic import ValidationError
from sqlalchemy import select
from app.config import settings
from app.schemas.enterprise import enterprise as schemas
from app.clients.enterprise.enterprise_dify import EnterpriseDifyClient
from app.repositories.enterprise.enterprise_repository import digest
from app.core.enterprise.enterprise_authorization import error
from app.services.enterprise.enterprise_customer import CustomerService
from app.services.enterprise.enterprise_daily_report import DailyReportService
from app.services.enterprise.enterprise_score import ScoreService

CATALOG={
 'customer.create':('customer.create',schemas.CustomerCreate,'customer','create'),
 'customer.update':('customer.update',schemas.CustomerUpdate,'customer','update'),
 'customer.status':('customer.status',schemas.StatusUpdate,'customer','status'),
 'customer.archive':('customer.archive',schemas.Mutation,'customer','archive'),
 'customer.assign':('customer.assign',schemas.Assignment,'customer','assign'),
 'daily.create':('daily.write_own',schemas.DailyCreate,'daily','create'),
 'daily.update':('daily.write_own',schemas.DailyUpdate,'daily','update'),
 'daily.void':('daily.write_own',schemas.Mutation,'daily','void'),
 'score.create':('score.write',schemas.ScoreCreate,'score','create'),
 'score.update':('score.write',schemas.ScoreUpdate,'score','update'),
 'score.void':('score.void',schemas.Mutation,'score','void')}

class CommandService:
    def __init__(self,repo,client=None):self.repo,self.client=repo,client or EnterpriseDifyClient()
    def preview(self,text,key):
        self.repo.ctx.require('command')
        from app.models.common import operation_log
        opkey=digest([self.repo.ctx.user_id,'enterprise.command',key]);old=self.repo.db.execute(select(operation_log).where(operation_log.c.operation_key==opkey)).mappings().first()
        if old:
            if old['parameters_hash']!=digest({'text':text}):error(409,'同键不能请求不同提取内容')
            result=old['result_reference'];self._authorize_result(result);return result
        allowed={k:v for k,v in CATALOG.items() if self.repo.ctx.can(v[0])}
        field_schema={k:v[1].model_json_schema() for k,v in allowed.items()}
        targets={}
        for resource in {v[2] for v in allowed.values()}:
            for row in self.repo.page(resource,20)['items']:
                from app.repositories.enterprise.enterprise_repository import RESOURCES
                if resource=='daily' and row['employee_id']!=self.repo.ctx.employee_id and not self.repo.ctx.is_admin:continue
                pk=RESOURCES[resource][1]
                targets[(resource,row[pk])]={k:v for k,v in row.items() if k in (pk,'full_name','report_date','course_code','student_id','row_version')}
        self.repo.db.rollback()
        result=self.client.run('extract',{'text':text,'action_catalog':list(allowed),'field_schema':field_schema,'context':{'today':datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat(),'authorized_targets':[{'resource':r,'id':i,**row} for (r,i),row in targets.items()]},'contract_version':settings.ENTERPRISE_DIFY_CONTRACT_VERSION},self.repo.ctx.user_id)
        if result.get('action') not in allowed:error(400,'未识别到已授权的业务动作')
        if not isinstance(result.get('target'),dict) or not isinstance(result.get('fields'),dict):error(503,'提取输出类型不合法')
        if result.get('needs_clarification') or result.get('missing_fields'):return {'needs_clarification':True,'missing_fields':result.get('missing_fields',[]),'action':result['action'],'fields':result['fields']}
        _,_,resource,verb=allowed[result['action']]
        if verb!='create':
            chosen=targets.get((resource,result['target'].get('id')))
            if chosen is None:error(400,'目标须从本次已授权候选中选择；请使用表单定位其他记录')
            result['fields']['expected_version']=chosen['row_version']
        try:payload=allowed[result['action']][1].model_validate(result['fields'])
        except ValidationError:error(400,'提取字段不完整，请补充后重新预览')
        fields=payload.model_dump(mode='json',exclude_unset=True);target=result['target']
        if len(settings.ENTERPRISE_CONFIRM_SECRET)<32:error(503,'企业确认签名未配置')
        preview={'action':result['action'],'target':target,'fields':fields,'needs_clarification':False}
        self._authorize_result(preview)
        now=datetime.now(timezone.utc)
        token=jwt.encode({'sub':str(self.repo.ctx.user_id),'aud':'enterprise-confirm','iat':now,'exp':now+timedelta(minutes=5),'payload_hash':digest(preview),'department_id':None if self.repo.ctx.is_admin else self.repo.ctx.department_id},settings.ENTERPRISE_CONFIRM_SECRET,algorithm='HS256')
        preview['token']=token;preview['expires_in']=300
        def work():
            self._authorize_result(preview)
            if not self.repo.ctx.is_admin and self.repo.ctx.department_id!=claims_department:error(409,'所属部门已变化，请重新预览')
            return preview,None,'enterprise_command',None
        claims_department=self.repo.ctx.department_id
        return self.repo.operation('enterprise.command',key,{'text':text},work,lambda:self._authorize_result(preview))
    def _authorize_result(self,result):
        action=result.get('action')
        if action not in CATALOG:error(400,'不支持的业务动作')
        permission,model,resource,verb=CATALOG[action];self.repo.ctx.require(permission)
        if verb!='create':
            target=result.get('target',{});object_id=target.get('id')
            if not isinstance(object_id,int) or isinstance(object_id,bool) or object_id<=0:error(400,'须由授权候选选择目标ID')
            self.repo.one(resource,object_id)
            if resource=='score':
                row=self.repo.one(resource,object_id)
                ScoreService(self.repo).authorized(row['student_id'],row['course_code'])
    def confirm(self,key,payload):
        self.repo.ctx.require('command');self._authorize_result(payload)
        try:
            claims=jwt.decode(payload['token'],settings.ENTERPRISE_CONFIRM_SECRET,algorithms=['HS256'],audience='enterprise-confirm',options={'verify_exp':False})
        except jwt.InvalidTokenError:error(409,'确认凭证无效')
        preview={k:payload[k] for k in ['action','target','fields']};preview['needs_clarification']=False
        if claims.get('sub')!=str(self.repo.ctx.user_id) or claims.get('department_id')!=(None if self.repo.ctx.is_admin else self.repo.ctx.department_id) or claims.get('payload_hash')!=digest(preview):error(409,'确认凭证与账号、范围或参数不一致')
        from app.models.common import operation_log
        permission,model,resource,verb=CATALOG[payload['action']]
        validated=model.model_validate(payload['fields']).model_dump(exclude_unset=True)
        object_id=payload['target'].get('id')
        if claims.get('exp',0)<datetime.now(timezone.utc).timestamp():
            # 过期凭证只能安全查询已有成功回执，不触发新写入。
            opkey=digest([self.repo.ctx.user_id,'enterprise.'+permission,key]);receipt=self.repo.db.execute(select(operation_log).where(operation_log.c.operation_key==opkey,operation_log.c.operation_status=='succeeded')).mappings().first()
            if receipt is None:error(409,'确认已过期，请重新生成预览')
            expected={'verb':verb,'id':object_id,**validated}
            if receipt['parameters_hash']!=digest(expected):error(409,'请求参数与成功回执不一致')
            return receipt['result_reference']
        services={'customer':CustomerService,'daily':DailyReportService,'score':ScoreService}
        return services[resource](self.repo).mutate(verb,key,validated,object_id)
