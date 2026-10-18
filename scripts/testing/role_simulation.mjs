/** Multi-role normal operation: every business mutation is submitted through the real frontend. */
import { chromium } from '@playwright/test';
import { mkdir,readFile,writeFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import assert from 'node:assert/strict';

const dir='.runtime/role-simulation';await mkdir(dir,{recursive:true});
const resume=process.argv.includes('--resume');
const state=resume?JSON.parse(await readFile(dir+'/run.json','utf8')):{run_id:'sim_'+Date.now(),started_at:new Date().toISOString(),accounts:{},ids:{},receipts:{},scenarios:[],calls:[],errors:[]};
const base=process.env.SYSTEM_BASE_URL||'http://127.0.0.1',run=state.run_id,ids=state.ids;
const save=()=>writeFile(dir+'/run.json',JSON.stringify(state,null,2));
const browser=await chromium.launch({channel:'msedge',headless:true});
const actors=new Map();let currentStep='';
const e='/api/v1/enterprise/',s='/api/v1/student/',i='/api/v1/internal/student/';
const now=Date.now(),date=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(now);
const localTime=offset=>new Date(now+offset+8*3600000).toISOString().slice(0,19);

async function step(name,work){
  currentStep=name;
  const previous=state.scenarios.find(x=>x.name===name);
  if(resume&&previous?.status==='passed'){console.log('REUSED',name);return;}
  if(previous)state.scenarios.splice(state.scenarios.indexOf(previous),1);
  const before=state.calls.length;
  try{await work();state.scenarios.push({name,status:'passed',requests:state.calls.length-before});console.log('PASS',name);}
  catch(error){
    const status=error.skip?'skipped':'failed';
    const entry={name,status,reason:error.message,requests:state.calls.length-before};state.scenarios.push(entry);console.log(status.toUpperCase(),name,error.message);
    for(const [role,a] of actors)if(a.page&&!a.page.isClosed()){
      await a.page.screenshot({path:dir+'/failure-'+name.replace(/[^a-z0-9]+/gi,'-')+'-'+role+'.png'}).catch(()=>{});
    }
  }
  await save();
}
function requireIds(...names){for(const name of names)if(!ids[name]){const error=new Error('前置业务尚未完成：'+name);error.skip=true;throw error;}}
function skip(reason){const error=new Error(reason);error.skip=true;throw error;}
async function actor(role){
  if(actors.has(role))return actors.get(role);
  const account=role==='root'?{username:'root',password:'root'}:state.accounts[role];
  if(!account)skip('尚未创建角色 '+role);
  const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();page.setDefaultTimeout(10000);
  page.on('pageerror',error=>state.errors.push({role,url:page.url(),message:error.message,step:currentStep}));
  await page.goto(base+'/common/login.html');
  await page.locator('[name=username]').fill(account.username);await page.locator('[name=password]').fill(account.password||'123456');
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await page.waitForURL(url=>!url.pathname.endsWith('/common/login.html'));
  await page.locator('html[data-live-ready=true]').waitFor();
  const result={context,page,role,landing:new URL(page.url()).pathname};actors.set(role,result);return result;
}
async function goto(role,path){const a=await actor(role);await a.page.goto(base+'/'+path);await a.page.locator('html[data-live-ready=true]').waitFor();return a;}
async function fill(card,fields){
  for(const [key,value] of Object.entries(fields)){
    const input=card.locator('[name="'+key+'"]');
    await input.waitFor({state:'attached'});
    if(value===null){if(await input.evaluate(n=>n.tagName==='SELECT'))await input.selectOption('');else await input.fill('');continue;}
    if(await input.evaluate(n=>n.tagName==='SELECT'))await input.selectOption(String(value));
    else await input.fill(typeof value==='object'?JSON.stringify(value):String(value));
  }
}
async function submit(role,pagePath,method,path,fields={},key,expected=0,identity){
  if(method!=='GET'&&key&&state.receipts[key])return state.receipts[key];
  const {page}=await goto(role,pagePath),op=method+' '+path,card=page.locator('[data-operation="'+op+'"]');
  await card.waitFor({state:'attached'});await card.evaluate(n=>n.open=true);
  if(identity){const picker=card.locator('[name=identity-choice]');const value=await picker.locator('option').filter({hasText:identity}).getAttribute('value');await picker.selectOption(value);}
  await fill(card,fields);
  const invalid=await card.locator('input:invalid,select:invalid,textarea:invalid').evaluateAll(nodes=>nodes.map(n=>n.name+': '+n.validationMessage));
  assert.deepEqual(invalid,[],op+' form validation');
  const urlPath=path.replace(/\{([^}]+)\}/g,(_,name)=>String(fields[name]));
  const awaited=page.waitForResponse(response=>new URL(response.url()).pathname===urlPath&&response.request().method()===method);
  await card.getByRole('button',{name:method==='GET'?'查询':'确认提交',exact:true}).click();
  const response=await awaited,obj=await response.json();
  state.calls.push({role,step:currentStep,operation:op,http:response.status(),code:obj.code??response.status(),message:obj.message||obj.detail||'',request_key:response.request().headers()['idempotency-key']||null});
  assert.equal(obj.code??response.status(),expected,op+': '+JSON.stringify(obj).slice(0,500));
  if(method!=='GET'&&key&&expected===0){state.receipts[key]=obj.data;await save();}
  if(expected===0)await card.locator('.live-status').filter({hasText:method==='GET'?'已读取':'操作成功'}).waitFor();
  else await card.locator('.live-error').waitFor();
  return obj.data;
}
const get=(role,pagePath,path,fields={},expected=0)=>submit(role,pagePath,'GET',path,fields,undefined,expected);
async function screenshot(role,name){const {page}=await actor(role);await page.screenshot({path:dir+'/'+name+'.png',fullPage:true});}
async function register(role,identity,department,position,profileExtra={}){
  if(state.accounts[role])return state.accounts[role];
  const username=run+'_'+role;
  const fields={username};
  if(identity!=='admin'){
    Object.assign(fields,{'profile.full_name':({manager:'模拟运营主管',consultant:'模拟招生顾问',teacher:'模拟班主任',academic:'模拟教务',counselor:'模拟关怀老师',employee:'模拟普通员工',customer:'模拟客户',student:'模拟学生甲',consultantB:'模拟二部顾问',teacherB:'模拟二部班主任',studentB:'模拟学生乙'})[role]||role,'profile.department_id':department});
    if(identity==='employee')Object.assign(fields,{'profile.employee_no':run.slice(-10)+'_'+role,'profile.position_title':position});
    if(identity==='student')fields['profile.student_no']=run.slice(-10)+'_'+role;
    for(const [k,v]of Object.entries(profileExtra))fields['profile.'+k]=v;
  }
  const data=await submit('root','admin/accounts.html','POST','/api/v1/auth/register',fields,'register-'+role,0,({admin:'平台管理员',employee:'员工',student:'学生',customer:'客户'})[identity]);
  state.accounts[role]={role,username,password:'123456',identity_type:identity,position_title:position||'',user_id:data.user_id,employee_id:data.employee_id,student_id:data.student_id,customer_id:data.customer_id,department_id:department,role_codes:data.role_codes};
  await save();return state.accounts[role];
}
async function entity(role,pagePath,resource,idName,id){return get(role,pagePath,e+resource+'/{'+idName+'}',{[idName]:id});}
async function freshCustomer(role){return entity(role,'enterprise/customers.html','customer','customer_id',ids.customer);}
async function freshTicket(role='teacher'){return entity(role,'enterprise/tickets.html','tickets','ticket_id',ids.ticket);}
async function runWorkers(){
  const python=process.env.STUPROJECT_PYTHON||'D:/anaconda3/envs/SST/python.exe';
  const out=[];
  for(const [name,args] of [['student',['scripts/student/run_student_tasks.py','--once']],['enterprise',['scripts/enterprise/run_enterprise_tasks.py']]]){
    const p=spawnSync(python,args,{encoding:'utf8',windowsHide:true,timeout:45000,env:{...process.env,PYTHONUTF8:'1',PYTHONDONTWRITEBYTECODE:'1',PYTHONPATH:process.cwd()+'/.runtime/backend-deps'}});
    assert.equal(p.status,0,name+' worker: '+p.stderr);out.push({name,output:p.stdout.trim()});
  }
  state.worker_runs??=[];state.worker_runs.push(out);await save();
}

