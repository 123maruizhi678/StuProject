"""企业授权、固定服务、数据库事务、回放及SQL边界的集成回归。"""
import unittest
from unittest.mock import patch
from datetime import datetime,date,timedelta,timezone
from types import SimpleNamespace
from sqlalchemy import create_engine,insert,select,func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.database import Base,get_db
from app.models import common as t
from app.models import enterprise as own
from app.core.common.auth import get_current_account
from app.core.common.response import BusinessException
from app.core.enterprise.enterprise_authorization import context_for
from app.repositories.enterprise.enterprise_repository import EnterpriseRepository
from app.services.enterprise.enterprise_customer import CustomerService
from app.services.enterprise.enterprise_daily_report import DailyReportService
from app.services.enterprise.enterprise_score import ScoreService
from app.services.enterprise.enterprise_ticket import TicketService
from app.services.enterprise.enterprise_knowledge import KnowledgeService
from app.core.enterprise.enterprise_sql_guard import validate_query

class EnterpriseTests(unittest.TestCase):
    def setUp(self):
        from app.config import settings
        from cryptography.fernet import Fernet
        secrets = patch.multiple(settings,
            AUTH_SECRET_KEY='fictional-enterprise-auth-signing-key-for-tests-only',
            ENTERPRISE_CONFIRM_SECRET='fictional-enterprise-confirm-key-for-tests-only',
            ENTERPRISE_PHONE_LOOKUP_SECRET='fictional-enterprise-phone-lookup-key-for-tests-only',
            ENTERPRISE_PHONE_ENCRYPTION_KEY=Fernet.generate_key().decode())
        secrets.start()
        self.addCleanup(secrets.stop)
        self.engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
        # 只创建本次企业依赖，避免把无关报告MySQL方言DDL带入SQLite。
        tables=[getattr(t,name).__table__ if name=='UserAccount' else getattr(t,name) for name in t.__all__]
        tables += [getattr(own,name) for name in own.__all__]
        Base.metadata.create_all(self.engine,tables=tables)
        self.db=Session(self.engine)
        for d in [1,2]:self.db.execute(insert(t.org_department).values(department_id=d,department_code=f'D{d}',department_name=f'部门{d}',status='active'))
        roles={1:['consultant','manager','academic','teacher'],2:['consultant'],3:['consultant','manager']}
        for e in [1,2,3]:
            self.db.execute(insert(t.employee).values(employee_id=e,employee_no=f'E{e}',full_name=f'员工{e}',department_id=1 if e<3 else 2,login_provider='local',login_subject=f'E{e}',role_codes=roles[e],status='active',joined_date=date(2020,1,1)))
            self.db.add(t.UserAccount(user_id=e,username=f'u{e}',password_hash='unused',identity_type='employee',employee_id=e))
        self.db.execute(insert(t.student_profile).values(student_id=1,student_no='S1',full_name='测试学生',department_id=1,status='active',is_archived=False))
        self.db.execute(insert(t.student_staff_binding).values(student_id=1,employee_id=1,relation_type='score_editor',course_scope_code='MATH',is_primary=False,status='active',valid_from=datetime(2020,1,1)))
        self.db.execute(insert(t.student_staff_binding).values(student_id=1,employee_id=1,relation_type='class_teacher',is_primary=True,status='active',valid_from=datetime(2020,1,1)))
        self.db.commit()
        self.repo=self.repository(1)
    def tearDown(self):self.db.close();self.engine.dispose()
    def repository(self,user):return EnterpriseRepository(self.db,context_for(self.db,self.db.get(t.UserAccount,user)))
    def platform_admin(self):
        self.db.add(t.UserAccount(user_id=50,username='highest-admin',password_hash='unused',identity_type='admin'));self.db.commit()
        return self.repository(50)
    def test_platform_admin_has_all_actions_without_account_employee_fk(self):
        repo=self.platform_admin()
        self.assertTrue(repo.ctx.is_admin)
        for action in ['customer.create','customer.assign','score.write','academic.write','ticket.handle','knowledge.publish','role.manage','audit.read']:self.assertTrue(repo.ctx.can(action),action)
        customer=self.customer(self.repository(3))
        self.assertEqual(repo.one('customer',customer['customer_id'])['department_id'],2)
    def test_platform_admin_todos_include_other_reviewers_leave(self):
        from app.api.enterprise.enterprise import todos
        leave_id=self.db.execute(insert(t.student_admin_service).values(student_id=1,apply_type='leave',apply_content='测试待办',leave_start_at=datetime(2026,10,20),leave_end_at=datetime(2026,10,21),reviewer_id=2,request_key='highest-todo-leave',request_hash='a'*64)).inserted_primary_key[0]
        self.db.commit()
        ordinary=todos(db=self.db,ctx=self.repo.ctx)['data']['items']
        self.assertFalse(any(row['type']=='leave' and row['id']==leave_id for row in ordinary))
        admin=todos(db=self.db,ctx=self.platform_admin().ctx)['data']['items']
        self.assertTrue(any(row['type']=='leave' and row['id']==leave_id for row in admin))
    def test_platform_admin_uses_dedicated_actor_and_audits_real_account(self):
        repo=self.platform_admin();row=CustomerService(repo).mutate('create','highest-admin-customer',{'full_name':'管理员新客户'})
        actor=self.db.execute(select(t.employee).where(t.employee.c.employee_id==row['employee_id'])).mappings().one()
        self.assertEqual(actor['login_provider'],'platform_admin');self.assertEqual(actor['login_subject'],'50')
        self.assertIsNone(self.db.get(t.UserAccount,50).employee_id)
        audit=self.db.execute(select(t.operation_log).where(t.operation_log.c.request_key=='highest-admin-customer')).mappings().one()
        self.assertEqual(audit['before_data']['operator_user_id'],50)
        CustomerService(repo).mutate('create','highest-admin-customer-2',{'full_name':'第二位客户'})
        self.assertEqual(self.db.scalar(select(func.count()).select_from(t.employee).where(t.employee.c.login_provider=='platform_admin')),1)
    def test_highest_admin_can_manage_other_authors_daily_and_unbound_scores(self):
        daily=DailyReportService(self.repo).mutate('create','ordinary-daily-original',{'report_date':date.today(),'submitted_content':'原始日报'})
        admin=self.platform_admin()
        changed=DailyReportService(admin).mutate('update','highest-admin-daily',{'submitted_content':'管理员更正','expected_version':1},daily['daily_report_id'])
        self.assertEqual(changed['employee_id'],1);self.assertEqual(changed['department_id_at_submit'],1)
        score=ScoreService(admin).mutate('create','highest-admin-score',{'student_id':1,'course_code':'NO_BINDING','term_code':'2026','assessment_code':'EX','attempt_no':1,'score_value':88,'max_score':100})
        self.assertEqual(score['score_value'],88)
        with self.assertRaises(BusinessException):ScoreService(admin).mutate('update','highest-admin-score-invalid',{'score_value':101,'max_score':100,'reason':'测试校验','expected_version':1},score['score_id'])
    def test_employee_admin_is_highest_and_revocation_is_rechecked(self):
        from sqlalchemy import update
        self.db.execute(update(t.employee).where(t.employee.c.employee_id==1).values(role_codes=['employee','admin']));self.db.commit()
        repo=self.repository(1);self.assertTrue(repo.ctx.is_admin);self.assertTrue(repo.ctx.can('score.write'))
        self.db.execute(update(t.employee).where(t.employee.c.employee_id==1).values(role_codes=['employee']));self.db.commit()
        with self.assertRaises(BusinessException):CustomerService(repo).mutate('create','revoked-highest-admin',{'full_name':'不应创建'})
    def test_dify_context_serializes_real_database_dates(self):
        import json
        from unittest.mock import patch
        from app.clients.enterprise import enterprise_dify
        class Transport:
            def post_json_sync(self,path,*,api_key,payload):
                context=json.loads(payload['inputs']['payload'])['context']
                self.context=context
                return {'data':{'status':'succeeded','outputs':{'scene':'extract','result':{'contract_version':'enterprise-v1','action':'daily.create','target':{},'fields':{},'missing_fields':[],'needs_clarification':False}}}}
        transport=Transport()
        with patch.object(enterprise_dify,'settings',SimpleNamespace(ENTERPRISE_DIFY_API_KEY='unit-test-key',ENTERPRISE_DIFY_CONTRACT_VERSION='enterprise-v1')):
            enterprise_dify.EnterpriseDifyClient(transport).run('extract',{'context':{'targets':[{'report_date':date(2026,10,17),'created_at':datetime(2026,10,17,1,2,3)}]}},50)
        self.assertEqual(transport.context['targets'][0]['report_date'],'2026-10-17')
        self.assertEqual(transport.context['targets'][0]['created_at'],'2026-10-17T01:02:03')
    def customer(self,repo=None):return CustomerService(repo or self.repo).mutate('create','customer-create-1',{'full_name':'测试客户'})
    def test_customer_scope_and_replay(self):
        row=self.customer();cid=row['customer_id']
        self.assertEqual(row,self.customer())
        self.assertEqual(self.db.scalar(select(func.count()).select_from(t.customer_profile)),1)
        with self.assertRaises(BusinessException):CustomerService(self.repo).mutate('create','customer-create-1',{'full_name':'不同内容'})
        with self.assertRaises(BusinessException):self.repository(3).one('customer',cid)
    def test_phone_canonical_token_has_encrypted_storage(self):
        from app.core.common.phone_protection import phone_fields
        national=phone_fields('13800138000');international=phone_fields('+86 13800138000')
        self.assertEqual(national['phone_lookup_token'],international['phone_lookup_token'])
        self.assertNotIn(b'13800138000',national['phone_ciphertext'])
        self.assertNotEqual(national['phone_ciphertext'],international['phone_ciphertext'])
        with self.assertRaises(BusinessException):phone_fields('not-a-phone')
    def test_version_conflict_does_not_leave_audit(self):
        row=self.customer()
        with self.assertRaises(BusinessException):CustomerService(self.repo).mutate('update','bad-version-key',{'full_name':'更正','expected_version':99},row['customer_id'])
        self.assertEqual(self.db.scalar(select(func.count()).select_from(t.operation_log)),1)
    def test_daily_department_snapshot_and_author(self):
        service=DailyReportService(self.repo);row=service.mutate('create','daily-create-1',{'report_date':date.today(),'submitted_content':'首次正文'})
        from sqlalchemy import update
        self.db.execute(update(t.employee).where(t.employee.c.employee_id==1).values(department_id=2));self.db.commit()
        updated=DailyReportService(self.repository(1)).mutate('update','daily-update-1',{'expected_version':1,'submitted_content':'修订正文'},row['daily_report_id'])
        self.assertEqual(updated['department_id_at_submit'],1)
        self.assertEqual(updated['submitted_at'],row['submitted_at'])
        with self.assertRaises(BusinessException):self.repository(3).one('daily',row['daily_report_id'])
    def test_course_write_does_not_borrow_manager_range(self):
        good={'student_id':1,'course_code':'MATH','term_code':'2026','assessment_code':'EX1','attempt_no':1,'score_value':80,'max_score':100}
        result=ScoreService(self.repo).mutate('create','score-create-1',good)
        self.assertEqual(result['score_value'],80)
        with self.assertRaises(BusinessException):ScoreService(self.repo).mutate('create','score-create-2',{**good,'course_code':'OTHER'})
    def test_disabled_employee_cannot_replay(self):
        self.customer()
        from sqlalchemy import update
        self.db.execute(update(t.employee).where(t.employee.c.employee_id==1).values(status='disabled'));self.db.commit()
        with self.assertRaises(BusinessException):self.customer()
    def test_no_source_knowledge_does_not_call_model(self):
        class ForbiddenModel:
            def run(self,*a):raise AssertionError('没有来源不应调用模型')
        self.assertEqual(KnowledgeService(self.repo,ForbiddenModel()).ask('不存在的制度')['citations'],[])
    def test_command_confirm_tampering_and_replay(self):
        from app.services.enterprise.enterprise_command import CommandService
        class Model:
            calls=0
            def run(self,*args):
                self.calls+=1
                return {'action':'customer.create','target':{},'fields':{'full_name':'命令测试客户'},'needs_clarification':False}
        model=Model();service=CommandService(self.repo,model)
        result=service.preview('新增命令测试客户','command-preview-1')
        self.assertEqual(self.db.scalar(select(func.count()).select_from(t.customer_profile)),0)
        self.assertEqual(service.preview('新增命令测试客户','command-preview-1'),result);self.assertEqual(model.calls,1)
        payload={k:result[k] for k in ('token','action','target','fields')}
        with self.assertRaises(BusinessException):service.confirm('command-confirm-bad',{**payload,'fields':{'full_name':'篡改名称'}})
        saved=service.confirm('command-confirm-1',payload)
        self.assertEqual(service.confirm('command-confirm-1',payload),saved)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(t.customer_profile)),1)
    def test_academic_reschedule_is_atomic_and_keeps_cancelled_settings(self):
        from app.services.enterprise.enterprise_education import EducationService
        service=EducationService(self.repo);due=datetime.now(timezone.utc)+timedelta(days=3)
        row=service.mutate('academic','create','academic-create-1',{'student_id':1,'event_type':'exam','title':'考试','due_at':due})
        self.assertIsNone(row['synced_at']);self.assertEqual(row['source_system'],'local')
        for lead,status in [(60,'sent'),(120,'cancelled')]:self.db.execute(insert(t.student_academic_reminder).values(student_id=1,academic_event_id=row['id'],lead_minutes=lead,notify_at=due.replace(tzinfo=None)-timedelta(minutes=lead),event_version=1,status=status,sent_at=datetime.utcnow() if status=='sent' else None))
        self.db.commit()
        with self.assertRaises(BusinessException):service.mutate('academic','update','academic-bad-version',{'due_at':due+timedelta(days=1),'expected_event_version':99,'reason':'改期'},row['id'])
        self.assertEqual(self.db.scalar(select(t.student_academic_reminder.c.event_version).limit(1)),1)
        changed=service.mutate('academic','update','academic-update-1',{'due_at':due+timedelta(days=1),'expected_event_version':1,'reason':'改期'},row['id'])
        self.assertEqual(changed['event_version'],2)
        reminders=self.db.execute(select(t.student_academic_reminder).order_by(t.student_academic_reminder.c.lead_minutes)).mappings().all()
        self.assertEqual([r['status'] for r in reminders],['pending','cancelled']);self.assertTrue(all(r['event_version']==2 and r['sent_at'] is None for r in reminders))
        self.assertEqual(self.db.scalar(select(t.operation_log.c.change_reason).where(t.operation_log.c.request_key=='academic-update-1')),'改期')
    def test_course_enrollment_requires_exact_authorization(self):
        from app.services.enterprise.enterprise_education import EducationService
        service=EducationService(self.repo)
        service.mutate('course','create','course-create-math',{'course_code':'MATH','course_name':'数学'})
        service.mutate('course','create','course-create-other',{'course_code':'OTHER','course_name':'其他课程'})
        row=service.mutate('enrollment','create','enrollment-create-1',{'student_id':1,'course_code':'MATH','term_code':'2026'})
        self.assertEqual(row['status'],'active')
        with self.assertRaises(BusinessException):service.mutate('enrollment','create','enrollment-create-2',{'student_id':1,'course_code':'OTHER','term_code':'2026'})
    def test_progress_customer_scope_is_independent_of_academic_role(self):
        from app.services.enterprise.enterprise_education import EducationService
        from sqlalchemy import update
        customer=self.customer()
        self.db.execute(update(t.student_profile).where(t.student_profile.c.student_id==1).values(customer_id=customer['customer_id']));self.db.commit()
        service=EducationService(self.repo)
        row=service.mutate('progress','create','progress-create-1',{'student_id':1,'application_name':'本地申请','stage_code':'visa_process','stage_status':'pending'})
        self.assertEqual(row['source_system'],'local')
        with self.assertRaises(BusinessException):EducationService(self.repository(3)).mutate('progress','update','progress-out-of-scope',{'stage_status':'completed','expected_version':1,'reason':'测试'},row['id'])
    def test_followup_round_dedupe_and_generation_invalidation(self):
        from app.tasks.enterprise.enterprise_tasks import scan,publish_one
        customer=self.customer();service=CustomerService(self.repo);now=datetime.now(timezone.utc)
        row=service.followup(customer['customer_id'],'followup-create-1',{'content':'已沟通','channel':'phone','followup_at':now-timedelta(hours=3),'next_followup_at':now-timedelta(hours=2)})
        self.assertIsNotNone(row['schedule_operation_id'])
        scan(self.db);scan(self.db)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(t.business_notification)),1)
        service.followup(customer['customer_id'],'followup-reschedule-1',{'followup_status':'pending','next_followup_at':now+timedelta(days=1),'expected_version':1},row['followup_id'])
        self.assertTrue(publish_one(self.db))
        self.assertEqual(self.db.scalar(select(t.business_notification.c.delivery_status)),'dead_letter')
    def test_notification_sent_read_and_then_loses_visibility(self):
        from app.tasks.enterprise.enterprise_tasks import scan,publish_one
        from app.services.enterprise.enterprise_notification import mark_read
        from sqlalchemy import update
        customer=self.customer();now=datetime.now(timezone.utc)
        CustomerService(self.repo).followup(customer['customer_id'],'followup-visible-1',{'content':'已沟通','channel':'phone','followup_at':now-timedelta(hours=3),'next_followup_at':now-timedelta(hours=2)})
        scan(self.db);publish_one(self.db)
        notification=self.repo.page('notification')['items'][0]
        self.assertIsNotNone(mark_read(self.repo,notification['notification_id'])['read_at'])
        # 转为另一部门顾问，原收件人即使仍兼主管也不能读取另一部门事实。
        self.db.execute(update(t.customer_profile).where(t.customer_profile.c.customer_id==customer['customer_id']).values(employee_id=3,department_id=2));self.db.commit()
        self.assertEqual(self.repo.page('notification')['total'],0)
    def test_ticket_solution_keeps_student_confirmation_and_first_response(self):
        now=datetime.utcnow();ticket_id=self.db.execute(insert(t.service_ticket).values(ticket_no='T1',student_id=1,ticket_type='complaint',category_code='teaching',content='测试工单',priority='normal',employee_id=1,handling_department_id=1,status='assigned',response_due_at=now+timedelta(hours=24),resolution_due_at=now+timedelta(hours=72),reopen_count=0,row_version=1)).inserted_primary_key[0];self.db.commit()
        result=TicketService(self.repo).mutate('resolve',ticket_id,'ticket-resolve-1',{'content':'已提出方案','visibility':'student_visible','expected_version':1})
        self.assertEqual(result['status'],'awaiting_student');self.assertIsNone(result['closed_at']);self.assertIsNotNone(result['first_response_at'])
        self.assertEqual(self.db.scalar(select(func.count()).select_from(t.service_ticket_record)),2)
        snapshot=self.db.scalar(select(t.service_ticket_record.c.sla_snapshot).where(t.service_ticket_record.c.record_type=='sla_cycle'))
        self.assertEqual(snapshot['policy_version'],'legacy-unverified')
    def test_lease_recovery_does_not_consume_student_notifications(self):
        from app.services.enterprise.enterprise_notification import enqueue
        from app.tasks.enterprise.enterprise_tasks import publish_one
        from sqlalchemy import update
        customer=self.customer()
        for prefix in ('enterprise','student'):enqueue(self.db,event=prefix+'.customer.test',entity_type='customer_profile',entity_id=customer['customer_id'],employee_id=1,version=1,title='测试')
        self.db.execute(update(t.business_notification).where(t.business_notification.c.event_code.like('enterprise.%')).values(delivery_status='sending',lease_until=datetime.utcnow()-timedelta(seconds=1)));self.db.commit()
        self.assertTrue(publish_one(self.db));self.assertFalse(publish_one(self.db))
        states=dict(self.db.execute(select(t.business_notification.c.event_code,t.business_notification.c.delivery_status)).all())
        self.assertEqual(states['enterprise.customer.test'],'sent');self.assertEqual(states['student.customer.test'],'pending')
    def test_http_identity_validation_and_unknown_fields(self):
        from app.main import app
        def database():yield self.db
        app.dependency_overrides[get_db]=database
        app.dependency_overrides[get_current_account]=lambda:self.db.get(t.UserAccount,1)
        try:
            with TestClient(app) as client:
                response=client.post('/api/v1/enterprise/customer',headers={'Idempotency-Key':'http-create-key'},json={'full_name':'HTTP客户'})
                self.assertEqual(response.json()['code'],0,response.text)
                denied=client.post('/api/v1/enterprise/customer',headers={'Idempotency-Key':'http-create-evil'},json={'full_name':'越权','department_id':2})
                self.assertEqual(denied.json()['code'],400)
                self.assertEqual(client.get('/api/v1/enterprise/me/permissions').json()['code'],0)
        finally:app.dependency_overrides.clear()

