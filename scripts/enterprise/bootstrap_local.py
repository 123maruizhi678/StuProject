"""本机首次开通配置员工账号；随机口令只写入忽略的本地文件。"""
from pathlib import Path
import sys,secrets,json
from datetime import date,datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sqlalchemy import select,insert,update
from app.database import SessionLocal
from app.models import common as t
from app.services.auth_service import hash_password
from app.config import BASE_DIR

def main():
    folder=BASE_DIR/'.runtime';folder.mkdir(exist_ok=True)
    with SessionLocal() as db:
        account=db.scalar(select(t.UserAccount).where(t.UserAccount.username=='enterprise.local'))
        if account:
            if '--rotate-password' in sys.argv:
                password=secrets.token_urlsafe(24)
                account.password_hash=hash_password(password)
                (folder/'enterprise-login.json').write_text(json.dumps({'username':'enterprise.local','password':password,'purpose':'本地联调','url':'http://127.0.0.1:8000/enterprise'},ensure_ascii=False,indent=2),encoding='utf-8')
                db.commit()
            print(json.dumps({'account':'enterprise.local','created':False,'credentials_file':'.runtime/enterprise-login.json'}));return
        dept=db.execute(insert(t.org_department).values(department_code='ENTERPRISE_LOCAL',department_name='本地企业联调组织',status='active',row_version=1)).inserted_primary_key[0]
        employee=db.execute(insert(t.employee).values(employee_no='ENTERPRISE_LOCAL_ADMIN',full_name='本地配置员工',department_id=dept,login_provider='local',login_subject='enterprise.local',role_codes=['employee','admin','manager','consultant','academic','teacher'],status='active',joined_date=date.today(),row_version=1)).inserted_primary_key[0]
        password=secrets.token_urlsafe(18)
        account=t.UserAccount(username='enterprise.local',password_hash=hash_password(password),identity_type='employee',employee_id=employee)
        db.add(account);db.flush()
        credentials={'username':'enterprise.local','password':password,'purpose':'本地联调，不是平台管理员或正式员工身份','url':'http://127.0.0.1:8000/enterprise'}
        # 先成功保存口令再提交账号；保存失败时数据库回滚，避免创建无法取回口令的账号。
        (folder/'enterprise-login.json').write_text(json.dumps(credentials,ensure_ascii=False,indent=2),encoding='utf-8')
        db.execute(update(t.org_department).where(t.org_department.c.department_id==dept).values(employee_id=employee));db.commit()
        print(json.dumps({'account':'enterprise.local','created':True,'credentials_file':'.runtime/enterprise-login.json','password_printed':False}))
if __name__=='__main__':main()
