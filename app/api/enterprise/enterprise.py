"""企业HTTP接口；静态操作先注册，每个方法路径只装配一次。"""
from datetime import datetime
from fastapi import APIRouter,Depends,Header,Query,Request,UploadFile,File
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select,func,and_
from app.database import get_db
from app.core.response import success
from app.core.enterprise.enterprise_authorization import current_employee,error,scope,valid_binding
from app.repositories.enterprise.enterprise_repository import EnterpriseRepository,RESOURCES,public,project,digest
from app.schemas.enterprise import enterprise as s
from app.services.enterprise.enterprise_customer import CustomerService
from app.services.enterprise.enterprise_daily_report import DailyReportService
from app.services.enterprise.enterprise_score import ScoreService
from app.services.enterprise.enterprise_ticket import TicketService
from app.services.enterprise.enterprise_admin import AdminService
from app.services.enterprise.enterprise_education import EducationService
from app.services.enterprise.enterprise_knowledge import KnowledgeService
from app.services.enterprise.enterprise_command import CommandService
from app.services.enterprise.enterprise_notification import mark_read
from app.models import common as t
from app.models.enterprise import customer_followup,employee_daily_report

router=APIRouter(prefix='/enterprise',tags=['企业管理'])
def repo(db,ctx):return EnterpriseRepository(db,ctx)
def oid(request):
    value=next(iter(request.path_params.values()),None)
    try:
        value=int(value)
        if value<=0 or value>9223372036854775807:raise ValueError()
        return value
    except (TypeError,ValueError):error(400,'对象ID须为正整数')
def respond(data):return success(jsonable_encoder(data))

@router.get('/me/permissions')
def permissions(ctx=Depends(current_employee)):
    return respond({'user_id':ctx.user_id,'identity_type':ctx.identity_type,'is_admin':ctx.is_admin,'employee_id':ctx.employee_id,'department_id':ctx.department_id,'roles':sorted(ctx.roles),'permissions':ctx.permissions()})

@router.post('/command')
def command(payload:s.TextRequest,db=Depends(get_db),ctx=Depends(current_employee),key:str=Header(alias='Idempotency-Key')):
    return respond(CommandService(repo(db,ctx)).preview(payload.text,key))
@router.post('/command/confirm')
def confirm(payload:s.ConfirmRequest,db=Depends(get_db),ctx=Depends(current_employee),key:str=Header(alias='Idempotency-Key')):
    return respond(CommandService(repo(db,ctx)).confirm(key,payload.model_dump()))
@router.post('/onboarding/ask')
def ask(payload:s.KnowledgeQuestion,db=Depends(get_db),ctx=Depends(current_employee)):
    return respond(KnowledgeService(repo(db,ctx)).ask(payload.question))
@router.post('/nl2sql')
def query(payload:s.QueryRequest,db=Depends(get_db),ctx=Depends(current_employee)):
    from app.services.enterprise.enterprise_nl2sql import run_query
    return respond(run_query(repo(db,ctx),payload.question,payload.filters))
@router.post('/voice/transcribe')
async def transcribe(file:UploadFile=File(...),ctx=Depends(current_employee)):
    ctx.require('command')
    from app.clients.enterprise.enterprise_asr import transcribe_audio
    from starlette.concurrency import run_in_threadpool
    content=await file.read(20*1024*1024+1)
    return respond(await run_in_threadpool(transcribe_audio,content,file.filename or 'audio'))
