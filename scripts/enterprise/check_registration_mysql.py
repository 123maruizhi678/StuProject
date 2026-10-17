"""真实MySQL开户验证；所有新账户和档案位于外层事务，验证结束整体回滚。"""
from pathlib import Path
from uuid import uuid4
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sqlalchemy import select,insert,func,update
from sqlalchemy.orm import Session
from pydantic import TypeAdapter
from fastapi.testclient import TestClient
from app.config import BASE_DIR
from app.database import engine,get_db
from app.models import common as t
from app.schemas.common.account_registration import RegistrationRequest
from app.services.common.account_registration import AccountRegistrationService
from app.services.auth_service import authenticate,create_access_token,verify_password
from app.main import app

def main():
    tag='REGCHECK_'+uuid4().hex[:12];results=[]
    with engine.connect() as conn:
        outer=conn.begin()
        try:
            with Session(bind=conn,join_transaction_mode='create_savepoint',expire_on_commit=False) as db:
                operator=db.scalar(select(t.UserAccount).where(t.UserAccount.username=='admin',t.UserAccount.identity_type=='admin'))
                if operator is None:raise RuntimeError('未找到现有平台管理员admin')
                department_id=db.scalar(select(t.org_department.c.department_id).where(t.org_department.c.status=='active').limit(1))
                if department_id is None:raise RuntimeError('需要已有有效部门')
                service=AccountRegistrationService(db,operator);adapter=TypeAdapter(RegistrationRequest)
                cases=[{'identity_type':'employee','username':tag+'_manager','profile':{'employee_no':tag+'_E','full_name':'事务验证主管','department_id':department_id,'position_title':'部门主管'}},
                    {'identity_type':'student','username':tag+'_student','profile':{'student_no':tag+'_S','full_name':'事务验证学生','department_id':department_id}},
                    {'identity_type':'customer','username':tag+'_customer','profile':{'full_name':'事务验证客户','department_id':department_id}},
                    {'identity_type':'admin','username':tag+'_admin'}]
                for body in cases:
                    payload=adapter.validate_python(body);key=tag+'-'+body['identity_type']
                    result=service.register(payload,key)
                    assert service.register(payload,key)==result,'幂等重放不一致'
                    account=authenticate(db,body['username'],'123456')
                    assert account is not None and verify_password('123456',account.password_hash)
                    if body['identity_type']=='employee':assert result['role_codes']==['employee','manager']
                    results.append({'identity_type':body['identity_type'],'created':True,'initial_password_login':True,'idempotent_replay':True})
                # 使用真正的请求依赖和MySQL会话验证接口，但仍由外层事务保护。
                def database():yield db
                app.dependency_overrides[get_db]=database
                try:
                    with TestClient(app) as client:
                        token=create_access_token(operator)[0]
                        headers={'Authorization':'Bearer '+token,'Idempotency-Key':tag+'-http-teacher'}
                        body={'identity_type':'employee','username':tag+'_teacher','profile':{'employee_no':tag+'_T','full_name':'事务验证老师','department_id':department_id,'position_title':'班主任'}}
                        response=client.post('/api/v1/auth/register',headers=headers,json=body).json()
                        assert response['code']==0,response.get('message')
                        assert response['data']['role_codes']==['employee','teacher']
                        login=client.post('/api/v1/auth/login',json={'username':body['username'],'password':'123456'}).json()
                        assert login['code']==0
                        denied=client.post('/api/v1/auth/register',headers={'Authorization':'Bearer '+login['data']['access_token'],'Idempotency-Key':tag+'-denied'},json={'identity_type':'admin','username':tag+'_forbidden'})
                        assert denied.status_code==403
                        results.append({'http_registration':True,'employee_cannot_register':True})
                finally:app.dependency_overrides.clear()
                # MySQL唯一约束失败不会残留新档案。
                before=db.scalar(select(func.count()).select_from(t.employee))
                duplicate={**cases[0],'username':tag+'_duplicate'}
                from app.core.response import BusinessException
                try:service.register(adapter.validate_python(duplicate),tag+'-duplicate')
                except BusinessException as exc:assert exc.code==409
                else:raise AssertionError('重复工号应失败')
                assert db.scalar(select(func.count()).select_from(t.employee))==before
                assert outer.is_active,'业务提交意外结束外层事务'
        finally:
            if outer.is_active:outer.rollback()
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(t.UserAccount).where(t.UserAccount.username.like(tag+'%')))==0
        assert conn.scalar(select(func.count()).select_from(t.employee).where(t.employee.c.employee_no.like(tag+'%')))==0
    output={'passed':True,'checks':results,'test_accounts_and_profiles_rolled_back':True,'new_persistent_admin_created':False}
    (BASE_DIR/'.runtime/admin-registration-mysql-check.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output,ensure_ascii=False))
if __name__=='__main__':main()
