"""按明确授权将enterprise.local改为平台管理员；保留口令和原员工事实。"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sqlalchemy import select,insert
from app.config import BASE_DIR,settings
from app.database import SessionLocal
from app.models import common as t
from app.repositories.enterprise.enterprise_repository import digest

def identity(account):
    return {name:getattr(account,name) for name in ('user_id','username','identity_type','employee_id','customer_id','student_id')}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    if settings.DB_HOST not in ('localhost','127.0.0.1','::1') or settings.DB_NAME!='education_agent':
        raise RuntimeError('仅限本机education_agent')
    folder=BASE_DIR/'.runtime';folder.mkdir(exist_ok=True)
    with SessionLocal() as db:
        account=db.scalar(select(t.UserAccount).where(t.UserAccount.username=='enterprise.local').with_for_update())
        if account is None:raise RuntimeError('目标账号不存在')
        before=identity(account)
        if not args.apply:
            print(json.dumps({'current':before,'target_identity':'admin','password_will_change':False}));return
        if account.identity_type not in ('employee','admin'):raise RuntimeError('账户原身份与预期不一致')
        changed=account.identity_type!='admin'
        if changed:
            backup=folder/'enterprise-local-identity-before.json'
            if not backup.exists():backup.write_text(json.dumps(before,ensure_ascii=False,indent=2),encoding='utf-8')
            original_hash=account.password_hash
            account.identity_type='admin';account.employee_id=None;account.customer_id=None;account.student_id=None
            db.flush()
            after=identity(account)
            if account.password_hash!=original_hash:raise RuntimeError('口令应保持不变')
            request_key='local-enterprise-account-promote-admin-v1'
            db.execute(insert(t.operation_log).values(operation_key=digest([request_key,account.user_id]),service_code='local.account.identity.change',action_code='enterprise.account.promote_admin',entity_type='user_account',entity_id=account.user_id,request_key=request_key,parameters_hash=digest({'username':account.username,'target_identity':'admin'}),before_data=before,after_data=after,result_reference=after,operation_status='succeeded',change_reason='用户明确要求将enterprise.local由员工身份改为平台管理员；保留用户名及密码，保留原员工档案。',finished_at=datetime.now(timezone.utc).replace(tzinfo=None),row_version=1))
            db.commit()
        result={'account':identity(account),'changed':changed,'password_changed':False,'employee_profile_deleted':False}
    credential_path=folder/'enterprise-login.json'
    if credential_path.exists():
        credentials=json.loads(credential_path.read_text(encoding='utf-8'))
        if credentials.get('username')=='enterprise.local':
            credentials.update(identity_type='admin',employee_id=None,purpose='平台管理员；现有企业工作台仅允许employee身份',url='http://127.0.0.1:8000/docs',login_api='http://127.0.0.1:8000/api/v1/auth/login')
            credential_path.write_text(json.dumps(credentials,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'enterprise-local-admin-change.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