@router.post('/daily-report/summary')
def summarize(payload:s.SummaryRequest,db=Depends(get_db),ctx=Depends(current_employee),key:str=Header(alias='Idempotency-Key')):
    r=repo(db,ctx);ctx.require('daily.write_own');row=r.one('daily',payload.report_id)
    if (row['employee_id']!=ctx.employee_id and not ctx.is_admin) or row['status']!='submitted':error(403,'只能摘要本人已提交日报，管理员可维护全局日报')
    action='enterprise.daily.write_own';params={'verb':'summary','id':payload.report_id}
    old=db.execute(select(t.operation_log).where(t.operation_log.c.operation_key==digest([ctx.user_id,action,key]))).mappings().first()
    if old:
        if old['parameters_hash']!=digest(params):error(409,'同键参数不一致')
        if old['operation_status']!='succeeded':error(409,'摘要仍在处理中')
        return respond(old['result_reference'])
    db.rollback()
    from app.clients.enterprise.enterprise_dify import EnterpriseDifyClient
    result=EnterpriseDifyClient().run('summary',{'content':row['submitted_content'],'report_date':str(row['report_date']),'contract_version':'enterprise-v1'},ctx.user_id)
    if not isinstance(result.get('summary'),str) or not result['summary'].strip():error(503,'摘要输出无效')
    def work():
        fresh=r.one('daily',payload.report_id,lock=True)
        if (fresh['employee_id']!=r.ctx.employee_id and not r.ctx.is_admin) or fresh['status']!='submitted':error(403,'日报已不可摘要')
        updated=r.version_update('daily',fresh,row['row_version'],{'ai_summary':result['summary']})
        return public(updated),fresh,'employee_daily_report',payload.report_id
    return respond(r.operation(action,key,params,work,lambda:r.one('daily',payload.report_id)))

@router.post('/customer/phone-candidates')
def phone_candidates(payload:s.PhoneCandidates,db=Depends(get_db),ctx=Depends(current_employee)):
    ctx.require('customer.read')
    from app.core.common.phone_protection import phone_fields
    token=phone_fields(payload.phone)['phone_lookup_token']
    result=repo(db,ctx).page('customer',10,0,extra=t.customer_profile.c.phone_lookup_token==token)
    return respond({'items':[{'customer_id':r['customer_id'],'full_name':r['full_name']} for r in result['items']],'total':result['total'],'auto_merge':False})
@router.get('/organization')
def organization(tree:bool=False,db=Depends(get_db),ctx=Depends(current_employee)):
    ctx.require('organization.read')
    rows=[public(r) for r in db.execute(select(t.org_department).where(t.org_department.c.status=='active')).mappings()]
    if not tree:return respond(rows)
    nodes={r['department_id']:{**r,'children':[]} for r in rows};roots=[]
    for item in nodes.values():
        parent=nodes.get(item['parent_department_id'])
        if parent is None:roots.append(item)
        else:parent['children'].append(item)
    return respond({'items':rows,'tree':roots,'total':len(rows)})
@router.get('/todos')
def todos(db=Depends(get_db),ctx=Depends(current_employee)):
    ctx.require('todo.read_own');now=datetime.utcnow();items=[]
    if ctx.can('customer.read'):
        for row in db.execute(select(customer_followup).where(scope(ctx,'followup',customer_followup),customer_followup.c.followup_status=='pending',customer_followup.c.next_followup_at<=now).limit(100)).mappings():
            items.append({'type':'followup','id':row['followup_id'],'title':'客户跟进到期','due_at':row['next_followup_at']})
    if ctx.can('ticket.read'):
        for row in db.execute(select(t.service_ticket).where(scope(ctx,'ticket',t.service_ticket),t.service_ticket.c.status!='closed').limit(100)).mappings():
            items.append({'type':'ticket','id':row['ticket_id'],'title':'工单待处理','due_at':row['resolution_due_at']})
    if 'teacher' in ctx.roles or ctx.is_admin:
        l=t.student_admin_service
        conditions=[] if ctx.is_admin else [l.c.reviewer_id==ctx.employee_id,valid_binding(ctx,['class_teacher'],l.c.student_id)]
        for row in db.execute(select(l).where(l.c.apply_type=='leave',l.c.approval_status=='pending',*conditions).limit(100)).mappings():
            items.append({'type':'leave','id':row['id'],'title':'学生请假待审批','collaboration':'student_service_required'})
    return respond({'items':items,'total':len(items)})