await step('01-root-login-and-create-two-departments',async()=>{
  const a=await actor('root');assert.equal(a.landing,'/dashboard/dashboard.html');
  for(const suffix of ['A','B']){const d=await submit('root','enterprise/organization.html','POST',e+'departments',{department_code:run+'_'+suffix,department_name:'模拟运营'+suffix+'部 '+run},'department-'+suffix);ids['department'+suffix]=d.department_id;}
});
await step('02-root-create-employee-roles',async()=>{
  requireIds('departmentA','departmentB');
  for(const [role,position]of [['manager','部门主管'],['consultant','招生顾问'],['teacher','班主任'],['academic','教务'],['counselor','学生关怀老师'],['employee','普通员工']])await register(role,'employee',ids.departmentA,position);
  await register('consultantB','employee',ids.departmentB,'招生顾问');await register('teacherB','employee',ids.departmentB,'班主任');
  await screenshot('root','admin-created-accounts');
});
await step('03-root-create-customer-and-students',async()=>{
  requireIds('departmentA','departmentB');
  const c=await register('customer','customer',ids.departmentA,null,{employee_id:state.accounts.consultant.employee_id,phone:'13900139001',education_level:'本科',target_country_code:'GB'});ids.customer=c.customer_id;
  const st=await register('student','student',ids.departmentA,null,{customer_id:ids.customer});ids.student=st.student_id;
  const stB=await register('studentB','student',ids.departmentB);ids.studentB=stB.student_id;
});
await step('04-each-role-login-and-landing',async()=>{
  for(const [role,account]of Object.entries(state.accounts)){
    const a=await actor(role);assert.equal(a.landing,account.identity_type==='student'?'/student/student-assistant.html':account.identity_type==='customer'?'/common/account.html':'/enterprise/enterprise.html');
  }
});
await step('05-root-create-course-and-service-bindings',async()=>{
  requireIds('student','studentB');
  const course=await submit('root','enterprise/courses.html','POST',e+'courses',{course_code:run,course_name:'模拟学术英语 '+run},'course');ids.course=course.course_id;ids.courseCode=run;
  for(const [role,student,relation,primary]of [['teacher',ids.student,'class_teacher',true],['counselor',ids.student,'class_teacher',false],['academic',ids.student,'score_editor',false],['teacherB',ids.studentB,'class_teacher',true]]){
    const fields={student_id:student,employee_id:state.accounts[role].employee_id,relation_type:relation,is_primary:primary,valid_from:localTime(-86400000)};
    if(relation==='score_editor')fields.course_scope_code=ids.courseCode;
    const r=await submit('root','enterprise/bindings.html','POST',e+'student-bindings',fields,'binding-'+role);ids['binding-'+role]=r.binding_id;
  }
});
await step('06-consultant-contact-and-followup',async()=>{
  requireIds('customer');let c=await freshCustomer('consultant');assert.equal(c.employee_id,state.accounts.consultant.employee_id);
  await submit('consultant','enterprise/customers.html','PUT',e+'customer/{customer_id}/status',{customer_id:ids.customer,status:'contacting',expected_version:c.row_version},'customer-contacting');
  const f=await submit('consultant','enterprise/followups.html','POST',e+'customer/{customer_id}/followups',{customer_id:ids.customer,content:'已完成首次需求沟通，客户计划申请英国院校。',channel:'phone',followup_at:localTime(-3600000),next_followup_at:localTime(86400000)},'followup');ids.followup=f.followup_id;
  c=await freshCustomer('consultant');await submit('consultant','enterprise/customers.html','PUT',e+'customer/{customer_id}/status',{customer_id:ids.customer,status:'qualified',expected_version:c.row_version},'customer-qualified');
});
await step('07-manager-scope-and-consultant-business-handover',async()=>{
  requireIds('customer');const c=await freshCustomer('manager');assert.equal(c.department_id,ids.departmentA);
  await submit('manager','enterprise/customers.html','POST',e+'customer/{customer_id}/assign',{customer_id:ids.customer,employee_id:state.accounts.consultant.employee_id,expected_version:c.row_version,reason:'主管核实负责顾问并确认进入签约准备'},'manager-assignment');
  await submit('consultantB','enterprise/customers.html','GET',e+'customer/{customer_id}',{customer_id:ids.customer},undefined,404);
});
await step('08-academic-enrollment-and-score',async()=>{
  requireIds('student','courseCode');
  const enrollment=await submit('academic','enterprise/courses.html','POST',e+'student-courses',{student_id:ids.student,course_code:ids.courseCode,term_code:'2026-FALL'},'enrollment');ids.enrollment=enrollment.enrollment_id;
  const score=await submit('academic','enterprise/scores.html','POST',e+'scores',{student_id:ids.student,course_code:ids.courseCode,term_code:'2026-FALL',assessment_code:'MIDTERM',attempt_no:1,score_value:86,max_score:100},'score');ids.score=score.score_id;
  await submit('academic','enterprise/scores.html','PUT',e+'scores/{score_id}',{score_id:ids.score,score_value:91,max_score:100,expected_version:1,reason:'教务复核客观题分数后更正'},'score-correction');
});
await step('09-student-and-teacher-read-real-course-and-score',async()=>{
  requireIds('score','courseCode');
  const courses=await get('student','student/academics.html',s+'courses');assert.ok(courses.items.some(x=>x.course_code===ids.courseCode));
  const scores=await get('student','student/academics.html',s+'scores');assert.equal(scores.items.find(x=>x.score_id===ids.score)?.score_value,91);
  const teacher=await entity('teacher','enterprise/scores.html','scores','score_id',ids.score);assert.equal(Number(teacher.score_value),91);
  const other=await get('studentB','student/academics.html',s+'scores');assert.ok(other.items.every(x=>x.score_id!==ids.score));
  await entity('teacherB','enterprise/scores.html','scores','score_id',ids.score).then(()=>assert.fail('cross-department teacher saw score')).catch(error=>{if(!error.message.includes('404'))throw error;});
  await screenshot('student','student-real-academics');
});
await step('10-academic-create-exam-student-reminder-and-reschedule',async()=>{
  requireIds('student');
  const event=await submit('academic','enterprise/academics.html','POST',e+'academic-events',{student_id:ids.student,event_type:'exam',title:'学术英语期末考试 '+run,due_at:localTime(7*86400000)},'exam');ids.event=event.id;
  const reminder=await submit('student','student/reminders.html','POST',s+'reminders',{academic_event_id:ids.event,lead_minutes:1440,expected_event_version:1},'reminder');ids.reminder=reminder.reminder_id;
  await submit('academic','enterprise/academics.html','PUT',e+'academic-events/{event_id}',{event_id:ids.event,expected_event_version:1,due_at:localTime(8*86400000),reason:'教务调整考试安排并同步重排提醒'},'exam-reschedule');
  const updated=await get('student','student/reminders.html',s+'reminders');assert.equal(updated.items.find(x=>x.id===ids.reminder)?.event_version,2);
});
await step('11-consultant-maintain-application-student-track-progress',async()=>{
  requireIds('student');
  const p=await submit('consultant','enterprise/application-progress.html','POST',e+'application-progress',{student_id:ids.student,application_name:'英国硕士申请 '+run,stage_code:'document_review',stage_status:'in_progress',detail:'顾问已收齐个人陈述和推荐信，进入文书审核。'},'application');ids.progress=p.id;
  await submit('consultant','enterprise/application-progress.html','PUT',e+'application-progress/{progress_id}',{progress_id:ids.progress,expected_version:1,stage_status:'completed',detail:'文书审核完成，材料可以递交。',reason:'顾问确认材料齐备'},'application-complete');
  const rows=await get('student','student/progress.html',s+'progress');assert.equal(rows.items.find(x=>x.id===ids.progress)?.stage_status,'completed');
});
await step('12-student-submit-leave-teacher-review',async()=>{
  requireIds('student');
  const leave=await submit('student','student/leave.html','POST',s+'leave',{leave_content:'因院校面试请假半天，课程材料将提前补齐。',leave_type:'personal',leave_start_at:localTime(2*86400000),leave_end_at:localTime(2*86400000+4*3600000)},'leave');ids.leave=leave.apply_id;
  assert.equal(leave.reviewer_id,state.accounts.teacher.employee_id);
  const detail=await get('teacher','enterprise/leave-review.html',i+'leave/{apply_id}',{apply_id:ids.leave});assert.equal(detail.approval_status,'pending');
  await submit('teacher','enterprise/leave-review.html','POST',i+'leave/{apply_id}/decision',{apply_id:ids.leave,expected_version:detail.row_version,decision:'approved',comment:'同意参加院校面试，返校后补齐课程。'},'leave-approved');
  const saved=await get('student','student/leave.html',s+'leave/{apply_id}',{apply_id:ids.leave});assert.equal(saved.approval_status,'approved');
});
await step('13-student-withdraw-second-leave',async()=>{
  const leave=await submit('student','student/leave.html','POST',s+'leave',{leave_content:'原计划办理材料，现预约取消，申请撤回。',leave_start_at:localTime(3*86400000),leave_end_at:localTime(3*86400000+3600000)},'leave-withdrawal-create');ids.withdrawnLeave=leave.apply_id;
  await submit('student','student/leave.html','DELETE',s+'leave/{apply_id}',{apply_id:ids.withdrawnLeave,expected_version:1},'leave-withdrawal');
});
await step('14-student-ticket-manager-assignment-teacher-reply',async()=>{
  const ticket=await submit('student','student/tickets.html','POST',s+'complaint',{content:'申请系统的课程材料说明不清晰，希望安排老师说明。',ticket_type:'complaint',category_code:'teaching'},'ticket');ids.ticket=ticket.ticket_id;
  const detail=await freshTicket('manager');
  await submit('manager','enterprise/tickets.html','POST',e+'tickets/{ticket_id}/assign',{ticket_id:ids.ticket,employee_id:state.accounts.teacher.employee_id,expected_version:detail.row_version,reason:'主管将课程材料问题分派给对应班主任'},'ticket-assignment');
  const assigned=await freshTicket();await submit('teacher','enterprise/tickets.html','POST',e+'tickets/{ticket_id}/followups',{ticket_id:ids.ticket,expected_version:assigned.row_version,content:'已核对材料清单，将安排一次说明会。',visibility:'student_visible'},'ticket-reply');
});
await step('15-student-reply-teacher-propose-solution',async()=>{
  requireIds('ticket');const r=await get('student','student/tickets.html',s+'tickets/{ticket_id}',{ticket_id:ids.ticket});
  await submit('student','student/tickets.html','POST',s+'tickets/{ticket_id}/reply',{ticket_id:ids.ticket,expected_version:r.row_version,content:'谢谢，希望补充上传材料的格式要求。'},'student-ticket-reply');
  const fresh=await freshTicket();await submit('teacher','enterprise/tickets.html','POST',e+'tickets/{ticket_id}/resolve',{ticket_id:ids.ticket,expected_version:fresh.row_version,content:'已发送材料格式说明并安排答疑，请学生确认是否解决。',visibility:'student_visible'},'ticket-first-solution');
});
await step('16-student-reopen-teacher-revise-solution',async()=>{
  requireIds('ticket');const r=await get('student','student/tickets.html',s+'tickets/{ticket_id}',{ticket_id:ids.ticket});
  await submit('student','student/tickets.html','POST',s+'tickets/{ticket_id}/confirm',{ticket_id:ids.ticket,expected_version:r.row_version,resolved:false,comment:'还缺少推荐信模板，请补充后再确认。'},'ticket-reopened');
  const fresh=await freshTicket();assert.equal(fresh.status,'reopened');assert.equal(fresh.reopen_count,1);
  await submit('teacher','enterprise/tickets.html','POST',e+'tickets/{ticket_id}/resolve',{ticket_id:ids.ticket,expected_version:fresh.row_version,content:'已补充推荐信模板并逐项解释材料要求。',visibility:'student_visible'},'ticket-final-solution');
});
await step('17-student-confirm-and-rate-ticket',async()=>{
  requireIds('ticket');let r=await get('student','student/tickets.html',s+'tickets/{ticket_id}',{ticket_id:ids.ticket});
  await submit('student','student/tickets.html','POST',s+'tickets/{ticket_id}/confirm',{ticket_id:ids.ticket,expected_version:r.row_version,resolved:true,comment:'问题已解决，材料要求已经清楚。'},'ticket-closed');
  r=await get('student','student/tickets.html',s+'tickets/{ticket_id}',{ticket_id:ids.ticket});
  await submit('student','student/tickets.html','POST',s+'tickets/{ticket_id}/rating',{ticket_id:ids.ticket,expected_version:r.row_version,satisfaction_score:5},'ticket-rated');
  await screenshot('student','student-closed-ticket');
});
await step('18-normal-employee-daily-report-manager-read',async()=>{
  const d=await submit('employee','enterprise/daily-report-new.html','POST',e+'daily-report',{report_date:date,submitted_content:'完成学生材料整理、课程说明与日常回访，问题已交接相关负责人。'},'daily');ids.daily=d.daily_report_id;
  const viewed=await entity('manager','enterprise/daily-reports.html','daily-report','report_id',ids.daily);assert.equal(viewed.employee_id,state.accounts.employee.employee_id);
  const other=await submit('consultantB','enterprise/daily-reports.html','POST',e+'daily-report',{report_date:date,submitted_content:'二部独立日报，用于部门数据隔离核验。'},'dailyB');ids.dailyB=other.daily_report_id;
  await get('manager','enterprise/daily-reports.html',e+'daily-report/{report_id}',{report_id:ids.dailyB},404);
});
await step('19-root-publish-knowledge-employee-read',async()=>{
  const knowledge=await submit('root','enterprise/knowledge.html','POST',e+'knowledge',{entry_code:run,entry_type:'faq',title:'新员工材料交接指引 '+run,question:'材料齐备后怎样交接？',answer:'顾问确认材料，教务核对课程，班主任跟踪学生反馈。',access_department_id:ids.departmentA},'knowledge');ids.knowledge=knowledge.knowledge_id;
  await submit('root','enterprise/knowledge.html','POST',e+'knowledge/{knowledge_id}/publish',{knowledge_id:ids.knowledge,expected_version:1,effective_from:localTime(-86400000)},'knowledge-published');
  const read=await entity('employee','enterprise/knowledge.html','knowledge','knowledge_id',ids.knowledge);assert.equal(read.status,'published');
  await get('consultantB','enterprise/knowledge.html',e+'knowledge/{knowledge_id}',{knowledge_id:ids.knowledge},404);
});
await step('20-real-notification-jobs-publish-and-student-read',async()=>{
  await runWorkers();
  const notices=await get('student','student/notifications.html',s+'notifications',{limit:100});
  assert.ok(notices.items.length>0,'student should receive business notifications');
  const notice=notices.items.find(x=>x.entity_id===ids.leave)||notices.items[0];ids.notification=notice.notification_id;
  await submit('student','student/notifications.html','POST',s+'notifications/{notification_id}/read',{notification_id:ids.notification},'notification-read');
  const detail=await get('student','student/notifications.html',s+'notifications/{notification_id}',{notification_id:ids.notification});assert.ok(detail.read_at);
  await screenshot('student','student-notifications');
});
await step('21-student-and-role-isolation-through-pages',async()=>{
  requireIds('leave','ticket');
  await get('studentB','student/leave.html',s+'leave/{apply_id}',{apply_id:ids.leave},404);
  await get('studentB','student/tickets.html',s+'tickets/{ticket_id}',{ticket_id:ids.ticket},404);
  await get('teacherB','enterprise/leave-review.html',i+'leave/{apply_id}',{apply_id:ids.leave},404);
  await submit('teacher','enterprise/scores.html','PUT',e+'scores/{score_id}',{score_id:ids.score,expected_version:2,score_value:100,max_score:100,reason:'权限隔离验证，应该拒绝'},undefined,403);
  for(const role of ['student','customer','employee']){const {page}=await goto(role,'admin/accounts.html');assert.equal(await page.locator('[data-operation="POST /api/v1/auth/register"]').count(),0);}
});
await step('22-customer-account-public-catalog-and-own-account',async()=>{
  const {page}=await goto('customer','common/account.html');assert.equal(await page.locator('[data-operation="GET /api/v1/auth/me/access"]').count(),1);
  await get('customer','agent/courses.html','/api/v1/agent/courses');
  await get('customer','agent/events.html','/api/v1/agent/events');
  await screenshot('customer','customer-public-catalog');
});
await step('23-counselor-authorized-view-without-fabricated-assessment',async()=>{
  const warnings=await get('counselor','enterprise/warnings.html',i+'warnings');assert.ok(Array.isArray(warnings.items));
  const denied=await get('teacher','enterprise/warnings.html',i+'warnings',{},403);
  assert.equal(denied,null);
});
await step('24-root-review-real-operation-audit',async()=>{
  const logs=await get('root','admin/audit.html',e+'operation-logs',{limit:100});assert.ok(logs.items.length>0);
  assert.ok(logs.items.some(x=>x.operation_status==='succeeded'));
  await screenshot('root','root-operation-audit');
});
await step('25-ai-workflows-and-real-risk-assessment',async()=>{
  skip('未配置实际模型；不编造心理评估或AI回答。人工关怀页面可访问，但没有本轮真实模型预警可供接手/关闭。');
});
await step('26-reports-receipt-and-actual-model-limit',async()=>{
  const receipt=await submit('root','report/generate.html','POST','/api/v1/report/generate',{report_code:'daily_report'},'report');ids.report=receipt.report_record_id;
  const detail=await get('root','report/detail.html','/api/v1/report/{report_record_id}',{report_record_id:ids.report});state.report_state=detail.status;
  if(detail.status==='failed'||detail.status==='pending')skip('真实模型未接入：报告收单/回执已验证，正文生成不计成功；当前状态 '+detail.status);
  assert.equal(detail.status,'success');
});
await step('27-no-browser-runtime-errors',async()=>assert.deepEqual(state.errors,[]));

state.finished_at=new Date().toISOString();state.summary={accounts:Object.keys(state.accounts).length,scenarios:state.scenarios.length,passed:state.scenarios.filter(x=>x.status==='passed').length,failed:state.scenarios.filter(x=>x.status==='failed').length,skipped:state.scenarios.filter(x=>x.status==='skipped').length,ui_requests:state.calls.length};
await save();
await writeFile(dir+'/accounts.csv','\uFEFF'+['角色,账号,初始密码,身份,职位,部门编号',...Object.values(state.accounts).map(a=>[a.role,a.username,'123456',a.identity_type,a.position_title,a.department_id].join(','))].join('\n'));
console.log(JSON.stringify(state.summary));
await browser.close();process.exitCode=state.summary.failed?1:0;
