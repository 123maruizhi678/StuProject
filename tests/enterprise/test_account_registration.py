"""管理员开户、档案状态、职位与事务边界的HTTP／数据库回归。"""
import unittest
from datetime import date,datetime
from sqlalchemy import create_engine,insert,select,update,func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from pydantic import TypeAdapter,ValidationError
from app.database import Base,get_db
from app.models import common as t
from app.core.response import BusinessException
from app.services.auth_service import hash_password,verify_password,create_access_token,authenticate
from app.services.common.account_registration import AccountRegistrationService
from app.schemas.common.account_registration import RegistrationRequest
from app.core.enterprise.enterprise_authorization import context_for
from app.repositories.enterprise.enterprise_repository import EnterpriseRepository
from app.services.enterprise.enterprise_admin import AdminService

ADAPTER=TypeAdapter(RegistrationRequest)

class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
        tables=[getattr(t,name).__table__ if name=='UserAccount' else getattr(t,name) for name in t.__all__]
        Base.metadata.create_all(self.engine,tables=tables)
        self.db=Session(self.engine)
        self.db.execute(insert(t.org_department).values(department_id=1,department_code='D1',department_name='有效部门',status='active'))
        self.db.execute(insert(t.org_department).values(department_id=2,department_code='D2',department_name='停用部门',status='disabled'))
        self.db.execute(insert(t.employee).values(employee_id=1,employee_no='E1',full_name='企业配置员工',department_id=1,position_title='企业配置管理员',login_provider='local',login_subject='employee-admin',role_codes=['employee','admin'],status='active',joined_date=date(2020,1,1)))
        for sid,archived in [(10,False),(11,True),(12,False)]:
            self.db.execute(insert(t.student_profile).values(student_id=sid,student_no='S'+str(sid),full_name='测试学生',department_id=1,status='active',is_archived=archived))
        self.db.execute(insert(t.customer_profile).values(customer_id=10,customer_no='C10',full_name='测试客户',department_id=1,source_channel='test',status='new',is_archived=False))
        self.password_hash=hash_password('test-password')
        for values in [dict(user_id=1,username='platform-admin',identity_type='admin'),dict(user_id=2,username='employee-admin',identity_type='employee',employee_id=1),dict(user_id=3,username='student-account',identity_type='student',student_id=12),dict(user_id=4,username='customer-account',identity_type='customer',customer_id=10)]:
            self.db.add(t.UserAccount(password_hash=self.password_hash,**values))
        self.db.commit();self.admin=self.db.get(t.UserAccount,1)
        from app.main import app
        self.app=app
        def database():yield self.db
        self.app.dependency_overrides[get_db]=database
        self.client=TestClient(app)
    def tearDown(self):
        self.client.close();self.app.dependency_overrides.clear();self.db.close();self.engine.dispose()
    def headers(self,user=1,key='registration-request-001'):
        return {'Authorization':'Bearer '+create_access_token(self.db.get(t.UserAccount,user))[0],'Idempotency-Key':key}
    def register(self,body,key='registration-request-001'):
        return AccountRegistrationService(self.db,self.admin).register(ADAPTER.validate_python(body),key)
    def employee_body(self,title='部门主管',username='new-manager',number='E2'):
        return {'identity_type':'employee','username':username,'profile':{'employee_no':number,'full_name':'新员工','department_id':1,'position_title':title}}
    def count(self,table):return self.db.scalar(select(func.count()).select_from(table))
    def test_employee_manager_and_default_password(self):
        result=self.register(self.employee_body())
        account=self.db.get(t.UserAccount,result['user_id'])
        self.assertTrue(verify_password('123456',account.password_hash));self.assertNotEqual(account.password_hash,'123456')
        self.assertEqual(result['role_codes'],['employee','manager'])
        self.assertIn('enterprise.ticket.assign',result['enterprise_permissions'])
        row=self.db.execute(select(t.employee).where(t.employee.c.employee_id==result['employee_id'])).mappings().one()
        self.assertEqual(row['position_title'],'部门主管');self.assertEqual(row['department_id'],1)
    def test_customer_can_be_assigned_to_highest_employee_admin(self):
        result=self.register({'identity_type':'customer','username':'admin-owned-customer','profile':{'full_name':'管理员负责客户','department_id':1,'employee_id':1}})
        row=self.db.execute(select(t.customer_profile).where(t.customer_profile.c.customer_id==result['customer_id'])).mappings().one()
        self.assertEqual(row['employee_id'],1)
    def test_four_identities_and_profile_links(self):
        admin=self.register({'identity_type':'admin','username':'second-admin'},'register-admin-key')
        student=self.register({'identity_type':'student','username':'new-student','profile':{'student_no':'S20','full_name':'新学生','department_id':1}},'register-student-key')
        customer=self.register({'identity_type':'customer','username':'new-customer','profile':{'full_name':'新客户','department_id':1}},'register-customer-key')
        self.assertIsNone(admin['employee_id']);self.assertIsNone(admin['student_id'])
        profile=self.db.execute(select(t.student_profile).where(t.student_profile.c.student_id==student['student_id'])).mappings().one()
        self.assertFalse(profile['is_archived']);self.assertEqual(profile['status'],'active')
        self.assertIn('student.profile.read_own',student['permissions']);self.assertNotIn('enterprise_permissions',student)
        self.assertIsNotNone(customer['customer_id'])
    def test_idempotent_replay_and_parameter_conflict(self):
        body=self.employee_body();first=self.register(body)
        self.assertEqual(self.register(body),first);self.assertEqual(self.count(t.employee),2)
        with self.assertRaises(BusinessException):self.register(self.employee_body(username='different'))
        self.assertEqual(self.count(t.UserAccount),5)
    def test_duplicate_number_rolls_back_everything(self):
        before=(self.count(t.UserAccount),self.count(t.employee),self.count(t.operation_log))
        with self.assertRaises(BusinessException):self.register(self.employee_body(number='E1'))
        self.assertEqual(before,(self.count(t.UserAccount),self.count(t.employee),self.count(t.operation_log)))
    def test_audit_failure_rolls_back_new_profile_and_account(self):
        from unittest.mock import patch
        execute=self.db.execute
        def fail_audit(statement,*args,**kwargs):
            if getattr(statement,'is_insert',False) and statement.table.name=='operation_log':raise RuntimeError('audit write failed')
            return execute(statement,*args,**kwargs)
        with patch.object(self.db,'execute',side_effect=fail_audit),self.assertRaises(RuntimeError):self.register(self.employee_body())
        self.assertEqual(self.count(t.employee),1);self.assertEqual(self.count(t.UserAccount),4)
    def test_archived_and_bound_students_rejected(self):
        for sid in (11,12):
            with self.subTest(sid=sid),self.assertRaises(BusinessException):self.register({'identity_type':'student','username':'s'+str(sid),'student_id':sid},'student-'+str(sid)+'-key')
        self.assertEqual(self.count(t.UserAccount),4)
    def test_existing_student_is_bound_without_duplication(self):
        first=self.register({'identity_type':'student','username':'bound-student','student_id':10})
        self.assertEqual(first['student_id'],10);self.assertEqual(self.count(t.student_profile),3)
    def test_invalid_position_and_department_rejected(self):
        with self.assertRaises(BusinessException):self.register(self.employee_body(title='假想主管助理'))
        body=self.employee_body();body['profile']['department_id']=2
        with self.assertRaises(BusinessException):self.register(body,'disabled-dept-key')
        self.assertEqual(self.count(t.employee),1)
    def test_role_and_password_cannot_be_injected(self):
        bodies=[{**self.employee_body(),'password':'custom-password'},self.employee_body()]
        bodies[1]['profile']['role_codes']=['admin']
        for body in bodies:
            with self.subTest(body_keys=list(body)),self.assertRaises(ValidationError):ADAPTER.validate_python(body)
    def test_admin_only_http_and_hidden_documentation(self):
        path='/api/v1/auth/register';body={'identity_type':'admin','username':'new-admin'}
        self.assertEqual(self.client.post(path,json=body).status_code,401)
        for user in (3,4):
            self.assertEqual(self.client.post(path,headers=self.headers(user),json=body).status_code,403)
            self.assertEqual(self.client.get('/api/v1/admin/openapi.json',headers=self.headers(user)).status_code,403)
        public=self.client.get('/openapi.json').json()
        self.assertNotIn(path,public['paths']);self.assertNotIn('AdminRegistration',public.get('components',{}).get('schemas',{}))
        private=self.client.get('/api/v1/admin/openapi.json',headers=self.headers()).json()
        self.assertEqual(self.client.get('/api/v1/admin/openapi.json',headers=self.headers(2)).status_code,200)
        created=self.client.post(path,headers=self.headers(2,'employee-admin-register'),json={'identity_type':'admin','username':'by-employee-admin'}).json()
        self.assertEqual(created['code'],0)
        self.assertIn(path,private['paths']);self.assertIn('EmployeeRegistration',private['components']['schemas'])
        response=self.client.post(path,headers=self.headers(),json=body).json()
        self.assertEqual(response['code'],0,response)
    def test_registration_schema_errors_do_not_echo_passwords(self):
        response=self.client.post('/api/v1/auth/register',headers=self.headers(),json={'identity_type':'admin','username':'bad-input','password':'do-not-echo-this'}).json()
        self.assertEqual(response['code'],400);self.assertNotIn('do-not-echo-this',str(response))
    def test_archival_revokes_login_and_existing_token(self):
        headers=self.headers(3)
        self.db.execute(update(t.student_profile).where(t.student_profile.c.student_id==12).values(is_archived=True));self.db.commit()
        self.assertEqual(self.client.get('/api/v1/auth/me/access',headers=headers).status_code,403)
        self.assertEqual(self.client.post('/api/v1/auth/login',json={'username':'student-account','password':'test-password'}).status_code,403)
    def test_role_change_during_request_is_rechecked(self):
        service=AccountRegistrationService(self.db,self.admin)
        self.db.execute(update(t.UserAccount).where(t.UserAccount.user_id==1).values(identity_type='employee',employee_id=2))
        self.db.execute(insert(t.employee).values(employee_id=2,employee_no='E2',full_name='原管理员',department_id=1,login_provider='local',login_subject='old-admin',role_codes=['employee'],status='active',joined_date=date(2020,1,1)))
        self.db.commit()
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):service.register(ADAPTER.validate_python({'identity_type':'admin','username':'not-created'}),'fresh-admin-check')
        self.assertEqual(self.count(t.UserAccount),4)
    def test_position_change_updates_roles_and_blocks_self_change(self):
        new=self.register(self.employee_body(title='普通员工'))
        repo=EnterpriseRepository(self.db,context_for(self.db,self.db.get(t.UserAccount,2)))
        result=AdminService(repo).mutate('employee','update','position-update-key',{'position_title':'教务专员','expected_version':1},new['employee_id'])
        self.assertEqual(result['role_codes'],['employee','academic'])
        with self.assertRaises(BusinessException):AdminService(repo).mutate('employee','update','self-position-key',{'position_title':'部门主管','expected_version':1},1)
        with self.assertRaises(BusinessException):AdminService(repo).mutate('employee','roles','conflicting-role-key',{'role_codes':['employee','manager'],'expected_version':2,'reason':'测试冲突'},new['employee_id'])
    def test_audit_contains_operator_but_no_password(self):
        self.register(self.employee_body())
        row=self.db.execute(select(t.operation_log)).mappings().one()
        self.assertEqual(row['after_data']['operator_user_id'],1)
        self.assertNotIn('123456',str(row['after_data']));self.assertNotIn('password_hash',str(row['result_reference']))

if __name__=='__main__':unittest.main()
