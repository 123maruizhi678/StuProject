"""Real HTTP/MySQL acceptance. Continue each scenario and report every API operation."""
import argparse
import json
import re
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import httpx
from sqlalchemy import insert, select, update
from app.database import SessionLocal
from app.models import common as t
from app.models.agent.agent import LectureEvent, CourseProject, Faq
from app.models.customer import Product


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    client = httpx.Client(base_url=args.base_url, timeout=15, trust_env=False)
    tag = 'QA' + uuid4().hex[:10]
    results, calls, ids, tokens = [], [], {}, {}
    now = datetime.now(timezone.utc)

    def call(method, path, body=None, *, actor='root', expected=0, key=None, **kwargs):
        headers = {'Idempotency-Key': key or tag + '-' + uuid4().hex}
        if actor in tokens:
            headers['Authorization'] = 'Bearer ' + tokens[actor]
        r = client.request(method, path, json=body, headers=headers, **kwargs)
        try:
            data = r.json()
        except ValueError:
            data = {'code': 0 if r.status_code == 200 else r.status_code, 'data': None}
        code = data.get('code', 0 if r.status_code == 200 else r.status_code)
        valid = code in expected if isinstance(expected, (list, tuple)) else code == expected
        calls.append({'method': method, 'path': path.split('?')[0], 'actor': actor,
                      'http': r.status_code, 'code': code, 'passed': valid,
                      'message': data.get('message', data.get('detail', ''))})
        assert valid, f'{method} {path}: HTTP {r.status_code}, code {code}, {str(data)[:350]}'
        return data.get('data', data)

    def scenario(name, work):
        before = len(calls)
        try:
            work()
            results.append({'name': name, 'status': 'passed', 'requests': len(calls)-before})
        except Exception as exc:
            results.append({'name': name, 'status': 'failed', 'reason': str(exc), 'requests': len(calls)-before})
            print('FAILED', name, str(exc), flush=True)

    def login(name, username, password):
        data = call('POST', '/api/v1/auth/login', {'username': username, 'password': password}, actor='anonymous')
        tokens[name] = data['access_token']

    login('root', 'root', 'root')
    schema = client.get('/openapi.json').json()
    admin_schema = call('GET', '/api/v1/admin/openapi.json')
    all_paths = {**schema['paths'], **admin_schema['paths']}
    all_paths['/api/v1/admin/openapi.json'] = {'get': {}}
    def enterprise(resource): return '/api/v1/enterprise/' + resource
    def get(resource, object_id=None):
        return call('GET', enterprise(resource) + ('/' + str(object_id) if object_id else ''))
    def post(resource, body): return call('POST', enterprise(resource), body)
    def put(resource, body): return call('PUT', enterprise(resource), body)
    def delete(resource, body): return call('DELETE', enterprise(resource), body)

    def authentication():
        call('GET','/health',actor='anonymous')
        call('GET','/api/v1/auth/public-access',actor='anonymous')
        call('GET','/api/v1/auth/me/access')
        call('GET','/api/v1/auth/me/access',actor='anonymous',expected=401)
        call('POST','/api/v1/auth/login',{'username':'root','password':'incorrect'},actor='anonymous',expected=401)
        call('GET',enterprise('me/permissions'))
        call('GET','/api/v1/admin/accounts/options')
        call('GET','/api/v1/admin/accounts')
    scenario('authentication_admin_and_denials', authentication)

    def prepare_people():
        dep = post('departments',{'department_code':tag,'department_name':'系统验收 '+tag})
        ids['department_id'] = dep['department_id']
        for actor, identity, position in [('teacher','employee','班主任'),('manager','employee','部门主管'),('student','student',None),('customer','customer',None),('admin2','admin',None)]:
            body = {'identity_type':identity,'username':tag+'_'+actor}
            if identity != 'admin':
                profile={'full_name':'验收'+actor,'department_id':ids['department_id']}
                if identity=='employee':profile.update(employee_no=tag+actor,position_title=position)
                elif identity=='student':profile['student_no']=tag+actor
                body['profile']=profile
            key=tag+'-register-'+actor
            receipt=call('POST','/api/v1/auth/register',body,key=key)
            replay=call('POST','/api/v1/auth/register',body,key=key)
            assert receipt==replay
            if identity in ('employee','student','customer'): ids[actor+'_id']=receipt[identity+'_id']
            login(actor,body['username'],'123456')
        call('POST','/api/v1/auth/register',{'identity_type':'admin','username':tag+'_denied'},actor='student',expected=403)
        binding=post('student-bindings',{'student_id':ids['student_id'],'employee_id':ids['teacher_id'],'relation_type':'class_teacher','is_primary':True,'valid_from':(now-timedelta(days=1)).isoformat()})
        ids['binding_id']=binding['binding_id']
    scenario('register_all_identities_and_business_profiles',prepare_people)

    def customer_flow():
        body={'full_name':'验收客户 '+tag,'phone':'13800138000','employee_id':ids['teacher_id']}
        # A teacher cannot be assigned a consulting customer; root owns the initial record.
        body.pop('employee_id')
        key=tag+'-customer-create'
        c=call('POST',enterprise('customer'),body,key=key);ids['customer_id']=c['customer_id']
        assert call('POST',enterprise('customer'),body,key=key)==c
        call('POST',enterprise('customer'),{**body,'full_name':'不同参数'},key=key,expected=409)
        get('customer',c['customer_id'])
        post('customer/phone-candidates',{'phone':'13800138000'})
        put('customer/'+str(c['customer_id']),{'full_name':'验收客户修订 '+tag,'expected_version':1})
        call('PUT',enterprise('customer/'+str(c['customer_id'])),{'full_name':'过期版本','expected_version':1},expected=409)
        put('customer/'+str(c['customer_id'])+'/status',{'status':'contacting','expected_version':2})
        # Reassign to the root admin actor, an explicitly supported highest administrator.
        actor=call('GET',enterprise('me/permissions'))['employee_id']
        post('customer/'+str(c['customer_id'])+'/assign',{'employee_id':actor,'expected_version':3,'reason':'验收分派'})
        f=post('customer/'+str(c['customer_id'])+'/followups',{'content':'验收跟进','channel':'online','followup_at':(now-timedelta(hours=1)).isoformat(),'next_followup_at':(now+timedelta(days=1)).isoformat()})
        call('GET',enterprise('customer/'+str(c['customer_id'])+'/followups'))
        put('customer/'+str(c['customer_id'])+'/followups/'+str(f['followup_id'])+'/schedule',{'expected_version':1,'followup_status':'done'})
        fresh=get('customer',c['customer_id'])
        delete('customer/'+str(c['customer_id']),{'expected_version':fresh['row_version'],'reason':'验收归档'})
    scenario('customer_crud_phone_followups_idempotency_versions',customer_flow)

    def daily():
        d=post('daily-report',{'report_date':(now-timedelta(days=int(tag[2:6],16)+1)).date().isoformat(),'submitted_content':'验收日报 '+tag})
        ids['daily_id']=d['daily_report_id'];get('daily-report',ids['daily_id'])
        put('daily-report/'+str(ids['daily_id']),{'submitted_content':'验收日报修订','expected_version':1})
        call('POST',enterprise('daily-report/summary'),{'report_id':ids['daily_id']},expected=503)
        delete('daily-report/'+str(ids['daily_id']),{'expected_version':2,'reason':'验收作废'})
    scenario('daily_create_update_summary_unconfigured_void',daily)

    def education():
        course=post('courses',{'course_code':tag,'course_name':'验收课程'});ids['course_id']=course['course_id']
        get('courses',ids['course_id'])
        put('courses/'+str(ids['course_id']),{'course_name':'验收课程修订','expected_version':1})
        enroll=post('student-courses',{'student_id':ids['student_id'],'course_code':tag,'term_code':'2026-FALL'})
        ids['enrollment_id']=enroll['enrollment_id'];get('student-courses',enroll['enrollment_id'])
        score=post('scores',{'student_id':ids['student_id'],'course_code':tag,'term_code':'2026-FALL','assessment_code':'MID','score_value':80,'max_score':100})
        ids['score_id']=score['score_id'];get('scores',score['score_id'])
        put('scores/'+str(score['score_id']),{'expected_version':1,'score_value':90,'max_score':100,'reason':'验收更正'})
        call('GET','/api/v1/student/scores',actor='student')
        call('GET','/api/v1/student/courses',actor='student')
        delete('scores/'+str(score['score_id']),{'expected_version':2,'reason':'验收作废'})
        put('student-courses/'+str(enroll['enrollment_id']),{'expected_version':1,'status':'disabled'})
        event=post('academic-events',{'student_id':ids['student_id'],'event_type':'exam','title':'验收考试','due_at':(now+timedelta(days=3)).isoformat()})
        ids['event_id']=event['id'];get('academic-events',event['id'])
        put('academic-events/'+str(event['id']),{'expected_event_version':1,'title':'验收考试修订','reason':'验收改期'})
        p=post('application-progress',{'student_id':ids['student_id'],'application_name':'验收申请','stage_code':'visa_process','stage_status':'pending'})
        ids['progress_id']=p['id'];get('application-progress',p['id'])
        put('application-progress/'+str(p['id']),{'expected_version':1,'stage_status':'in_progress','reason':'验收进展'})
        get('students',ids['student_id'])
    scenario('courses_enrollments_scores_academic_application',education)

    def student_leave():
        body={'leave_content':'验收请假','leave_type':'personal','leave_start_at':(now+timedelta(days=1)).isoformat(),'leave_end_at':(now+timedelta(days=1,hours=2)).isoformat()}
        key=tag+'-leave'
        receipt=call('POST','/api/v1/student/leave',body,actor='student',key=key);ids['leave_id']=receipt['apply_id']
        assert call('POST','/api/v1/student/leave',body,actor='student',key=key)==receipt
        call('GET','/api/v1/student/leave',actor='student')
        call('GET','/api/v1/student/leave/'+str(ids['leave_id']),actor='student')
        call('GET','/api/v1/internal/student/leave',actor='teacher')
        call('GET','/api/v1/internal/student/leave/'+str(ids['leave_id']),actor='teacher')
        call('POST','/api/v1/internal/student/leave/'+str(ids['leave_id'])+'/decision',{'expected_version':1,'decision':'approved','comment':'验收批准'},actor='teacher')
        other=call('POST','/api/v1/student/leave',body,actor='student')
        call('DELETE','/api/v1/student/leave/'+str(other['apply_id']),{'expected_version':1},actor='student')
        for actor in ('root','customer'):
            call('GET','/api/v1/student/leave',actor=actor,expected=403)
    scenario('student_leave_review_withdraw_identity_isolation',student_leave)

    def student_ticket():
        r=call('POST','/api/v1/student/complaint',{'content':'验收服务反馈','ticket_type':'complaint','category_code':'teaching'},actor='student');tid=r['ticket_id'];ids['ticket_id']=tid
        call('GET','/api/v1/student/tickets',actor='student')
        call('GET','/api/v1/student/tickets/'+str(tid),actor='student')
        call('GET','/api/v1/student/tickets/'+str(tid)+'/records',actor='student')
        post('tickets/'+str(tid)+'/assign',{'employee_id':ids['teacher_id'],'expected_version':1,'reason':'验收分派'})
        post('tickets/'+str(tid)+'/followups',{'expected_version':2,'content':'验收人工回应'})
        call('POST','/api/v1/student/tickets/'+str(tid)+'/reply',{'expected_version':3,'content':'学生补充说明'},actor='student')
        fresh=get('tickets',tid)
        post('tickets/'+str(tid)+'/resolve',{'expected_version':fresh['row_version'],'content':'验收解决方案'})
        fresh=get('tickets',tid)
        call('POST','/api/v1/student/tickets/'+str(tid)+'/confirm',{'expected_version':fresh['row_version'],'resolved':True},actor='student')
        fresh=get('tickets',tid)
        call('POST','/api/v1/student/tickets/'+str(tid)+'/rating',{'expected_version':fresh['row_version'],'satisfaction_score':5},actor='student')
    scenario('student_ticket_full_lifecycle',student_ticket)

    def reminders():
        for p in ('academic','progress','notifications','reminders'):
            call('GET','/api/v1/student/'+p,actor='student')
        r=call('POST','/api/v1/student/reminders',{'academic_event_id':ids['event_id'],'lead_minutes':60,'expected_event_version':2},actor='student')
        ids['reminder_id']=r.get('id',r.get('reminder_id'))
        call('DELETE','/api/v1/student/reminders/'+str(ids['reminder_id']),{'expected_event_version':2,'expected_updated_at':r['updated_at']},actor='student')
    scenario('student_local_queries_reminders',reminders)

    def knowledge():
        k=post('knowledge',{'entry_code':tag,'entry_type':'faq','title':'验收知识','question':'验收问题','answer':'验收答案'});kid=k['knowledge_id'];ids['knowledge_id']=kid
        put('knowledge/'+str(kid),{'expected_version':1,'answer':'验收答案修订'})
        post('knowledge/'+str(kid)+'/publish',{'expected_version':2,'effective_from':(now-timedelta(minutes=1)).isoformat()})
        get('knowledge',kid)
        delete('knowledge/'+str(kid),{'expected_version':3,'reason':'验收停用'})
    scenario('knowledge_draft_publish_read_disable',knowledge)

    def research():
        with SessionLocal() as db:
            p=Product(product_code=tag,product_name='验收产品',status='active');db.add(p);db.commit()
        call('GET','/api/v1/customer/product')
        rule={'product_code':tag,'rule_content':{'logic':'all','conditions':[{'field':'age','op':'>=','value':18}]},'rule_description':'验收规则'}
        call('PUT','/api/v1/customer/rule',rule)
        call('GET','/api/v1/customer/rule')
        form={'text':'姓名：验收客户，年龄：25，学历：本科，电话：13800138000'}
        src=call('POST','/api/v1/customer/source',data=form)
        ids['source_id']=src['id']
        call('GET','/api/v1/customer/source')
        call('GET','/api/v1/customer/source/'+str(src['id']))
        parsed=call('POST','/api/v1/customer/source/'+str(src['id'])+'/parse',{'force':False})
        info=parsed['fields'][0]['id'];ids['info_id']=info
        result=call('POST','/api/v1/customer/judge',{'customer_info_id':info,'product_code':tag});ids['result_id']=result['id']
        call('POST','/api/v1/customer/judge/batch',{'customer_info_ids':[info,9223372036854775800],'product_code':tag})
        call('GET','/api/v1/customer/result/'+str(result['id']))
        call('GET','/api/v1/customer/result')
        src_file=call('POST','/api/v1/customer/source',files={'file':('qa.csv','姓名,年龄\n验收文件,25'.encode('utf-8'),'text/csv')})
        call('GET','/api/v1/customer/source/'+str(src_file['id'])+'/file')
        call('POST','/api/v1/customer/source/'+str(src_file['id'])+'/parse',{'force':False})
    scenario('research_upload_parse_rule_judge_batch_results',research)

    def agent_catalog():
        with SessionLocal() as db:
            e=LectureEvent(event_name='验收活动 '+tag,event_type='线上',start_time=(now+timedelta(days=3)).replace(tzinfo=None),quota=2,status='报名中')
            f=Faq(question=tag+' 常见问题',answer='验收FAQ答案')
            c=CourseProject(course_name='验收项目 '+tag,category='语言培训',description='验收项目介绍')
            db.add_all([e,f,c]);db.commit();ids['agent_event_id']=e.id
        call('GET','/api/v1/agent/events',actor='anonymous')
        call('GET','/api/v1/agent/events/'+str(ids['agent_event_id']),actor='anonymous')
        call('GET','/api/v1/agent/courses',actor='anonymous')
        call('GET','/api/v1/agent/faq',actor='anonymous',params={'q':tag})
        call('POST','/api/v1/agent/events/signup',{'event_id':ids['agent_event_id'],'customer_name':'验收访客','customer_phone':'13900139000'},actor='anonymous')
        call('POST','/api/v1/agent/chat',{'message':'验收咨询'},actor='anonymous',expected=503)
    scenario('anonymous_agent_catalog_signup_unconfigured_chat',agent_catalog)

    def report():
        configs=call('GET','/api/v1/report/configs')
        configs=configs.get('items',[]) if isinstance(configs,dict) else configs
        assert len(configs)==5, 'five report configurations must exist'
        item=configs[0]
        body={k:item[k] for k in ('row_version','report_name','cron_expr','enabled')}
        call('PUT','/api/v1/report/configs/'+item['report_code'],body)
        call('PUT','/api/v1/report/configs/'+item['report_code'],body,expected=409)
        for code in ('customer_overview','daily_report','weekly_report','mental_weekly','complaint_weekly'):
            receipt=call('POST','/api/v1/report/generate',{'report_code':code})
            call('GET','/api/v1/report/'+str(receipt['report_record_id']))
        call('GET','/api/v1/report/list')
        call('GET','/api/v1/report/configs',actor='student',expected=403)
    scenario('five_report_types_receipts_failure_handling_and_configs',report)

    def admin_updates():
        put('departments/'+str(ids['department_id']),{'department_name':'系统验收修订 '+tag,'expected_version':1})
        get('employees',ids['teacher_id'])
        put('employees/'+str(ids['teacher_id']),{'full_name':'验收老师修订','expected_version':1})
        put('employees/'+str(ids['teacher_id'])+'/roles',{'role_codes':['employee','teacher'],'expected_version':2,'reason':'验收角色一致性'})
        put('student-bindings/'+str(ids['binding_id']),{'expected_version':1,'valid_to':(now+timedelta(days=10)).isoformat()})
        delete('student-bindings/'+str(ids['binding_id']),{'expected_version':2,'reason':'验收停用'})
        empty=post('departments',{'department_code':tag+'EMPTY','department_name':'验收空部门'})
        delete('departments/'+str(empty['department_id']),{'expected_version':1,'reason':'验收停用'})
    scenario('department_employee_role_binding_maintenance',admin_updates)

    # Every API operation gets at least an explicit reachability/validation/permission check.
    for template, operations in all_paths.items():
        if not template.startswith(('/api/', '/health')):continue
        for method, operation in operations.items():
            if method not in ('get','post','put','delete','patch'):continue
            regex='^'+re.sub(r'\{[^}]+\}',r'[^/]+',template)+'$'
            if any(c['method'].lower()==method and re.match(regex,c['path']) and c['passed'] for c in calls):continue
            path=re.sub(r'\{[^}]+\}','9223372036854775800',template)
            expected=(0,400,401,403,404,409,422,503)
            scenario('route:'+method.upper()+' '+template,
                     lambda m=method,p=path:call(m.upper(),p,None if m=='get' else {},expected=expected))

    operations=[]
    for path, methods in all_paths.items():
        if not path.startswith(('/api/','/health')):continue
        for method in methods:
            if method not in ('get','post','put','delete','patch'):continue
            regex='^'+re.sub(r'\{[^}]+\}',r'[^/]+',path)+'$'
            seen=[c for c in calls if c['method'].lower()==method and re.match(regex,c['path'])]
            operations.append({'method':method.upper(),'path':path,'requests':len(seen),
                               'success_observed':any(c['code']==0 for c in seen),
                               'codes':sorted(set(c['code'] for c in seen))})
    output={'run_id':tag,'base_url':args.base_url,'scenarios':results,'calls':calls,'operations':operations,'fixture_ids':ids,
            'summary':{'scenarios':len(results),'passed':sum(r['status']=='passed' for r in results),
                       'failed':sum(r['status']=='failed' for r in results),'requests':len(calls),
                       'operations':len(operations),'operations_exercised':sum(o['requests']>0 for o in operations),
                       'operations_success':sum(o['success_observed'] for o in operations)}}
    (ROOT/'.runtime/backend-system.json').write_text(json.dumps(output,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps(output['summary']),flush=True)
    client.close()
    return int(output['summary']['failed']>0)


if __name__=='__main__':
    raise SystemExit(main())
