"""Real MySQL collaboration checks in a rollback-only outer transaction.

TestClient exercises production dependencies except the database session is bound
to a real MySQL savepoint. Explicit service configuration exists only in this run.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from sqlalchemy import select,insert,update,func
from sqlalchemy.orm import Session
from app.config import settings
from app.database import engine,get_db
from app.main import app
from app.models import common as t
from app.core.student.student_auth import Principal
from app.core.common.authorization import permissions_for
from app.schemas.student.student import MentalAssessment
from app.services.student.student_service import StudentService,warnings,utcnow


def main():
    baseline=json.loads((ROOT/'.runtime/backend-system.json').read_text(encoding='utf-8'))
    ids=baseline['fixture_ids'];tag=baseline['run_id'];run='SUP'+uuid4().hex[:10]
    results=[];calls=[];tokens={};now=datetime.now(timezone.utc)
    with engine.connect() as connection:
        outer=connection.begin()
        db=Session(bind=connection,join_transaction_mode='create_savepoint',expire_on_commit=False)
        def database():yield db
        original=app.dependency_overrides.copy();app.dependency_overrides[get_db]=database
        try:
            with patch.object(settings,'STUDENT_WARNING_ASSIGNER_IDS',[ids['manager_id']]), \
                 patch.object(settings,'STUDENT_WARNING_ASSIGNMENT_SCOPES',{ids['manager_id']:[ids['student_id']]}), \
                 patch.object(settings,'STUDENT_DIFY_KEY',__import__('pydantic').SecretStr('')), \
                 patch.object(settings,'ENTERPRISE_DIFY_API_KEY',''), \
                 TestClient(app,raise_server_exceptions=False) as client:
                def call(method,path,body=None,actor='root',expected=0,**kwargs):
                    h={'Idempotency-Key':run+'-'+uuid4().hex}
                    if actor in tokens:h['Authorization']='Bearer '+tokens[actor]
                    r=client.request(method,path,json=body,headers=h,**kwargs)
                    obj=r.json();code=obj.get('code',r.status_code)
                    good=code in expected if isinstance(expected,tuple) else code==expected
                    calls.append({'method':method,'path':path,'actor':actor,'code':code,'passed':good,'message':obj.get('message','')})
                    assert good,f'{method} {path}: {str(obj)[:400]}'
                    return obj.get('data')
                def case(name,work):
                    try:work();results.append({'name':name,'status':'passed'})
                    except Exception as exc:db.rollback();results.append({'name':name,'status':'failed','reason':str(exc)});print('FAILED',name,str(exc),flush=True)
                for actor in ('root','teacher','manager','student'):
                    user='root' if actor=='root' else tag+'_'+actor
                    data=call('POST','/api/v1/auth/login',{'username':user,'password':'root' if actor=='root' else '123456'},actor='anonymous')
                    tokens[actor]=data['access_token']
                def setup():
                    db.execute(update(t.student_staff_binding).where(t.student_staff_binding.c.binding_id==ids['binding_id']).values(status='active',is_primary=True))
                    db.execute(update(t.employee).where(t.employee.c.employee_id==ids['teacher_id']).values(position_title='学生关怀老师',role_codes=['employee','teacher','counselor']))
                    db.execute(update(t.student_profile).where(t.student_profile.c.student_id==ids['student_id']).values(customer_id=ids['customer_id']))
                    # Use the registration customer, which remains active and in the fixture department.
                    account=db.scalar(select(t.UserAccount).where(t.UserAccount.username==tag+'_customer'))
                    db.execute(update(t.student_profile).where(t.student_profile.c.student_id==ids['student_id']).values(customer_id=account.customer_id))
                    db.execute(update(t.customer_profile).where(t.customer_profile.c.customer_id==account.customer_id).values(employee_id=ids['manager_id']))
                    db.commit()
                case('rollback_only_fixture_roles_and_bindings',setup)
                def mental_workflow():
                    user=db.scalar(select(t.UserAccount).where(t.UserAccount.username==tag+'_student'))
                    actor=Principal('student',ids['student_id'],scopes=tuple(permissions_for('student')),user_id=user.user_id)
                    # An explicitly synthetic assessment seeds the human handling flow; it is not an AI result.
                    assessment=MentalAssessment(emotion_tag='合成验收样本',emotion_score=20,risk_level='high',trigger_reason='合成数据，仅验证人工流转')
                    StudentService(db).record_mental(actor,run+'mental','合成验收样本',assessment)
                    warning=db.execute(select(warnings).where(warnings.c.student_id==ids['student_id']).order_by(warnings.c.id.desc())).mappings().first();wid=warning['id']
                    call('GET','/api/v1/internal/student/warnings',actor='teacher')
                    call('GET',f'/api/v1/internal/student/warnings/{wid}',actor='teacher')
                    for version,verb in enumerate(('ack','follow','close'),start=1):
                        call('POST',f'/api/v1/internal/student/warnings/{wid}/{verb}',{'expected_version':version,'note':'合成人工处置验收'},actor='teacher')
                    call('GET',f'/api/v1/internal/student/warnings/{wid}',actor='student',expected=403)
                    StudentService(db).record_mental(actor,run+'mental2','合成接管验收',assessment)
                    wid=db.scalar(select(warnings.c.id).where(warnings.c.student_id==ids['student_id']).order_by(warnings.c.id.desc()))
                    db.execute(update(warnings).where(warnings.c.id==wid).values(follower_id=None));db.commit()
                    call('GET','/api/v1/internal/student/warnings/assignments',actor='manager')
                    call('POST',f'/api/v1/internal/student/warnings/{wid}/assign',{'expected_version':1,'employee_id':ids['teacher_id'],'reason':'合成接管验收'},actor='manager')
                case('mental_warning_ack_follow_close_and_scoped_assignment',mental_workflow)
                def leave_takeover():
                    r=call('POST','/api/v1/student/leave',{'leave_content':'接管验收','leave_start_at':(now+timedelta(days=2)).isoformat(),'leave_end_at':(now+timedelta(days=2,hours=1)).isoformat()},actor='student')
                    aid=r['apply_id'];db.execute(update(t.student_admin_service).where(t.student_admin_service.c.id==aid).values(reviewer_id=None));db.commit()
                    call('GET','/api/v1/internal/student/leave/assignments',actor='manager')
                    call('POST',f'/api/v1/internal/student/leave/{aid}/assign',{'expected_version':1,'employee_id':ids['teacher_id'],'reason':'接管验收'},actor='manager')
                case('leave_unassigned_takeover',leave_takeover)
                def notifications():
                    n=t.business_notification
                    # Prepare sent-state fixtures to test read semantics independently of the worker.
                    db.execute(update(n).where(n.c.student_id==ids['student_id']).values(delivery_status='sent',sent_at=utcnow()))
                    db.execute(update(n).where(n.c.employee_id==ids['teacher_id'],n.c.event_code.like('student.%')).values(delivery_status='sent',sent_at=utcnow()))
                    db.commit()
                    data=call('GET','/api/v1/student/notifications',actor='student');assert data['items']
                    nid=data['items'][0]['notification_id']
                    call('GET',f'/api/v1/student/notifications/{nid}',actor='student')
                    call('POST',f'/api/v1/student/notifications/{nid}/read',actor='student')
                    call('POST',f'/api/v1/student/notifications/{nid}/read',actor='student')
                    data=call('GET','/api/v1/internal/student/notifications',actor='teacher');assert data['items']
                    nid=data['items'][0]['notification_id'];call('POST',f'/api/v1/internal/student/notifications/{nid}/read',actor='teacher')
                    root_id=db.scalar(select(t.UserAccount.user_id).where(t.UserAccount.username=='root'))
                    root_actor=db.execute(select(t.employee).where(t.employee.c.login_provider=='platform_admin',t.employee.c.login_subject==str(root_id))).mappings().first()
                    key=run+'notice'
                    nid=db.execute(insert(n).values(employee_id=root_actor['employee_id'],entity_type='employee_daily_report',entity_id=ids['daily_id'],event_code='enterprise.test.acceptance',title='合成通知验收',content='仅验收',channel='in_app',dedupe_key=key,delivery_status='sent',sent_at=utcnow())).inserted_primary_key[0];db.commit()
                    call('GET',f'/api/v1/enterprise/notifications/{nid}')
                    call('POST',f'/api/v1/enterprise/notifications/{nid}/read')
                case('student_teacher_enterprise_notification_detail_read_replay',notifications)
                def local_maintenance():
                    employee=call('POST','/api/v1/enterprise/employees',{'employee_no':run,'full_name':'合成教务','department_id':ids['department_id'],'login_provider':'qa','login_subject':run,'joined_date':now.date().isoformat(),'position_title':'教务'})
                    registered=call('POST','/api/v1/auth/register',{'identity_type':'employee','username':run,'employee_id':employee['employee_id']})
                    data=call('POST','/api/v1/auth/login',{'username':run,'password':'123456'},actor='anonymous');tokens['academic']=data['access_token']
                    call('POST','/api/v1/enterprise/student-bindings',{'student_id':ids['student_id'],'employee_id':employee['employee_id'],'relation_type':'score_editor','course_scope_code':tag,'valid_from':(now-timedelta(days=1)).isoformat()})
                    call('PUT',f'/api/v1/internal/student/academic/{ids["student_id"]}',{'event_type':'exam','title':'本地教务验收','due_at':(now+timedelta(days=4)).isoformat(),'source_timezone':'Asia/Shanghai'},actor='academic')
                    call('PUT',f'/api/v1/internal/student/progress/{ids["student_id"]}',{'external_application_id':run,'application_name':'本地申请验收','stage_code':'visa_process','stage_status':'pending'},actor='manager')
                case('employee_creation_existing_profile_registration_and_local_maintenance',local_maintenance)
                def sync_contract():
                    service_token=uuid4().hex+uuid4().hex;tokens['sync']=service_token
                    with patch.object(settings,'STUDENT_SYNC_ENABLED',True), \
                         patch.object(settings,'STUDENT_SYNC_TOKEN',__import__('pydantic').SecretStr(service_token)), \
                         patch.object(settings,'STUDENT_SYNC_ALLOWED_SOURCES',['qa']), \
                         patch.object(settings,'STUDENT_SYNC_ALLOWED_STUDENT_IDS',[ids['student_id']]):
                        academic={'student_id':ids['student_id'],'source_system':'qa','records':[{'external_event_id':run,'event_type':'exam','title':'合成同步节点','due_at':(now+timedelta(days=6)).isoformat(),'source_timezone':'Asia/Shanghai','source_updated_at':now.isoformat()}]}
                        call('POST','/api/v1/internal/student/sync/academic',academic,actor='sync')
                        call('POST','/api/v1/internal/student/sync/progress',{'student_id':ids['student_id'],'source_system':'qa','records':[{'external_application_id':run,'application_name':'合成同步申请','stage_code':'document_review','stage_status':'pending','source_updated_at':now.isoformat()}]},actor='sync')
                        call('POST','/api/v1/internal/student/sync/academic',{**academic,'source_system':'unauthorized'},actor='sync',expected=403)
                        call('POST','/api/v1/internal/student/sync/academic/pull',{'student_id':ids['student_id']},actor='sync',expected=(409,503))
                case('future_sync_batch_authority_and_unconfigured_pull',sync_contract)
                def no_external():
                    for path,body in [('/api/v1/enterprise/command',{'text':'创建客户'}),('/api/v1/enterprise/nl2sql',{'question':'查询客户'})]:
                        call('POST',path,body,expected=503)
                    call('POST','/api/v1/enterprise/onboarding/ask',{'question':run+'不存在的资料'})
                    for path,body in [('/api/v1/student/mental/monitor',{'chat_content':'合成评估测试'}),('/api/v1/student/chat',{'message':'合成聊天测试'})]:
                        call('POST',path,body,actor='student',expected=503)
                    call('POST','/api/v1/student/actions/confirm',{'action_token':'invalid'},actor='student',expected=401)
                    from app.core.student.student_auth import sign_token
                    token=sign_token({'subject':'student:'+str(ids['student_id']),'jti':uuid4().hex,'action':'leave.submit',
                        'parameters':{'leave_content':'合成凭证确认验收','leave_start_at':(now+timedelta(days=5)).isoformat(),'leave_end_at':(now+timedelta(days=5,hours=1)).isoformat()}},'student-action')
                    call('POST','/api/v1/student/actions/confirm',{'action_token':token},actor='student')
                    call('POST','/api/v1/enterprise/command/confirm',{'token':'invalid','action':'customer.create','target':{},'fields':{'full_name':'验收'}},expected=409)
                    import jwt
                    from app.repositories.enterprise.enterprise_repository import digest
                    preview={'action':'customer.create','target':{},'fields':{'full_name':'合成企业确认验收'},'needs_clarification':False}
                    uid=db.scalar(select(t.UserAccount.user_id).where(t.UserAccount.username=='root'))
                    signed=jwt.encode({'sub':str(uid),'aud':'enterprise-confirm','iat':now,'exp':now+timedelta(minutes=5),'payload_hash':digest(preview),'department_id':None},settings.ENTERPRISE_CONFIRM_SECRET,algorithm='HS256')
                    call('POST','/api/v1/enterprise/command/confirm',{'token':signed,**{k:preview[k] for k in ('action','target','fields')}})
                    import io,wave
                    sample=io.BytesIO()
                    with wave.open(sample,'wb') as audio:
                        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(16000);audio.writeframes(b'\0'*(16000*2))
                    call('POST','/api/v1/enterprise/voice/transcribe',files={'file':('qa.wav',sample.getvalue(),'audio/wav')},expected=(0,503))
                case('external_missing_config_no_model_call_and_tamper_rejection',no_external)
                assert outer.is_active,'service commit ended rollback-only transaction'
        finally:
            app.dependency_overrides.clear();app.dependency_overrides.update(original);db.close()
            if outer.is_active:outer.rollback()
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(t.operation_log).where(t.operation_log.c.request_key.like(run+'%')))==0
        assert connection.scalar(select(func.count()).select_from(t.employee).where(t.employee.c.employee_no==run))==0
    output={'scenarios':results,'calls':calls,'test_business_changes_rolled_back':True,
            'summary':{'scenarios':len(results),'passed':sum(x['status']=='passed' for x in results),'failed':sum(x['status']=='failed' for x in results),'requests':len(calls)}}
    (ROOT/'.runtime/backend-supplement.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output['summary']))
    return int(output['summary']['failed']>0)


if __name__=='__main__':raise SystemExit(main())
