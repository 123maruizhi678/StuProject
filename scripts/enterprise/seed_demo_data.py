"""初始化少量企业接口测试资料；仅本地库、整体事务、固定标识可重复执行。"""
from pathlib import Path
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select,insert,update,func
from sqlalchemy.orm import Session
from app.config import BASE_DIR,settings
from app.database import engine
from app.models import common as t
from app.models import enterprise as own
from app.core.enterprise.enterprise_authorization import context_for
from app.repositories.enterprise.enterprise_repository import EnterpriseRepository,digest
from app.services.enterprise.enterprise_customer import CustomerService
from app.services.enterprise.enterprise_daily_report import DailyReportService
from app.services.enterprise.enterprise_admin import AdminService
from app.services.enterprise.enterprise_education import EducationService
from app.services.enterprise.enterprise_score import ScoreService
from app.services.enterprise.enterprise_knowledge import KnowledgeService
from app.services.enterprise.enterprise_ticket import TicketService
from app.services.enterprise.enterprise_ticket_policy import new_cycle_snapshot
from app.services.enterprise.enterprise_notification import enqueue
from app.tasks.enterprise.enterprise_tasks import scan,publish_one

VERSION='enterprise-demo-v1'
MARKER=digest([VERSION,settings.DB_NAME])
TABLES={
    'customers':(t.customer_profile,'customer_id'),
    'students':(t.student_profile,'student_id'),
    'followups':(own.customer_followup,'followup_id'),
    'daily_reports':(own.employee_daily_report,'daily_report_id'),
    'courses':(own.enterprise_course,'course_id'),
    'enrollments':(own.enterprise_student_course,'enrollment_id'),
    'scores':(t.student_score,'score_id'),
    'bindings':(t.student_staff_binding,'binding_id'),
    'academic_events':(t.student_academic_event,'id'),
    'academic_reminders':(t.student_academic_reminder,'id'),
    'application_progress':(t.student_application_progress,'id'),
    'tickets':(t.service_ticket,'ticket_id'),
    'knowledge':(own.knowledge_entry,'knowledge_id'),
}

def key(scene):return VERSION+':'+scene

def snapshot(db,ids):
    result={}
    for group,values in ids.items():
        table,pk=TABLES[group]
        columns=[table.c[pk]]+[table.c[name] for name in ('full_name','student_no','course_code','course_name','title','report_date','status','followup_status','event_status','event_version','row_version','student_id','customer_id','employee_id','ticket_no','stage_code','stage_status') if name in table.c and name!=pk]
        result[group]=[dict(row) for row in db.execute(select(*columns).where(table.c[pk].in_(values)).order_by(table.c[pk])).mappings()]
    return jsonable_encoder(result)

