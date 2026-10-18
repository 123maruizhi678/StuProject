import { chromium } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';

const base=process.env.SYSTEM_BASE_URL||'http://127.0.0.1';
const catalog=JSON.parse(await readFile('frontend/pages.json','utf8'));
const backend=JSON.parse(await readFile('.runtime/backend-system.json','utf8'));
const browser=await chromium.launch({channel:'msedge',headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000}});
const page=await context.newPage();page.setDefaultTimeout(12000);
const results=[],errors=[],requests=[];
let browserEventId;
page.on('pageerror',error=>errors.push({url:page.url(),message:error.message}));
page.on('response',r=>{if(r.url().includes('/api/'))requests.push({url:r.url(),status:r.status()});});
async function check(name,run){
  try{await run();results.push({name,status:'passed'});}catch(error){
    const visibleErrors=await page.locator('.live-error').allTextContents();
    const invalid=await page.locator('input:invalid,select:invalid,textarea:invalid').evaluateAll(nodes=>nodes.map(n=>({name:n.name,reason:n.validationMessage}))).catch(()=>[]);
    results.push({name,status:'failed',reason:error.message,visibleErrors,invalid});console.log('FAILED',name,error.message,JSON.stringify({visibleErrors,invalid}));
  }
}
async function login(username,password){
  await page.goto(base+'/common/login.html');
  await page.locator('[name=username]').fill(username);await page.locator('[name=password]').fill(password);
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await page.waitForURL(url=>!url.pathname.endsWith('/common/login.html'));await page.waitForSelector('html[data-live-ready=true]');
}
async function ready(path){
  await page.goto(base+'/'+path);
  if(!['index.html','common/login.html','common/sitemap.html','common/password-reset.html'].includes(path))await page.waitForSelector('html[data-live-ready=true]');
}
async function submitOperation(operation,fields){
  const card=page.locator('[data-operation="'+operation+'"]');await card.evaluate(n=>n.open=true);
  for(const [name,value] of Object.entries(fields)){
    const input=card.locator('[name="'+name+'"]');
    if(await input.evaluate(n=>n.tagName==='SELECT'))await input.selectOption(String(value));
    else await input.fill(String(value));
  }
  await card.getByRole('button',{name:operation.startsWith('GET')?'查询':'确认提交',exact:true}).click();
  await card.locator('.live-status').filter({hasText:operation.startsWith('GET')?'已读取':'操作成功'}).waitFor();
  assert.equal(await card.locator('.live-error').count(),0);
  return card;
}
await check('root_login_through_vite_proxy',async()=>{
  await login('root','root');
  assert.equal(await page.locator('html[data-live-ready=true]').count(),1);
  assert.equal(await page.locator('.preview-notice').count(),0);
});
for(const item of catalog){
  await check('page:'+item.path,async()=>{
    await ready(item.path);
    assert.ok((await page.title()).length>0);
    if(item.path==='index.html'||item.path==='common/login.html'||item.path==='common/sitemap.html'||item.path==='common/password-reset.html')return;
    const cards=page.locator('[data-operation]');assert.ok(await cards.count()>0,'page must expose real operations');
    // Open every operation. GET cards without required identifiers load real data; mutations remain untouched.
    await cards.evaluateAll(nodes=>nodes.forEach(node=>node.open=true));
    await page.waitForFunction(()=>![...document.querySelectorAll('.live-form button[type=submit]')].some(b=>b.disabled));
    assert.equal(await page.locator('text=页面加载失败').count(),0);
    const messages=await page.locator('.live-error').allTextContents();
    assert.ok(!messages.some(x=>/Cannot |undefined|is not a |服务器内部错误/.test(x)),messages.join(';'));
  });
}
for(const [alias,target] of [['enterprise/index.html','enterprise/enterprise.html'],['report/index.html','report/report.html'],['research/index.html','customer/customer.html'],['student/login.html','common/login.html'],['student/preview.html','student/student-assistant.html']]){
  await check('compatibility_page:'+alias,async()=>{await page.goto(base+'/'+alias);await page.waitForURL('**/'+target);assert.ok(await page.title());});
}
await check('sitemap_search',async()=>{
  await page.goto(base+'/common/sitemap.html');await page.locator('[data-map-search]').fill('客户档案');
  assert.ok(await page.locator('.map-link:visible').count()>0);
  assert.ok(await page.locator('.map-link[hidden]').count()>0);
});
await check('customer_create_persisted_and_versioned_update',async()=>{
  await ready('enterprise/customers.html');
  const create=page.locator('[data-operation="POST /api/v1/enterprise/customer"]');await create.evaluate(n=>n.open=true);
  const name='浏览器验收 '+Date.now();await create.locator('[name=full_name]').fill(name);
  await create.getByRole('button',{name:'确认提交',exact:true}).click();
  await create.locator('.live-status').filter({hasText:'操作成功'}).waitFor();
  const response=await create.locator('.live-result').innerText();assert.ok(response.includes(name));
  const update=page.locator('[data-operation="PUT /api/v1/enterprise/customer/{customer_id}"]');await update.evaluate(n=>n.open=true);
  assert.ok(await update.locator('[name=customer_id]').inputValue(),'receipt populates exact customer id');
  assert.equal(await update.locator('[name=expected_version]').inputValue(),'1');
  await update.locator('[name=full_name]').fill(name+'修订');await update.getByRole('button',{name:'确认提交',exact:true}).click();
  await update.locator('.live-status').filter({hasText:'操作成功'}).waitFor();
  assert.ok((await update.locator('.live-result').innerText()).includes(name+'修订'));
});
await check('course_enrollment_score_academic_progress_forms',async()=>{
  const tag='WEB'+Date.now();await ready('enterprise/courses.html');
  await submitOperation('POST /api/v1/enterprise/courses',{course_code:tag,course_name:'浏览器验收课程'});
  await submitOperation('POST /api/v1/enterprise/student-courses',{student_id:backend.fixture_ids.student_id,course_code:tag,term_code:'2026-WEB'});
  await ready('enterprise/scores.html');
  await submitOperation('POST /api/v1/enterprise/scores',{student_id:backend.fixture_ids.student_id,course_code:tag,term_code:'2026-WEB',assessment_code:'WEB',score_value:88,max_score:100});
  await submitOperation('PUT /api/v1/enterprise/scores/{score_id}',{score_value:89,max_score:100,reason:'浏览器更正验收'});
  await ready('enterprise/academics.html');
  await submitOperation('POST /api/v1/enterprise/academic-events',{student_id:backend.fixture_ids.student_id,event_type:'exam',title:'浏览器验收考试',due_at:'2026-12-20T10:30'});
  browserEventId=await page.evaluate(()=>JSON.parse(sessionStorage.getItem('stuproject.live.selection')).event_id);
  await ready('enterprise/application-progress.html');
  await submitOperation('POST /api/v1/enterprise/application-progress',{student_id:backend.fixture_ids.student_id,application_name:'浏览器申请验收',stage_code:'visa_process',stage_status:'pending'});
});
await check('daily_knowledge_forms_and_real_results',async()=>{
  await ready('enterprise/daily-report-new.html');const day=new Date(Date.now()-Math.floor(Math.random()*3000+100)*86400000).toISOString().slice(0,10);
  await submitOperation('POST /api/v1/enterprise/daily-report',{report_date:day,submitted_content:'浏览器工作日报验收'});
  await submitOperation('PUT /api/v1/enterprise/daily-report/{report_id}',{submitted_content:'浏览器日报修订',reason:'验收'});
  await ready('enterprise/knowledge.html');await submitOperation('POST /api/v1/enterprise/knowledge',{entry_code:'WEB'+Date.now(),entry_type:'faq',title:'浏览器验收知识',question:'如何查看验收结果',answer:'在验收报告中查看'});
  await submitOperation('POST /api/v1/enterprise/knowledge/{knowledge_id}/publish',{effective_from:'2026-10-01T00:00',expected_version:1});
});
await check('customer_file_upload_parse_and_judge_forms',async()=>{
  await ready('customer/sources.html');const card=page.locator('[data-operation="POST /api/v1/customer/source"]');await card.evaluate(n=>n.open=true);
  await card.locator('[name=file]').setInputFiles({name:'browser-qa.csv',mimeType:'text/csv',buffer:Buffer.from('姓名,年龄,学历\n浏览器验收客户,25,本科')});
  await card.getByRole('button',{name:'确认提交',exact:true}).click();await card.locator('.live-status').filter({hasText:'操作成功'}).waitFor();
  await submitOperation('POST /api/v1/customer/source/{source_id}/parse',{});
  // Selecting a parsed field supplies its stable identifier for the judgement page.
  const infoId=await page.evaluate(()=>JSON.parse(sessionStorage.getItem('stuproject.live.selection')).fields?.[0]?.id);
  assert.ok(infoId);await ready('customer/results.html');
  await submitOperation('POST /api/v1/customer/judge',{customer_info_id:infoId,product_code:backend.run_id});
});
await check('student_leave_ticket_reminder_forms',async()=>{
  await login(backend.run_id+'_student','123456');await ready('student/leave.html');
  await submitOperation('POST /api/v1/student/leave',{leave_content:'浏览器请假验收',leave_start_at:'2026-12-01T09:00',leave_end_at:'2026-12-01T10:00'});
  await submitOperation('DELETE /api/v1/student/leave/{apply_id}',{});
  await ready('student/tickets.html');await submitOperation('POST /api/v1/student/complaint',{content:'浏览器反馈验收',category_code:'service'});
  assert.ok(browserEventId);await ready('student/reminders.html');await submitOperation('POST /api/v1/student/reminders',{academic_event_id:browserEventId,lead_minutes:30,expected_event_version:1});
  await submitOperation('DELETE /api/v1/student/reminders/{reminder_id}',{});
  await login('root','root');
});
await check('report_generate_config_and_failed_external_status',async()=>{
  await login('root','root');
  await ready('report/generate.html');const card=await submitOperation('POST /api/v1/report/generate',{report_code:'daily_report'});
  assert.ok((await card.locator('.live-result').innerText()).includes('报告编号'));
  await ready('report/configs.html');
  await page.locator('[data-operation="GET /api/v1/report/configs"] .live-result button').first().click();
  const row=await page.evaluate(()=>JSON.parse(sessionStorage.getItem('stuproject.live.selection')));
  await submitOperation('PUT /api/v1/report/configs/{report_code}',{report_code:row.report_code,report_name:row.report_name,enabled:String(row.enabled),row_version:row.row_version});
});
await check('admin_register_student_and_login',async()=>{
  await ready('admin/accounts.html');const card=page.locator('[data-operation="POST /api/v1/auth/register"]');await card.evaluate(n=>n.open=true);
  const select=card.locator('[name=identity-choice]');
  const studentOption=await select.locator('option').filter({hasText:'学生'}).getAttribute('value');await select.selectOption(studentOption);
  const username='browser_'+Date.now();await card.locator('[name=username]').fill(username);
  await card.locator('[name="profile.student_no"]').fill(username);await card.locator('[name="profile.full_name"]').fill('浏览器验收学生');
  await card.locator('[name="profile.department_id"]').selectOption(String(backend.fixture_ids.department_id));
  await card.getByRole('button',{name:'确认提交',exact:true}).click();await card.locator('.live-status').filter({hasText:'操作成功'}).waitFor();
  await login(username,'123456');await ready('student/leave.html');
  assert.equal(await page.locator('.live-error').filter({hasText:'当前账号没有访问权限'}).count(),0);
});
await check('student_pages_real_queries',async()=>{
  await login(backend.run_id+'_student','123456');
  for(const item of catalog.filter(x=>x.path.startsWith('student/'))){
    await ready(item.path);
    const cards=page.locator('[data-operation]');await cards.evaluateAll(nodes=>nodes.forEach(n=>n.open=true));
    await page.waitForFunction(()=>![...document.querySelectorAll('.live-form button[type=submit]')].some(b=>b.disabled));
    const messages=await page.locator('.live-error').allTextContents();
    assert.ok(!messages.some(x=>/服务器内部错误|页面加载失败/.test(x)),messages.join(';'));
  }
});
await check('student_cannot_open_admin_registration',async()=>{
  await ready('admin/accounts.html');assert.equal(await page.locator('[data-operation="POST /api/v1/auth/register"]').count(),0);
});
await check('mobile_layout_and_navigation',async()=>{
  await login('root','root');await page.setViewportSize({width:390,height:844});await ready('enterprise/customers.html');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
  await page.locator('[data-menu]').click();assert.ok((await page.locator('body').getAttribute('class')).includes('rail-open'));
  await page.waitForFunction(()=>document.querySelector('.app-rail').getBoundingClientRect().left>=-1);
  await page.locator('.mobile-scrim').click({position:{x:370,y:200}});
  await page.waitForFunction(()=>document.querySelector('.app-rail').getBoundingClientRect().right<=1);
  await page.screenshot({path:'.runtime/system-mobile.png'});await page.setViewportSize({width:1440,height:1000});
});
await check('public_no_auth_catalog_and_unconfigured_ai',async()=>{
  await page.evaluate(()=>sessionStorage.clear());await ready('agent/events.html');
  assert.equal(await page.locator('.live-error').count(),0);
  await submitOperation('POST /api/v1/agent/events/signup',{event_id:backend.fixture_ids.agent_event_id,customer_name:'浏览器报名验收',customer_phone:'138'+String(Date.now()).slice(-8)});
  await ready('agent/agent.html');const chat=page.locator('[data-operation="POST /api/v1/agent/chat"]');
  await chat.locator('[name=message]').fill('测试咨询');await chat.getByRole('button',{name:'确认提交',exact:true}).click();
  await chat.locator('.live-error').waitFor();assert.ok((await chat.locator('.live-error').innerText()).length>0);
});
await check('no_browser_runtime_errors',async()=>assert.deepEqual(errors,[]));
await login('root','root');await ready('enterprise/customers.html');await page.screenshot({path:'.runtime/system-desktop.png',fullPage:true});
const result={base_url:base,pages:catalog.length+5,primary_pages:catalog.length,compatibility_pages:5,results,errors,requests,
  summary:{checks:results.length,passed:results.filter(x=>x.status==='passed').length,failed:results.filter(x=>x.status==='failed').length,api_responses:requests.length}};
await writeFile('.runtime/browser-system.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result.summary));
await browser.close();process.exitCode=result.summary.failed?1:0;