@router.post('/notifications/{notification_id}/read')
def read_notification(notification_id:int,db=Depends(get_db),ctx=Depends(current_employee)):
    return respond(mark_read(repo(db,ctx),notification_id))

READS=[('customer','customer','customer_id','customer.read'),('daily-report','daily','report_id','daily.read'),('students','student','student_id','student.read'),('scores','score','score_id','score.read'),('tickets','ticket','ticket_id','ticket.read'),('knowledge','knowledge','knowledge_id','knowledge.read'),('notifications','notification','notification_id','notification.read_own'),('employees','employee','employee_id','organization.read'),('operation-logs','audit','operation_log_id','audit.read'),('student-bindings','binding','binding_id','binding.manage')]
READS += [('courses','course','course_id','score.read'),('student-courses','enrollment','enrollment_id','score.read'),('academic-events','academic','event_id','student.read'),('application-progress','progress','progress_id','customer.read')]
def reader(resource,permission,detail):
    def endpoint(request:Request,limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0),unread_only:bool=False,manage:bool=False,db=Depends(get_db),ctx=Depends(current_employee)):
        ctx.require(permission);r=repo(db,ctx)
        if detail:
            row=KnowledgeService(r).manage_row(oid(request)) if resource=='knowledge' and ctx.can('knowledge.manage') else r.one(resource,oid(request))
            if resource=='ticket':
                records=db.execute(select(t.service_ticket_record).where(t.service_ticket_record.c.ticket_id==row['ticket_id']).order_by(t.service_ticket_record.c.created_at,t.service_ticket_record.c.ticket_record_id)).mappings()
                row['records']=[public(record) for record in records]
            return respond(project(resource,row))
        if manage and resource=='knowledge':
            ctx.require('knowledge.manage');table,pk=RESOURCES[resource]
            rows=db.execute(select(table).order_by(table.c[pk].desc()).limit(limit).offset(offset)).mappings()
            return respond({'items':[public(x) for x in rows],'total':db.scalar(select(func.count()).select_from(table)),'limit':limit,'offset':offset})
        extra=None
        if resource=='notification' and unread_only:extra=t.business_notification.c.read_at.is_(None)
        result=r.page(resource,limit,offset,extra=extra)
        if resource=='notification':result['unread_count']=db.scalar(select(func.count()).select_from(t.business_notification).where(scope(ctx,'notification',t.business_notification),t.business_notification.c.read_at.is_(None)))
        return respond(result)
    return endpoint
for path,resource,param,permission in READS:
    router.add_api_route('/'+path,reader(resource,permission,False),methods=['GET'],name=resource+'_list')
    if resource not in ('audit','binding'):router.add_api_route('/'+path+'/{'+param+'}',reader(resource,permission,True),methods=['GET'],name=resource+'_detail')

def mutation(resource,verb,model):
    def endpoint(request:Request,payload,db=Depends(get_db),ctx=Depends(current_employee),key:str=Header(alias='Idempotency-Key')):
        r=repo(db,ctx);params=payload.model_dump(exclude_unset=True);object_id=oid(request) if request.path_params else None
        if resource=='customer':result=CustomerService(r).mutate(verb,key,params,object_id)
        elif resource=='daily':result=DailyReportService(r).mutate(verb,key,params,object_id)
        elif resource=='score':result=ScoreService(r).mutate(verb,key,params,object_id)
        elif resource=='ticket':result=TicketService(r).mutate(verb,object_id,key,params)
        elif resource=='knowledge':result=KnowledgeService(r).mutate(verb,key,params,object_id)
        elif resource in ('course','enrollment','academic','progress'):result=EducationService(r).mutate(resource,verb,key,params,object_id)
        else:result=AdminService(r).mutate(resource,verb,key,params,object_id)
        return respond(result)
    endpoint.__annotations__['payload']=model
    return endpoint