def seed():
    if settings.DB_HOST not in ('localhost','127.0.0.1','::1') or settings.DB_NAME!='education_agent':
        raise RuntimeError('此脚本仅允许本机education_agent，不允许猜测其他目标库')
    with engine.connect() as conn:
        outer=conn.begin()
        try:
            with Session(bind=conn,join_transaction_mode='create_savepoint',expire_on_commit=False) as db:
                previous=db.execute(select(t.operation_log).where(t.operation_log.c.operation_key==MARKER)).mappings().first()
                if previous:
                    if previous['operation_status']!='succeeded':raise RuntimeError('测试资料初始化状态未完成，请先检查')
                    result=previous['result_reference']
                    outer.rollback()
                    return result,False
                # 首次只给空业务库初始化，不覆盖后来录入的真实资料。
                for group in ('customers','students','daily_reports','courses','tickets','knowledge'):
                    table,_=TABLES[group]
                    if db.scalar(select(func.count()).select_from(table)):
                        raise RuntimeError(table.name+'已有资料；停止自动初始化，保留现有数据')
                account=db.scalar(select(t.UserAccount).where(t.UserAccount.username=='enterprise.local'))
                if account is None:raise RuntimeError('已有本地联调账号未找到；脚本不会另建账号')
                ctx=context_for(db,account);r=EnterpriseRepository(db,ctx)
                for action in ('customer.create','binding.manage','academic.write','score.write','progress.write','knowledge.manage','knowledge.publish','ticket.handle'):
                    ctx.require(action)
                now=datetime.now(timezone.utc).replace(microsecond=0)
                naive=now.replace(tzinfo=None)
                today=now.astimezone(ZoneInfo('Asia/Shanghai')).date()
                db.execute(insert(t.operation_log).values(operation_key=MARKER,employee_id=ctx.employee_id,action_code='enterprise.demo.seed',entity_type='enterprise_demo',request_key=VERSION,parameters_hash=digest({'version':VERSION}),operation_status='processing',row_version=1))
                ids={group:[] for group in TABLES}
                def remember(group,row):
                    rid=row[TABLES[group][1]];ids[group].append(rid);return rid

                customers=CustomerService(r)
                for i,status in enumerate(('new','signed','signed'),1):
                    row=customers.mutate('create',key('customer-'+str(i)),{'full_name':'接口测试客户'+str(i),'education_level':'本科','target_country_code':'GB'})
                    cid=remember('customers',row)
                    if status!='new':customers.mutate('status',key('customer-status-'+str(i)),{'status':status,'expected_version':row['row_version']},cid)
                    followup=customers.followup(cid,key('followup-'+str(i)),{'content':'【接口测试】模拟咨询和资料沟通，不代表真实客户联系。','channel':'online','followup_at':now-timedelta(hours=3),'next_followup_at':now-timedelta(hours=2) if i==1 else now+timedelta(days=i)})
                    fid=remember('followups',followup)
                    if i==2:customers.followup(cid,key('followup-complete-2'),{'followup_status':'done','expected_version':followup['row_version'],'reason':'【接口测试】模拟已完成'},fid)

                for i,cid in enumerate(ids['customers'][1:],1):
                    sid=db.execute(insert(t.student_profile).values(student_no='DEMO_STU_00'+str(i),full_name='接口测试学生'+str(i),customer_id=cid,department_id=ctx.department_id,status='active',is_archived=False)).inserted_primary_key[0]
                    ids['students'].append(sid)
                    remember('bindings',AdminService(r).mutate('binding','create',key('class-teacher-'+str(i)),{'student_id':sid,'employee_id':ctx.employee_id,'relation_type':'class_teacher','is_primary':True,'valid_from':now-timedelta(days=1)}))
                edu=EducationService(r)
                course_codes=('DEMO_ENGLISH','DEMO_MATH')
                for course,name in zip(course_codes,('接口测试英语课程','接口测试数学课程')):
                    remember('courses',edu.mutate('course','create',key(course),{'course_code':course,'course_name':name}))
                for i,sid in enumerate(ids['students'],1):
                    for j,course in enumerate(course_codes,1):
                        remember('bindings',AdminService(r).mutate('binding','create',key(f'score-binding-{i}-{j}'),{'student_id':sid,'employee_id':ctx.employee_id,'relation_type':'score_editor','course_scope_code':course,'is_primary':False,'valid_from':now-timedelta(days=1)}))
                        remember('enrollments',edu.mutate('enrollment','create',key(f'enrollment-{i}-{j}'),{'student_id':sid,'course_code':course,'term_code':'2026-FALL'}))
                        remember('scores',ScoreService(r).mutate('create',key(f'score-{i}-{j}'),{'student_id':sid,'course_code':course,'term_code':'2026-FALL','assessment_code':'DEMO_MIDTERM','attempt_no':1,'score_value':90-i*3+j,'max_score':100}))
                    event=edu.mutate('academic','create',key('event-'+str(i)),{'student_id':sid,'event_type':'exam' if i==1 else 'ddl','title':'【接口测试】模拟考试' if i==1 else '【接口测试】模拟材料截止','due_at':now+timedelta(days=2 if i==1 else 7)})
                    eid=remember('academic_events',event)
                    for lead in (60,1440):
                        reminder=db.execute(insert(t.student_academic_reminder).values(student_id=sid,academic_event_id=eid,lead_minutes=lead,notify_at=now.replace(tzinfo=None)+timedelta(days=2 if i==1 else 7)-timedelta(minutes=lead),event_version=event['event_version'],status='pending',updated_at=naive)).inserted_primary_key[0]
                        ids['academic_reminders'].append(reminder)
                    remember('application_progress',edu.mutate('progress','create',key('progress-'+str(i)),{'student_id':sid,'application_name':'【接口测试】模拟院校申请'+str(i),'stage_code':'document_review' if i==1 else 'school_application','stage_status':'in_progress' if i==1 else 'pending','detail':'仅用于接口验证，不代表真实申请进展。'}))
                for days in (1,2):
                    remember('daily_reports',DailyReportService(r).mutate('create',key('daily-'+str(days)),{'report_date':today-timedelta(days=days),'submitted_content':'【接口测试日报】完成模拟客户沟通及资料核对；下一步验证成绩、学业节点与工单接口。此记录为测试样例。'}))

                knowledge=KnowledgeService(r)
                entries=[{'entry_code':'DEMO_FAQ_001','entry_type':'faq','title':'【接口测试】测试签到时间','question':'接口测试签到时间是什么？','answer':'仅供接口测试：测试签到时间为上午九点，不代表正式制度。'},
                    {'entry_code':'DEMO_DOC_001','entry_type':'document','title':'【接口测试】测试资料提交流程','content_text':'仅供接口测试的模拟流程：第一步收集测试资料；第二步核对资料；第三步提交审核。本内容不代表实际业务制度。','source_reference':'本地接口测试样例，非正式制度'}]
                for i,entry in enumerate(entries,1):
                    row=knowledge.mutate('create',key('knowledge-'+str(i)),entry);kid=remember('knowledge',row)
                    knowledge.mutate('publish',key('knowledge-publish-'+str(i)),{'expected_version':row['row_version'],'effective_from':now-timedelta(minutes=1)},kid)

                scenarios=[('DEMO_TICKET_001','assigned','complaint','normal',2),('DEMO_TICKET_002','open','complaint','high',6),('DEMO_TICKET_003','assigned','suggestion','normal',3)]
                for i,(number,status,kind,priority,hours) in enumerate(scenarios,1):
                    start=naive-timedelta(hours=hours)
                    values={'ticket_no':number,'student_id':ids['students'][(i-1)%2],'ticket_type':kind,'category_code':'teaching','content':'【接口测试】模拟教学反馈'+str(i)+'，不对应真实投诉。','priority':priority,'employee_id':None if status=='open' else ctx.employee_id,'handling_department_id':ctx.department_id,'status':status,'reopen_count':0,'row_version':1,'created_at':start,'updated_at':start}
                    frozen=new_cycle_snapshot(values,start)
                    values['response_due_at']=datetime.fromisoformat(frozen['response_due_at'])
                    values['resolution_due_at']=datetime.fromisoformat(frozen['resolution_due_at'])
                    tid=db.execute(insert(t.service_ticket).values(**values)).inserted_primary_key[0];ids['tickets'].append(tid)
                    db.execute(insert(t.service_ticket_record).values(ticket_id=tid,record_type='sla_cycle',service_code='enterprise.demo.seed',content='【接口测试】模拟工单创建及连续自然小时策略快照',visibility='internal',to_status=status,cycle_no=1,record_key=key(number),sla_snapshot=frozen,created_at=start))
                    if i==1:enqueue(db,event='enterprise.ticket.assigned',entity_type='service_ticket',entity_id=tid,employee_id=ctx.employee_id,version=1,title='【接口测试】收到模拟工单分派')
                    if i==3:TicketService(r).mutate('resolve',tid,key('ticket-solution-3'),{'expected_version':1,'content':'【接口测试】已提出模拟处理方案，等待学生确认。','visibility':'student_visible'})

                result={'version':VERSION,'database':settings.DB_NAME,'created_at_beijing':now.astimezone(ZoneInfo('Asia/Shanghai')).isoformat(),'login_username':'enterprise.local','employee_id':ctx.employee_id,'department_id':ctx.department_id,'records':snapshot(db,ids),'counts':{group:len(values) for group,values in ids.items()}}
                db.execute(update(t.operation_log).where(t.operation_log.c.operation_key==MARKER).values(operation_status='succeeded',after_data=result,result_reference=result,finished_at=naive))
                db.commit()
                if not outer.is_active:raise RuntimeError('外层事务意外结束')
            outer.commit()
            return result,True
        except Exception:
            if outer.is_active:outer.rollback()
            raise

