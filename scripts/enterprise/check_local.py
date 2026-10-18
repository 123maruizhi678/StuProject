"""真实本机只读验收；从忽略文件读取联调凭据，不输出口令或Token。"""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import requests
from app.config import BASE_DIR

def main():
    base='http://127.0.0.1:8000';credentials=json.loads((BASE_DIR/'.runtime/enterprise-login.json').read_text(encoding='utf-8'))
    session=requests.Session()
    login=session.post(base+'/api/v1/auth/login',json={k:credentials[k] for k in ('username','password')},timeout=15).json()
    assert login['code']==0,'login failed'
    session.headers['Authorization']='Bearer '+login['data']['access_token'];results=[]
    for path in ['me/permissions','customer','daily-report','students','scores','tickets','knowledge','notifications','employees','organization','student-bindings','operation-logs','todos','courses','student-courses','academic-events','application-progress']:
        data=session.get(base+'/api/v1/enterprise/'+path,timeout=15).json()
        assert data['code']==0,f'{path}: code={data["code"]}'
        results.append({'path':path,'passed':True})
    response=session.post(base+'/api/v1/enterprise/nl2sql',json={'question':'统计我有权限查看的客户总数','filters':{}},timeout=120).json()
    assert response['code']==0,f'NL2SQL: code={response["code"]}'
    results.append({'path':'nl2sql','passed':True,'returned_rows':response['data']['row_count']})
    key='local-check-preview-20261017'
    payload={'text':'新增客户，客户姓名为仅联调预览。只预览，不确认写入。'}
    preview=session.post(base+'/api/v1/enterprise/command',headers={'Idempotency-Key':key},json=payload,timeout=120).json()
    assert preview['code']==0 and preview['data'].get('token') and preview['data']['action']=='customer.create',f'preview: code={preview["code"]}'
    replay=session.post(base+'/api/v1/enterprise/command',headers={'Idempotency-Key':key},json=payload,timeout=15).json()
    assert replay['data']==preview['data'],'preview receipt replay failed'
    results.append({'path':'command','passed':True,'preview_only':True,'replay':True})
    audio=BASE_DIR/'.runtime/asr-sample.wav'
    if audio.exists():
        with audio.open('rb') as stream:voice=session.post(base+'/api/v1/enterprise/voice/transcribe',files={'file':('asr-sample.wav',stream,'audio/wav')},timeout=120).json()
        assert voice['code']==0 and voice['data']['text'] and voice['data']['requires_user_review'] and not voice['data']['business_written'],f'voice: code={voice["code"]}'
        results.append({'path':'voice/transcribe','passed':True,'local_model':True})
    assert session.get(base+'/enterprise',timeout=10).status_code==200
    assert session.get(base+'/static/js/enterprise/enterprise.js',timeout=10).status_code==200
    output={'login':True,'http_checks':results,'frontend_assets':True,'secrets_printed':False}
    (BASE_DIR/'.runtime/enterprise-live-check.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(output))
if __name__=='__main__':main()