MUTATIONS=[
 ('POST','/customer','customer','create',s.CustomerCreate),('PUT','/customer/{customer_id}','customer','update',s.CustomerUpdate),('PUT','/customer/{customer_id}/status','customer','status',s.StatusUpdate),('DELETE','/customer/{customer_id}','customer','archive',s.Mutation),('POST','/customer/{customer_id}/assign','customer','assign',s.Assignment),
 ('POST','/daily-report','daily','create',s.DailyCreate),('PUT','/daily-report/{report_id}','daily','update',s.DailyUpdate),('DELETE','/daily-report/{report_id}','daily','void',s.Mutation),
 ('POST','/scores','score','create',s.ScoreCreate),('PUT','/scores/{score_id}','score','update',s.ScoreUpdate),('DELETE','/scores/{score_id}','score','void',s.Mutation),
 ('POST','/tickets/{ticket_id}/assign','ticket','assign',s.Assignment),('POST','/tickets/{ticket_id}/followups','ticket','followup',s.TicketRecord),('POST','/tickets/{ticket_id}/resolve','ticket','resolve',s.TicketRecord),
 ('POST','/departments','department','create',s.DepartmentCreate),('PUT','/departments/{department_id}','department','update',s.DepartmentUpdate),('DELETE','/departments/{department_id}','department','disable',s.Mutation),
 ('POST','/employees','employee','create',s.EmployeeCreate),('PUT','/employees/{employee_id}','employee','update',s.EmployeeUpdate),('PUT','/employees/{employee_id}/roles','employee','roles',s.RoleUpdate),
 ('POST','/student-bindings','binding','create',s.BindingCreate),('PUT','/student-bindings/{binding_id}','binding','update',s.BindingUpdate),('DELETE','/student-bindings/{binding_id}','binding','disable',s.Mutation),
 ('POST','/knowledge','knowledge','create',s.KnowledgeCreate),('PUT','/knowledge/{knowledge_id}','knowledge','update',s.KnowledgeUpdate),('DELETE','/knowledge/{knowledge_id}','knowledge','disable',s.Mutation),('POST','/knowledge/{knowledge_id}/publish','knowledge','publish',s.KnowledgePublish)]
MUTATIONS += [
 ('POST','/courses','course','create',s.CourseCreate),('PUT','/courses/{course_id}','course','update',s.CourseUpdate),
 ('POST','/student-courses','enrollment','create',s.EnrollmentCreate),('PUT','/student-courses/{enrollment_id}','enrollment','update',s.EnrollmentUpdate),
 ('POST','/academic-events','academic','create',s.AcademicCreate),('PUT','/academic-events/{event_id}','academic','update',s.AcademicUpdate),
 ('POST','/application-progress','progress','create',s.ProgressCreate),('PUT','/application-progress/{progress_id}','progress','update',s.ProgressUpdate)]
for method,path,resource,verb,model in MUTATIONS:router.add_api_route(path,mutation(resource,verb,model),methods=[method],name=resource+'_'+verb)

@router.get('/customer/{customer_id}/followups')
def followups(customer_id:int,limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0),db=Depends(get_db),ctx=Depends(current_employee)):
    ctx.require('customer.read');r=repo(db,ctx);r.one('customer',customer_id)
    return respond(r.page('followup',limit,offset,extra=customer_followup.c.customer_id==customer_id))
@router.post('/customer/{customer_id}/followups')
def add_followup(customer_id:int,payload:s.FollowupCreate,db=Depends(get_db),ctx=Depends(current_employee),key:str=Header(alias='Idempotency-Key')):
    return respond(CustomerService(repo(db,ctx)).followup(customer_id,key,payload.model_dump(exclude_unset=True)))
@router.put('/customer/{customer_id}/followups/{followup_id}/schedule')
def schedule(customer_id:int,followup_id:int,payload:s.ScheduleUpdate,db=Depends(get_db),ctx=Depends(current_employee),key:str=Header(alias='Idempotency-Key')):
    return respond(CustomerService(repo(db,ctx)).followup(customer_id,key,payload.model_dump(exclude_unset=True),followup_id))