def export(result):
    folder=BASE_DIR/'.runtime';folder.mkdir(exist_ok=True)
    (folder/'enterprise-demo-data.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    records=result['records'];customer=records['customers'][0];score=records['scores'][0];event=records['academic_events'][0];ticket=records['tickets'][0]
    doc=['# 企业管理模块接口测试数据','',f"初始化时间（北京时间）：{result['created_at_beijing']}。目标库：`{result['database']}`。",'',
         '全部样例带“接口测试”或DEMO标识，供本机接口功能验证。未创建新账号，也未修改原账号角色。使用现有`enterprise.local`登录，密码见根目录`.runtime/enterprise-login.json`；不要将该凭据提交到Git。','',
         '## 数据清单','','| 数据组 | 条数 | 实际主键ID |','| --- | --- | --- |']
    names={'customers':'客户','students':'学生','followups':'客户跟进','daily_reports':'日报','courses':'课程','enrollments':'学生选课','scores':'成绩','bindings':'学生员工关系','academic_events':'学业节点','academic_reminders':'学业提醒','application_progress':'申请进度','tickets':'工单','knowledge':'已发布测试知识'}
    for group,rows in records.items():doc.append('| '+names[group]+' | '+str(len(rows))+' | '+', '.join(str(row[TABLES[group][1]]) for row in rows)+' |')
    doc+=['','工作台：http://127.0.0.1:8000/enterprise 。Swagger：http://127.0.0.1:8000/docs 。', '',
          f"本组资料归属部门`{result['department_id']}`、员工`{result['employee_id']}`。已为两名样例学生绑定该员工的班主任和两门课程score_editor关系，因此现有联调账号可访问样例学生、成绩并办理样例工单。",'',
          '样例覆盖：新客户和已签约客户；到期待跟进、已完成和未来跟进；两份历史日报；两名学生及两门课程、四笔成绩；考试／DDL及提醒；两条申请进度；待分派、已分派和待学生确认三种工单状态。第二个工单的首次回应已超时，可测试督办。测试知识分别为FAQ和文档，均明确标注不代表正式制度。','',
          '## 请求示例','','先调用`POST /api/v1/auth/login`登录，再在Swagger的Authorize中填写返回的Bearer Token。业务更新使用本次新生成的8—128位可见ASCII幂等键；同一请求重试保持原键，变更请求内容时换新键。','',
          '以下ID和版本是初始化快照；执行过更新后，先GET详情读取最新版本再继续。业务错误也可能返回HTTP200，应检查JSON的code字段。','',
          f"1. 客户详情：`GET /api/v1/enterprise/customer/{customer['customer_id']}`。更新：`PUT /api/v1/enterprise/customer/{customer['customer_id']}`，请求体：",'',
          '```json',json.dumps({'full_name':'接口测试客户1_已修改','expected_version':customer['row_version']},ensure_ascii=False,indent=2),'```','',
          f"2. 成绩更正：`PUT /api/v1/enterprise/scores/{score['score_id']}`，请求体：",'',
          '```json',json.dumps({'score_value':95,'max_score':100,'reason':'接口测试：模拟成绩更正','expected_version':score['row_version']},ensure_ascii=False,indent=2),'```','',
          f"3. 学业节点：`GET /api/v1/enterprise/academic-events/{event['id']}`。用`PUT`修改时传`expected_event_version`（初始{event['event_version']}）、带时区的due_at及reason，可查看student_academic_reminder中的提醒同步重排。",'',
          f"4. 工单回应：`POST /api/v1/enterprise/tickets/{ticket['ticket_id']}/followups`，请求体：",'',
          '```json',json.dumps({'content':'接口测试：老师已查看反馈，正在跟进。','visibility':'student_visible','expected_version':ticket['row_version']},ensure_ascii=False,indent=2),'```','',
          '5. 日报摘要：`POST /api/v1/enterprise/daily-report/summary`，传`{"report_id":'+str(records['daily_reports'][0]['daily_report_id'])+'}`，并提供幂等键。','',
          '6. 知识问答：`POST /api/v1/enterprise/onboarding/ask`，传`{"question":"接口测试签到时间是什么？"}`或`{"question":"测试资料提交流程是什么？"}`。','',
          '7. 查询与待办：`GET /api/v1/enterprise/todos`、`GET /api/v1/enterprise/notifications`；自然语言查询：`POST /api/v1/enterprise/nl2sql`，传`{"question":"统计我有权限查看的客户总数","filters":{}}`。','',
          '## 重复执行','','`python -X utf8 scripts/enterprise/seed_demo_data.py --apply`使用固定初始化标记，成功后重复执行仅导出原清单，不追加重复资料，不重置你已修改的业务记录；若已有其他业务资料且没有初始化标记，则停止而不覆盖。初始化写入位于外层事务内，失败整体回滚。','',
          '企业通知通过现有扫描及发布器处理，工单的student前缀消息保留给学生模块消费。本次不创建学生登录账号，不改动其他模块数据。']
    (BASE_DIR/'开发文档/企业管理模块_接口测试数据.md').write_text('\n'.join(doc)+'\n',encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    if not args.apply:
        print('仅预览：将初始化3客户、2学生、2课程、4成绩、3工单等关联样例；添加--apply执行。');return
    result,created=seed()
    with Session(engine) as db:
        scan(db)
        for _ in range(100):
            if not publish_one(db):break
    export(result)
    print(json.dumps({'database':result['database'],'newly_created':created,'counts':result['counts'],'test_guide':'开发文档/企业管理模块_接口测试数据.md'},ensure_ascii=False))
if __name__=='__main__':main()
