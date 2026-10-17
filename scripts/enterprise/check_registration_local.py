"""部署后的真实本地HTTP只读验收；不创建额外持久账户，不输出凭据。"""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import requests
from app.config import BASE_DIR

def main():
    credentials=json.loads((BASE_DIR/'.runtime/enterprise-login.json').read_text(encoding='utf-8'))
    base='http://127.0.0.1:8000';session=requests.Session()
    login=session.post(base+'/api/v1/auth/login',json={k:credentials[k] for k in ('username','password')},timeout=15).json()
    assert login['code']==0
    session.headers['Authorization']='Bearer '+login['data']['access_token']
    assert session.get(base+'/api/v1/auth/me/access',timeout=15).json()['data']['identity_type']=='admin'
    public=session.get(base+'/openapi.json',timeout=15).json()
    assert '/api/v1/auth/register' not in public['paths']
    assert not any('Registration' in name for name in public.get('components',{}).get('schemas',{}))
    private=session.get(base+'/api/v1/admin/openapi.json',timeout=15).json()
    assert '/api/v1/auth/register' in private['paths']
    options=session.get(base+'/api/v1/admin/accounts/options',timeout=15).json()
    assert options['code']==0 and options['data']['initial_password']=='123456' and options['data']['positions']['部门主管']==['employee','manager']
    accounts=session.get(base+'/api/v1/admin/accounts',timeout=15).json()
    assert accounts['code']==0 and all('password_hash' not in row for row in accounts['data']['items'])
    anonymous=requests.get(base+'/api/v1/admin/openapi.json',timeout=15)
    assert anonymous.status_code==401
    assert requests.post(base+'/api/v1/auth/register',json={'identity_type':'admin','username':'not-created'},timeout=15).status_code==401
    for path in ['/admin/accounts','/static/css/admin/accounts.css','/static/js/admin/accounts.js']:
        assert session.get(base+path,timeout=15).status_code==200
    report={'login_admin':True,'public_schema_hides_registration':True,'private_schema_available':True,'position_mapping':True,'default_password_policy':True,'account_list_excludes_passwords':True,'anonymous_denied':True,'admin_assets_available':True,'new_persistent_accounts_created':False}
    (BASE_DIR/'.runtime/admin-registration-local-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
