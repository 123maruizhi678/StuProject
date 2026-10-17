"""企业独立Workflow适配；复用唯一公共HTTP传输。"""
import json
from fastapi.encoders import jsonable_encoder
from app.config import settings
from app.core.dify import DifyHttpClient
from app.core.enterprise.enterprise_authorization import error

KEYS={'extract':'ENTERPRISE_EXTRACT_DIFY_API_KEY','query':'ENTERPRISE_NL2SQL_DIFY_API_KEY','knowledge':'ENTERPRISE_KNOWLEDGE_DIFY_API_KEY','summary':'ENTERPRISE_SUMMARY_DIFY_API_KEY'}
class EnterpriseDifyClient:
    def __init__(self,transport=None):self.transport=transport
    def run(self,scene,inputs,user_id):
        key=getattr(settings,KEYS[scene])
        if not key or 'PLACEHOLDER' in key:error(503,'此企业工作流尚未配置有效应用Key')
        encoded={k:json.dumps(jsonable_encoder(v),ensure_ascii=False) if isinstance(v,(dict,list)) else str(v) for k,v in inputs.items()}
        try:
            client=self.transport or DifyHttpClient(settings.DIFY_API_BASE,settings.DIFY_API_TIMEOUT_SECONDS)
            response=client.post_json_sync('/workflows/run',api_key=key,payload={'inputs':encoded,'response_mode':'blocking','user':f'enterprise:{user_id}'})
            data=response.get('data',{})
            if data.get('status')!='succeeded':error(503,'企业Workflow未成功完成')
            value=data.get('outputs',{}).get('query_result' if scene=='query' else 'result')
            if isinstance(value,str):value=json.loads(value)
            if not isinstance(value,dict) or value.get('contract_version')!=settings.ENTERPRISE_DIFY_CONTRACT_VERSION:error(503,'工作流输出契约无效')
            return value
        except Exception as exc:
            from app.core.response import BusinessException
            if isinstance(exc,BusinessException):raise
            error(503,'企业模型服务不可用或输出不合法')
