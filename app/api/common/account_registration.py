"""管理员专用开户与查询；所有路由从公共OpenAPI隐藏。"""
from fastapi import APIRouter,Depends,Header,Query
from fastapi.encoders import jsonable_encoder
from app.database import get_db
from app.core.common.admin_authorization import require_platform_admin
from app.core.response import success
from app.schemas.common.account_registration import RegistrationRequest
from app.services.common.account_registration import AccountRegistrationService,registration_options,list_registered_accounts

router=APIRouter(tags=['管理员账户管理'],include_in_schema=False)

@router.post('/auth/register',name='admin_register_account')
def register_account(payload:RegistrationRequest,db=Depends(get_db),operator=Depends(require_platform_admin),key:str=Header(alias='Idempotency-Key')):
    return success(jsonable_encoder(AccountRegistrationService(db,operator).register(payload,key)))

@router.get('/admin/accounts/options',name='admin_account_options')
def options(db=Depends(get_db),operator=Depends(require_platform_admin)):
    return success(jsonable_encoder(registration_options(db)))

@router.get('/admin/accounts',name='admin_account_list')
def accounts(limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0),db=Depends(get_db),operator=Depends(require_platform_admin)):
    return success(jsonable_encoder(list_registered_accounts(db,limit,offset)))
