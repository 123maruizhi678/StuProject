"""用无个人信息的样例核验已发布企业Workflow。"""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.clients.enterprise.enterprise_dify import EnterpriseDifyClient
def main():
    client=EnterpriseDifyClient();cases={
      'extract':{'text':'提交今天的日报，完成本地测试。','action_catalog':['daily.create'],'field_schema':{'daily.create':{'report_date':'YYYY-MM-DD','submitted_content':'string'}},'context':{'today':'2026-10-17'},'contract_version':'enterprise-v1'},
      'query':{'question':'有多少客户？','schema_context':{'customers':['customer_id','status']},'dialect':'mysql','query_constraints':{'max_rows':100},'bound_filters':{},'schema_version':'enterprise-query-v1','contract_version':'enterprise-v1'},
      'knowledge':{'question':'测试制度规定的签到时间？','mode':'qa','candidates':[{'id':1,'version':1,'title':'仅测试制度','content':'测试制度：签到时间为上午九点。'}],'contract_version':'enterprise-v1'},
      'summary':{'content':'仅联调样例：完成本地接口检查，下一步完善测试。','report_date':'2026-10-17','contract_version':'enterprise-v1'}}
    results=[]
    for scene,inputs in cases.items():
        try:
            result=client.run(scene,inputs,0);results.append({'scene':scene,'passed':True,'output_keys':sorted(result)})
        except Exception as e:results.append({'scene':scene,'passed':False,'error_type':type(e).__name__,'message':str(e)})
        print(json.dumps(results[-1],ensure_ascii=False),flush=True)
    rag={**cases['knowledge'],'mode':'rag'}
    result=client.run('knowledge',rag,0)
    assert result['mode']=='rag' and result['citations'],'RAG branch failed'
    print(json.dumps({'scene':'knowledge.rag','passed':True,'output_keys':sorted(result)}),flush=True)
    if not all(r['passed'] for r in results):sys.exit(1)
if __name__=='__main__':main()
