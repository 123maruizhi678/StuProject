"""更新明确指定的本地管理员登录名及密码；密码从进程环境读取，不写入日志。"""
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
import argparse,json,os,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sqlalchemy import select,insert
from app.config import BASE_DIR,settings
from app.database import SessionLocal
from app.models import common as t
from app.services.common.auth_service import hash_password,verify_password
from app.repositories.enterprise.enterprise_repository import digest

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--user-id',required=True,type=int)
    parser.add_argument('--expected-username',required=True)
    parser.add_argument('--username',required=True)
    parser.add_argument('--password-env',required=True)
    args=parser.parse_args()
    if settings.DB_HOST not in ('localhost','127.0.0.1','::1') or settings.DB_NAME!='education_agent':raise RuntimeError('仅允许本机education_agent')
    if not 1<=len(args.username)<=64:raise RuntimeError('用户名长度不符合要求')
    password=os.environ.get(args.password_env)
    if not password or len(password)>256:raise RuntimeError('未提供有效的新密码环境变量')
    with SessionLocal() as db:
        account=db.scalar(select(t.UserAccount).where(t.UserAccount.user_id==args.user_id).with_for_update())
        if account is None or account.identity_type!='admin':raise RuntimeError('目标平台管理员不存在')
        if account.username not in (args.expected_username,args.username):raise RuntimeError('原用户名不符合预期，停止修改')
        duplicate=db.scalar(select(t.UserAccount.user_id).where(t.UserAccount.username==args.username,t.UserAccount.user_id!=account.user_id))
        if duplicate is not None:raise RuntimeError('新用户名已被其他账户使用，停止修改')
        before={'user_id':account.user_id,'username':account.username,'identity_type':account.identity_type}
        changed=account.username!=args.username or not verify_password(password,account.password_hash)
        if changed:
            account.username=args.username;account.password_hash=hash_password(password)
            after={'user_id':account.user_id,'username':account.username,'identity_type':account.identity_type,'password_changed':True}
            request_key='local-admin-login-change-'+uuid4().hex
            db.execute(insert(t.operation_log).values(operation_key=digest([request_key,account.user_id]),service_code='local.account.credentials.change',action_code='enterprise.account.credentials_change',entity_type='user_account',entity_id=account.user_id,request_key=request_key,parameters_hash=digest({'user_id':account.user_id,'username':account.username}),before_data=before,after_data=after,result_reference=after,operation_status='succeeded',change_reason='用户明确指定更新现有平台管理员登录名和密码；保留账户主键及管理员身份。',finished_at=datetime.now(timezone.utc).replace(tzinfo=None),row_version=1))
            db.commit()
        result={'user_id':account.user_id,'username':account.username,'identity_type':account.identity_type,'changed':changed}
    folder=BASE_DIR/'.runtime';folder.mkdir(exist_ok=True)
    credential_path=folder/'enterprise-login.json'
    credentials=json.loads(credential_path.read_text(encoding='utf-8')) if credential_path.exists() else {}
    if credentials.get('username') not in (None,args.expected_username,args.username):raise RuntimeError('本地凭据文件属于其他账号，未覆盖')
    credentials.update(username=args.username,password=password,identity_type='admin',employee_id=None,purpose='平台管理员；现有企业工作台仅允许employee身份',url='http://127.0.0.1:8000/docs',login_api='http://127.0.0.1:8000/api/v1/auth/login')
    credential_path.write_text(json.dumps(credentials,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'admin-account-change.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({**result,'credentials_file':'.runtime/enterprise-login.json','password_printed':False},ensure_ascii=False))
if __name__=='__main__':main()
