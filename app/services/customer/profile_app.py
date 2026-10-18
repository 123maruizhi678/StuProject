"""仅客户画像的本机服务。认证与来源数据范围沿用现有远程后端，分析不写数据库。"""
import os
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, File, Form, Path, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.common.response import BusinessException, success
from app.schemas.customer.profile import ProfileEvaluationRequest, PROFILE_FIELDS
from app.services.customer.profile_input import MAX_FILE_BYTES, coerce_profile, preview_input
from app.services.customer.profile_rules import RULE_VERSION, catalog, evaluate_profile

REMOTE_API=os.environ.get('CUSTOMER_AUTH_BACKEND','http://192.168.5.12:8000').rstrip('/')
FRONTEND_ORIGINS=os.environ.get('CUSTOMER_FRONTEND_ORIGINS','http://192.168.5.13:5173,http://127.0.0.1:5173,http://localhost:5173').split(',')
app=FastAPI(title='客户信息研判独立服务',version=RULE_VERSION)
app.add_middleware(CORSMiddleware,allow_origins=FRONTEND_ORIGINS,allow_methods=['GET','POST'],
                   allow_headers=['Authorization','Content-Type','Accept'],allow_credentials=False)


@app.exception_handler(BusinessException)
async def business_error(request,exc):
    code=exc.code if 400<=exc.code<=599 else 400
    return JSONResponse(status_code=code,content={'code':code,'message':exc.message,'data':None})


def remote_get(path,token):
    # 仅允许本模块内部构造的鉴权和来源读取路径，不开放任意代理入口。
    try:
        with httpx.Client(timeout=12,trust_env=False,follow_redirects=False) as client:
            response=client.get(REMOTE_API+path,headers={'Authorization':token,'Accept':'application/json'})
        body=response.json()
    except (httpx.HTTPError,ValueError):
        raise BusinessException('现有后端暂时无法验证登录或读取资料，请稍后重试',code=503)
    if response.status_code!=200 or not isinstance(body,dict) or body.get('code')!=0:
        code=response.status_code if response.status_code in (401,403,404) else body.get('code',503) if isinstance(body,dict) else 503
        if code not in (401,403,404):code=503
        raise BusinessException({401:'请先在现有系统登录',403:'当前账号没有此操作权限',404:'资料来源不存在'}.get(code,'现有后端读取失败'),code=code)
    return body.get('data')


def access(request:Request):
    token=request.headers.get('Authorization','')
    if not token.startswith('Bearer ') or len(token)<8:raise BusinessException('请先在现有系统登录',code=401)
    data=remote_get('/api/v1/auth/me/access',token)
    if not isinstance(data,dict) or data.get('identity_type') not in ('admin','employee'):
        raise BusinessException('当前身份无权访问客户研判',code=403)
    return token,data


def require(permission):
    def dependency(context=Depends(access)):
        if permission not in (context[1].get('permissions') or []):raise BusinessException('当前账号没有此操作权限',code=403)
        return context
    return dependency


def remote_file(source_id,token):
    try:
        with httpx.Client(timeout=30,trust_env=False,follow_redirects=False) as client:
            with client.stream('GET',REMOTE_API+f'/api/v1/customer/source/{source_id}/file',
                               headers={'Authorization':token}) as response:
                if response.status_code!=200 or 'json' in response.headers.get('content-type',''):
                    raise BusinessException('原件暂时无法读取，请检查原件权限或重新上传资料',code=403 if response.status_code==403 else 502)
                chunks=[];size=0
                for chunk in response.iter_bytes():
                    size+=len(chunk)
                    if size>MAX_FILE_BYTES:raise BusinessException('原件超过 20 MB，请拆分后上传',code=400)
                    chunks.append(chunk)
                return b''.join(chunks)
    except httpx.HTTPError:
        raise BusinessException('原件读取失败，请稍后重试或重新上传',code=503)


@app.get('/health')
def health():return success({'service':'customer-profile','rule_version':RULE_VERSION,'database_writes':False})


@app.get('/api/v1/customer/profile/catalog')
def get_catalog(context=Depends(require('customer.rule.read'))):return success(catalog())


@app.post('/api/v1/customer/profile/analyze')
def analyze(text:Optional[str]=Form(None),file:Optional[UploadFile]=File(None),
            context=Depends(require('customer.judge.create'))):
    return success(preview_input(text=text,file_name=file.filename if file else None,
        file_bytes=file.file.read(MAX_FILE_BYTES+1) if file else None))


@app.post('/api/v1/customer/profile/evaluate')
def evaluate(body:ProfileEvaluationRequest,context=Depends(require('customer.judge.create'))):
    return success(evaluate_profile(body.facts.model_dump(exclude_none=True)))


@app.get('/api/v1/customer/source/{source_id}/profile')
def evaluate_source(source_id:int=Path(...,gt=0,le=9223372036854775807),context=Depends(require('customer.source.read'))):
    detail=remote_get(f'/api/v1/customer/source/{source_id}',context[0])
    items=[]
    if not isinstance(detail,dict):raise BusinessException('来源详情响应不完整',code=502)
    source=detail.get('source') or {}
    if source.get('file_name') and 'customer.source.file' in (context[1].get('permissions') or []):
        # 原件仍由原后端验证所有权；不依赖旧版解析器遗漏的意愿 / 能力字段。
        preview=preview_input(file_name=source['file_name'],file_bytes=remote_file(source_id,context[0]))
        return success({**preview,'source':source,'notice':'已按原件实时解析并研判；现有后端资料和解析状态未修改'})
    for index,row in enumerate(detail.get('fields') or [],1):
        facts={k:v for k,v in (row.get('profile_fields') or {}).items() if k in PROFILE_FIELDS}
        for key in ('full_name','age','education_level'):
            if row.get(key) is not None:facts[key]=row[key]
        facts,warnings=coerce_profile(facts)
        items.append({'row_number':index,'customer_info_id':row.get('id'),'facts':facts,'warnings':warnings,
                      'error':None,'evaluation':evaluate_profile(facts)})
    return success({'source':source,'items':items,'total':len(items),'persisted':False,
                    'notice':'读取现有后端有权查看的字段并实时研判；未提供的意愿、能力等信息仍需核实'})
