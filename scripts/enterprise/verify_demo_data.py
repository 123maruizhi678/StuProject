"""验证已初始化样例可由已有联调账号从企业API读取，不打印凭据。"""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import requests
from app.config import BASE_DIR

def main():
    credentials=json.loads((BASE_DIR/'.runtime/enterprise-login.json').read_text(encoding='utf-8'))
    manifest=json.loads((BASE_DIR/'.runtime/enterprise-demo-data.json').read_text(encoding='utf-8'))
    base='http://127.0.0.1:8000';session=requests.Session()
    login=session.post(base+'/api/v1/auth/login',json={k:credentials[k] for k in ('username','password')},timeout=15).json()
    assert login['code']==0,'登录失败'
    session.headers['Authorization']='Bearer '+login['data']['access_token']
    paths={'customers':('customer','customer_id'),'students':('students','student_id'),'followups':(None,'followup_id'),'daily_reports':('daily-report','daily_report_id'),'courses':('courses','course_id'),'enrollments':('student-courses','enrollment_id'),'scores':('scores','score_id'),'bindings':('student-bindings','binding_id'),'academic_events':('academic-events','id'),'application_progress':('application-progress','id'),'tickets':('tickets','ticket_id'),'knowledge':('knowledge','knowledge_id')}
    results=[]
    for group,(path,pk) in paths.items():
        if path is None:continue
        response=session.get(base+'/api/v1/enterprise/'+path,params={'limit':100},timeout=15).json()
        assert response['code']==0,group+'读取失败'
        actual={row[pk] for row in response['data']['items']};expected={row[pk] for row in manifest['records'][group]}
        assert expected<=actual,group+'样例在当前账号下不可见'
        results.append({'resource':path,'sample_rows_visible':len(expected)})
    for path in ('todos','notifications'):
        response=session.get(base+'/api/v1/enterprise/'+path,timeout=15).json()
        assert response['code']==0 and response['data']['total']>0,path+'未产生可见测试事项'
        results.append({'resource':path,'visible_total':response['data']['total']})
    result=session.post(base+'/api/v1/enterprise/onboarding/ask',json={'question':'签到'},timeout=90).json()
    assert result['code']==0 and result['data']['citations'],'样例知识检索或真实模型调用未通过'
    results.append({'resource':'onboarding/ask','citations_present':True,'mode':result['data']['mode']})
    (BASE_DIR/'.runtime/enterprise-demo-verification.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':True,'checks':results,'secrets_printed':False},ensure_ascii=False))
if __name__=='__main__':main()
