"""真实MySQL固定服务验收；服务提交映射到保存点，外层事务最终整体回滚测试资料。"""
from pathlib import Path
import sys,json
from datetime import datetime,timedelta,timezone,date
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sqlalchemy import select,insert
from sqlalchemy.orm import Session
from app.database import engine
from app.config import BASE_DIR
from app.models import common as t
from app.models import enterprise as own
from app.core.enterprise.enterprise_authorization import context_for
from app.repositories.enterprise.enterprise_repository import EnterpriseRepository
from app.services.enterprise.enterprise_customer import CustomerService
from app.services.enterprise.enterprise_daily_report import DailyReportService
from app.services.enterprise.enterprise_admin import AdminService
from app.services.enterprise.enterprise_score import ScoreService
from app.services.enterprise.enterprise_ticket import TicketService
from app.services.enterprise.enterprise_knowledge import KnowledgeService
from app.services.enterprise.enterprise_education import EducationService

def main():
    tag=uuid4().hex;passed=[];cid=None
    def key(scene):return 'mysql-check-'+tag+'-'+scene
    with engine.connect() as conn:
        outer=conn.begin()
        try:
            with Session(bind=conn,join_transaction_mode='create_savepoint',expire_on_commit=False) as db:
                account=db.scalar(select(t.UserAccount).where(t.UserAccount.username=='enterprise.local'))
                assert account is not None,'本地联调账号未准备'
                r=EnterpriseRepository(db,context_for(db,account));ctx=r.ctx;now=datetime.now(timezone.utc)
                customer=CustomerService(r).mutate('create',key('customer'),{'full_name':'事务回滚验证客户','phone':'13800138000'});cid=customer['customer_id'];passed.append('customer.create')
                assert CustomerService(r).mutate('create',key('customer'),{'full_name':'事务回滚验证客户','phone':'13800138000'})==customer
                followup=CustomerService(r).followup(cid,key('followup'),{'content':'事务内验证','channel':'local','followup_at':now-timedelta(hours=1),'next_followup_at':now+timedelta(days=1)})
                CustomerService(r).followup(cid,key('schedule'),{'followup_status':'done','expected_version':1},followup['followup_id']);passed.append('followup.schedule')
                daily=DailyReportService(r).mutate('create',key('daily'),{'report_date':date(2000,1,1),'submitted_content':'仅事务回滚验证'})
                DailyReportService(r).mutate('update',key('daily-update'),{'submitted_content':'回滚验证修订','expected_version':1},daily['daily_report_id']);passed.append('daily.revision')
                sid=db.execute(insert(t.student_profile).values(student_no='CHECK'+tag[:16],full_name='事务回滚验证学生',customer_id=cid,department_id=ctx.department_id,status='active',is_archived=False)).inserted_primary_key[0]
                course='CHECK_'+tag[:16]
                for relation in ('score_editor','class_teacher'):
                    params={'student_id':sid,'employee_id':ctx.employee_id,'relation_type':relation,'is_primary':relation=='class_teacher','valid_from':now-timedelta(days=1)}
                    if relation=='score_editor':params['course_scope_code']=course
                    AdminService(r).mutate('binding','create',key(relation),params)
                edu=EducationService(r)
                edu.mutate('course','create',key('course'),{'course_code':course,'course_name':'事务回滚验证课程'})
                edu.mutate('enrollment','create',key('enrollment'),{'student_id':sid,'course_code':course,'term_code':'CHECK'})
                passed.append('course.enrollment')
                score=ScoreService(r).mutate('create',key('score'),{'student_id':sid,'course_code':course,'term_code':'CHECK','assessment_code':'EX','attempt_no':1,'score_value':80,'max_score':100})
                ScoreService(r).mutate('void',key('score-void'),{'expected_version':1,'reason':'事务验证'},score['score_id']);passed.append('score.void')
                academic=edu.mutate('academic','create',key('academic'),{'student_id':sid,'event_type':'exam','title':'事务验证考试','due_at':now+timedelta(days=1)})
                edu.mutate('academic','update',key('academic-reschedule'),{'due_at':now+timedelta(days=2),'expected_event_version':1,'reason':'事务验证'},academic['id']);passed.append('academic.reschedule')
                edu.mutate('progress','create',key('progress'),{'student_id':sid,'application_name':'事务验证申请','stage_code':'visa_process','stage_status':'pending'});passed.append('application.progress')
                kid=KnowledgeService(r).mutate('create',key('knowledge'),{'entry_code':'CHECK'+tag,'entry_type':'faq','title':'仅事务验证制度','question':'测试问题','answer':'测试答案'})['knowledge_id']
                KnowledgeService(r).mutate('publish',key('publish'),{'expected_version':1,'effective_from':now-timedelta(minutes=1)},kid);passed.append('knowledge.publish')
                ticket=db.execute(insert(t.service_ticket).values(ticket_no='CHECK'+tag[:16],student_id=sid,ticket_type='complaint',category_code='teaching',content='仅事务验证',priority='normal',employee_id=ctx.employee_id,handling_department_id=ctx.department_id,status='assigned',response_due_at=now.replace(tzinfo=None)+timedelta(hours=24),resolution_due_at=now.replace(tzinfo=None)+timedelta(hours=72))).inserted_primary_key[0]
                db.commit()
                TicketService(r).mutate('resolve',ticket,key('resolve'),{'expected_version':1,'content':'仅事务验证方案','visibility':'student_visible'});passed.append('ticket.solution_and_notification')
                assert outer.is_active,'业务提交意外结束外层事务'
        finally:outer.rollback()
    with engine.connect() as conn:assert conn.scalar(select(t.customer_profile.c.customer_id).where(t.customer_profile.c.customer_id==cid)) is None,'测试事务回滚失败'
    result={'mysql_fixed_service_checks':passed,'all_passed':True,'test_business_data_rolled_back':True}
    (BASE_DIR/'.runtime/enterprise-mysql-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
