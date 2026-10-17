// 主入口、18个独立页面、智能助手、权限及移动端回归；真实页面＋隔离API数据。
async (page) => {
  const context=await page.context().browser().newContext({viewport:{width:1440,height:1000}});
  const checks=[];
  try{
    const p=await context.newPage(),errors=[],writes=[];
    const all=['access','daily.read','daily.write_own','organization.read','knowledge.read','todo.read_own','notification.read_own','command','query','customer.read','customer.create','customer.update','customer.status','customer.followup','customer.archive','customer.assign','ticket.read','ticket.assign','ticket.handle','progress.write','student.read','score.read','score.write','score.void','academic.write','organization.manage','employee.manage','role.manage','binding.manage','knowledge.manage','knowledge.publish','audit.read'];
    let permissions=all,failCustomer=true,failList=false;
    const fixture={
      customer:{customer_id:31,customer_no:'C20261017001',full_name:'林同学',status:'contacting',employee_id:1,row_version:2},
      students:{student_id:3,student_no:'S2026003',full_name:'林同学',department_id:1,status:'active'},
      courses:{course_id:10,course_code:'MATH_101',course_name:'学术数学',status:'active',row_version:2},
      'student-courses':{enrollment_id:5,student_id:3,course_code:'MATH_101',term_code:'2026-FALL',status:'active',row_version:2},
      'daily-report':{daily_report_id:7,report_date:'2026-10-17',employee_id:1,submitted_content:'完成学生回访与申请资料核对。',status:'submitted',row_version:2},
      scores:{score_id:9,student_id:3,course_code:'MATH_101',assessment_code:'MIDTERM',score_value:92,max_score:100,status:'valid',row_version:2},
      tickets:{ticket_id:12,ticket_no:'TK2026101701',category_code:'academic',status:'processing',employee_id:1,resolution_due_at:'2026-10-19T09:00:00',row_version:2},
      'academic-events':{id:21,student_id:3,title:'学期考试',event_type:'exam',event_status:'active',due_at:'2026-10-20T02:00:00',event_version:4},
      'application-progress':{id:15,student_id:3,application_name:'英国院校申请',stage_code:'document_review',stage_status:'in_progress',detail:'资料复核中',row_version:2},
      knowledge:{knowledge_id:11,title:'新员工工作指引',entry_type:'faq',version_no:2,status:'published',row_version:2},
      notifications:{notification_id:10,title:'考试安排已更新',sent_at:'2026-10-17T03:20:00',read_at:null},
      employees:{employee_id:1,employee_no:'E001',full_name:'周老师',department_id:1,position_title:'老师',work_email:'teacher@example.test',row_version:2},
      departments:{department_id:1,department_code:'EDU',department_name:'教务服务部',status:'active',row_version:2},
      'student-bindings':{binding_id:6,student_id:3,employee_id:1,relation_type:'class_teacher',course_scope_code:'MATH_101',status:'active',row_version:2},
      'operation-logs':{operation_log_id:88,created_at:'2026-10-17T04:12:00',employee_id:1,action_code:'enterprise.score.write',entity_type:'student_score',entity_id:'9',operation_status:'succeeded'},
      todos:{id:3,title:'跟进学生申请资料',type:'followup',due_at:'2026-10-17T10:00:00'}
    };
    p.on('pageerror',error=>errors.push(error.message));
    await p.addInitScript(()=>sessionStorage.setItem('enterprise.token','isolated-module-test'));
    await p.route('**/api/v1/**',async route=>{
      const request=route.request(),url=new URL(request.url()),path=url.pathname,resource=path.split('/')[4];let data;
      if(path.endsWith('/auth/me/access'))data={user_id:2,identity_type:'employee'};
      else if(path.endsWith('/me/permissions'))data={employee_id:1,department_id:1,roles:['employee','manager','teacher','academic','admin'],permissions:permissions.map(x=>'enterprise.'+x)};
      else if(request.method()!=='GET'){
        const body=request.headers()['content-type']?.includes('application/json')?request.postDataJSON():null;
        writes.push({path,method:request.method(),body,key:request.headers()['idempotency-key']});
        if(path.endsWith('/customer') && failCustomer){failCustomer=false;return route.fulfill({json:{code:503,message:'测试临时不可用，请重试。',data:null}});}
        if(path.endsWith('/command'))data={token:'signed-preview',action:'daily.create',target:{},fields:{report_date:'2026-10-17',submitted_content:'测试日报'},needs_clarification:false};
        else if(path.endsWith('/nl2sql'))data={rows:[{full_name:'<script>bad()</script>',customer_id:31}]};
        else if(path.endsWith('/onboarding/ask'))data={answer:'请在员工日报页面录入当天工作。',citations:[{id:11,version:2}]};
        else data=fixture[resource]||{};
      }else if(path.endsWith('/organization'))data=[fixture.departments];
      else if(failList && resource==='customer')return route.fulfill({json:{code:503,message:'列表加载失败，请刷新。',data:null}});
      else if(/\/\d+$/.test(path))data=fixture[resource]||{};
      else{
        const row=fixture[resource];data={items:row?[row]:[],total:row?1:0};
        if(resource==='customer'){data.total=21;if(url.searchParams.get('offset')==='20')data.items=[{...fixture.customer,customer_id:32,full_name:'陈同学'}];}
      }
      await route.fulfill({json:{code:0,message:'success',data}});
    });
    await p.goto('http://127.0.0.1:8000/enterprise');
    const frame=p.frameLocator('#module-frame');
    async function go(name,key){await p.getByRole('link',{name,exact:true}).click();await frame.locator('body[data-resource="'+key+'"]').waitFor();await frame.locator('#table-body tr').waitFor();}
    await frame.locator('#quick-links button').first().waitFor();
    if(await frame.locator('.metric-value').count()!==4)throw Error('概览未加载授权指标');
    await p.screenshot({path:'D:/project/StuProject/.runtime/enterprise-tech-desktop.png',fullPage:true});
    checks.push('概览真实列表计数、快捷入口及科技风页面加载通过');
    const navigation=[['我的待办','todos'],['客户管理','customer'],['员工日报','daily-report'],['学生档案','students'],['学生成绩','scores'],['课程管理','courses'],['学生选课','student-courses'],['学业节点','academic-events'],['申请进度','application-progress'],['投诉工单','tickets'],['知识资料','knowledge'],['我的通知','notifications'],['组织通讯录','employees'],['部门配置','departments'],['学生员工关系','student-bindings'],['操作审计','operation-logs']];
    for(const [name,key]of navigation){
      await go(name,key);
      if(!p.url().endsWith('#/'+key))throw Error(name+'未写入独立页面地址');
      if(await frame.locator('#page-title').innerText()!==name)throw Error(name+'页面标题错误');
    }
    checks.push('16个业务HTML独立加载、导航及接口列表通过');
    await p.goBack();await frame.locator('body[data-resource="student-bindings"]').waitFor();
    await p.goForward();await frame.locator('body[data-resource="operation-logs"]').waitFor();
    checks.push('浏览器前进、后退恢复对应独立页面通过');
    await go('客户管理','customer');
    await frame.locator('#table-search').fill('不存在');await frame.locator('#empty').waitFor({state:'visible'});
    await frame.locator('#table-search').fill('');await frame.locator('#next').click();await frame.getByRole('cell',{name:'陈同学',exact:true}).waitFor();
    checks.push('本页筛选、空态与服务端分页通过');
    await frame.locator('#new-record').click();await frame.locator('[name="full_name"]').fill('测试客户');
    await frame.locator('#edit-form button[type="submit"]').click();await frame.locator('#edit-error').getByText('测试临时不可用，请重试。',{exact:true}).waitFor();
    await frame.locator('#edit-form button[type="submit"]').click();await frame.locator('#editor').waitFor({state:'hidden'});
    const createWrites=writes.filter(w=>w.path.endsWith('/customer'));
    if(createWrites.length!==2||createWrites[0].key!==createWrites[1].key||createWrites[1].body.full_name!=='测试客户')throw Error('新建客户请求或失败重试幂等键不正确');
    checks.push('客户新建与失败重试保持幂等键通过');
    await go('学业节点','academic-events');await frame.getByRole('button',{name:'编辑',exact:true}).click();
    if(await frame.locator('[name="due_at"]').inputValue()!=='2026-10-20T10:00')throw Error('UTC节点未按北京时间回填');
    await frame.locator('[name="due_at"]').fill('2026-10-21T11:30');await frame.locator('[name="reason"]').fill('考试调整');
    await frame.locator('#edit-form button[type="submit"]').click();await frame.locator('#editor').waitFor({state:'hidden'});
    const update=writes.at(-1);if(update.body.expected_event_version!==4||update.body.due_at!=='2026-10-21T11:30:00+08:00')throw Error('节点版本或北京时间提交错误');
    checks.push('学业节点独立版本及北京时间往返通过');
    await p.getByRole('link',{name:'智能助手',exact:true}).click();await frame.locator('#assistant-text').fill('提交今天日报');
    await frame.locator('#assistant-form button[type="submit"]').click();await frame.getByRole('button',{name:'确认办理',exact:true}).waitFor();
    if(writes.some(w=>w.path.endsWith('/command/confirm')))throw Error('预览阶段提前提交业务');
    await frame.getByRole('button',{name:'确认办理',exact:true}).click();await frame.getByText('办理成功',{exact:true}).waitFor();
    const confirmation=writes.at(-1);if(confirmation.body.token!=='signed-preview'||!confirmation.key)throw Error('确认请求缺少签名或幂等键');
    await frame.locator('#assistant-mode').selectOption('query');await frame.locator('#assistant-text').fill('查询客户');
    await frame.locator('#assistant-form button[type="submit"]').click();await frame.getByRole('cell',{name:'<script>bad()</script>',exact:true}).waitFor();
    if(writes.at(-1).body.question!=='查询客户'||await frame.locator('#assistant-result script').count())throw Error('查询参数或转义不正确');
    await frame.locator('#assistant-mode').selectOption('knowledge');await frame.locator('#assistant-text').fill('如何提交日报');
    await frame.locator('#assistant-form button[type="submit"]').click();await frame.getByText('来源 11 · 版本 2',{exact:true}).waitFor();
    checks.push('助手三模式、写入确认、知识引用与输出转义通过');
    await p.setViewportSize({width:390,height:844});await p.locator('#toggle-nav').click();await go('学生成绩','scores');
    if(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth)||await frame.locator('body').evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('移动端整页横向溢出');
    if(await p.locator('#toggle-nav').getAttribute('aria-expanded')!=='false')throw Error('移动端导航未关闭');
    await p.waitForFunction(()=>document.getElementById('sidebar').getBoundingClientRect().right<=1);
    await p.screenshot({path:'D:/project/StuProject/.runtime/enterprise-tech-mobile.png',fullPage:true});
    checks.push('手机侧栏、表格局部滚动与页面尺寸通过');
    await p.setViewportSize({width:1440,height:1000});
    await go('客户管理','customer');failList=true;
    await frame.locator('#refresh').click();await frame.getByText('列表加载失败，请刷新。',{exact:true}).waitFor();
    if(await frame.locator('#table-body tr').count())throw Error('失败后保留了旧列表');checks.push('列表异常提示并清除过期记录通过');
    failList=false;permissions=['daily.read','daily.write_own','todo.read_own','organization.read','notification.read_own','knowledge.read','command','query'];
    await p.goto('http://127.0.0.1:8000/enterprise#/scores');await p.reload();await frame.locator('#quick-links button').first().waitFor();
    if(await p.getByRole('link',{name:'学生成绩',exact:true}).count())throw Error('无成绩权限仍展示入口');
    await p.goto('http://127.0.0.1:8000/static/enterprise/pages/scores.html');await p.getByRole('heading',{name:'暂时无法访问'}).waitFor();
    checks.push('无权限隐藏导航，直接访问独立页面也被拒绝通过');
    await p.goto('http://127.0.0.1:8000/static/index.html');await p.getByRole('link',{name:/企业管理/}).waitFor();
    if(await p.getByRole('link',{name:/企业管理/}).getAttribute('href')!=='/enterprise')throw Error('主页面未连接独立企业模块');
    checks.push('系统主页面跳转企业独立模块通过');
    if(errors.length)throw Error(errors.join('; '));
    return {passed:true,checks,uncaught_errors:errors,real_database_written:false};
  }catch(error){throw Error('已完成：'+checks.join('；')+'；失败：'+error.message);}
  finally{await context.close();}
}