class SQLGuardTests(unittest.TestCase):
    def test_safe_bound_query(self):
        sql,values=validate_query('SELECT c.customer_id FROM customers c WHERE c.status=:s',{'s':'status'},{'status':'new'},{'customers':['customer_id','status']})
        self.assertIn('LIMIT 100',sql);self.assertEqual(values,{'s':'new'})
    def test_rejects_exfiltration_and_parameter_creation(self):
        attacks=['SELECT * FROM customers','SELECT c.password_hash FROM customers c','SELECT customer_id FROM user_account','SELECT SLEEP(5) FROM customers','SELECT customer_id FROM customers; DELETE FROM customers','SELECT customer_id FROM customers FOR UPDATE',"SELECT customer_id FROM customers WHERE status='signed'",'WITH evil AS (SELECT * FROM user_account) SELECT * FROM evil','SELECT customer_id INTO OUTFILE \'/tmp/x\' FROM customers']
        for query in attacks:
            with self.subTest(query=query),self.assertRaises(BusinessException):validate_query(query,{}, {},{'customers':['customer_id','status']})
        with self.assertRaises(BusinessException):validate_query('SELECT customer_id FROM customers WHERE status=:s',{'s':'new_status'},{'status':'new'},{'customers':['customer_id','status']})
    def test_count_is_allowed(self):
        self.assertIn('COUNT(*)',validate_query('SELECT COUNT(*) AS total FROM customers',{}, {},{'customers':['customer_id']})[0])
    def test_join_requires_real_relation_and_rejects_or_and_subquery(self):
        relations={'customers':['customer_id'],'followups':['customer_id','followup_id']}
        safe='SELECT f.followup_id FROM customers c JOIN followups f ON c.customer_id=f.customer_id'
        self.assertIn('JOIN',validate_query(safe,{}, {},relations)[0])
        for sql in [safe+' OR c.customer_id=c.customer_id','SELECT c.customer_id FROM customers c JOIN customers b ON c.customer_id=b.customer_id','SELECT c.customer_id FROM (SELECT customer_id FROM customers) c']:
            with self.subTest(sql=sql),self.assertRaises(BusinessException):validate_query(sql,{}, {},relations)

if __name__=='__main__':unittest.main()
