// 本地运行中的站点 + 隔离 API；不写入真实数据库。
async (page) => {
  const context=await page.context().browser().newContext({viewport:{width:1440,height:1000}});
  const checks=[];
  const assert=(ok,message)=>{if(!ok)throw Error(message);};
  try{
    const p=await context.newPage(),errors=[],writes=[],reads=[];
    const enterprise=['access','daily.read','daily.write_own','organization.read','organization.manage','employee.manage','role.manage','binding.manage',
      'customer.read','customer.create','customer.update','customer.status','customer.archive','customer.assign','customer.followup',
      'student.read','score.read','score.write','score.void','academic.write','progress.write','ticket.read','ticket.handle','ticket.assign',
      'knowledge.read','knowledge.manage','knowledge.publish','todo.read_own','notification.read_own','command','query','audit.read'].map(x=>'enterprise.'+x);
    const internal=['student.admin_service.review','student.admin_service.assign','student.warning.read','student.warning.handle','student.warning.assign','student.academic.maintain','student.progress.maintain'];
    let permissions=[...enterprise,...internal],identity='employee',retry=true,conflict=false,delayDetail=false;
    let customer={customer_id:31,full_name:'林同学',status:'contacting',education_level:'本科',row_version:3};
    let following={followup_id:72,customer_id:31,content:'确认申请材料',channel:'电话',followup_status:'pending',row_version:4,next_followup_at:'2026-10-20T02:00:00'};
    const fixture={
      customer:[customer,{customer_id:32,full_name:'陈同学',status:'new',row_version:1}],
      organization:[{department_id:3,department_name:'教务服务部',department_code:'EDU',row_version:4,status:'active'}],
      employees:[{employee_id:9,employee_no:'E009',full_name:'周老师',department_id:3,role_codes:['employee','teacher'],row_version:6,status:'active'}],
      'student-bindings':[{binding_id:15,student_id:1,employee_id:9,relation_type:'class_teacher',row_version:2}],
      'daily-report':[{daily_report_id:8,employee_id:7,report_date:'2026-10-18',submitted_content:'完成学生回访',row_version:2},
        {daily_report_id:9,employee_id:9,report_date:'2026-10-18',submitted_content:'他人日报',row_version:1}],
      students:[{student_id:1,full_name:'学生甲',row_version:1}],
      scores:[{score_id:4,student_id:1,course_code:'MATH',score_value:92,max_score:100,row_version:2}],
      courses:[{course_id:5,course_name:'学术数学',course_code:'MATH',status:'active',row_version:2}],
      'student-courses':[{enrollment_id:6,student_id:1,course_code:'MATH',term_code:'2026-FALL',status:'active',row_version:1}],
      'academic-events':[{id:21,student_id:1,title:'学期考试',event_type:'exam',due_at:'2026-10-20T02:00:00',event_version:4,event_status:'active',source_timezone:'Asia/Shanghai'}],
      'application-progress':[{id:22,student_id:1,application_name:'英国申请',stage_code:'document_review',stage_status:'pending',row_version:3}],
      tickets:[{ticket_id:12,title:'申请服务工单',status:'processing',row_version:5}],
      knowledge:[{knowledge_id:13,title:'入职指引',entry_type:'faq',row_version:2}],
      notifications:[{notification_id:14,title:'材料已更新',read_at:null,row_version:1}],
      'operation-logs':[{operation_log_id:17,action_code:'enterprise.customer.update'}],
      leave:[{id:61,student_id:1,approval_status:'pending',leave_content:'考试请假',row_version:5}],
      warnings:[{id:62,student_id:1,title:'关怀记录',status:'pending',row_version:2}],
      todos:[{type:'ticket',id:12,title:'工单待处理'},{type:'followup',id:72,title:'客户跟进到期'},{type:'leave',id:61,title:'学生请假待审批'}]
    };
    p.on('pageerror',error=>errors.push(error.message));
    await p.addInitScript(()=>sessionStorage.setItem('stuproject.auth.session',JSON.stringify({accessToken:'isolated-enterprise-dialog-test',expiresAt:Date.now()+3600000})));
    await p.route('**/api/v1/**',async route=>{
      const req=route.request(),u=new URL(req.url()),path=u.pathname,parts=path.split('/'),resource=path.startsWith('/api/v1/internal/student/')?parts[5]:parts[4];let data;
      if(path.endsWith('/admin/openapi.json'))return route.fulfill({json:{paths:{},components:{schemas:{}}}});
      if(path.endsWith('/admin/accounts/options'))data={positions:{老师:['employee','teacher']},departments:fixture.organization};
      else if(path.endsWith('/auth/me/access'))data={identity_type:identity,user_id:7,permissions};
      else if(path.endsWith('/me/permissions'))data={employee_id:7,permissions,is_admin:identity==='admin'};
      else if(req.method()!=='GET'){
        const body=req.postDataJSON();writes.push({path,method:req.method(),body,key:req.headers()['idempotency-key']});
        if(path=== '/api/v1/enterprise/customer/31'&&req.method()==='PUT'){
          if(conflict){conflict=false;customer.row_version=9;return route.fulfill({json:{code:409,message:'记录已更新，请重新读取',data:null}});}
          if(retry){retry=false;return route.fulfill({json:{code:503,message:'测试暂不可用，请重试',data:null}});}
          assert(body.expected_version===customer.row_version,'编辑未携带最新版本');customer={...customer,...body,row_version:customer.row_version+1};fixture.customer[0]=customer;data=customer;
        }else if(path==='/api/v1/enterprise/customer'&&req.method()==='POST'){
          assert(!Object.hasOwn(body,'customer_id')&&!Object.hasOwn(body,'expected_version'),'新增混入上一条记录');data={...body,customer_id:33,row_version:1};fixture.customer.push(data);
        }else if(path.endsWith('/phone-candidates')){data={items:[{customer_id:31,full_name:customer.full_name}],total:1};
        }else if(path.endsWith('/departments/3')){assert(body.expected_version===4,'部门版本错误');fixture.organization[0]={...fixture.organization[0],...body,row_version:5};data=fixture.organization[0];
        }else if(path.endsWith('/employees/9/roles')){assert(body.expected_version===6,'角色操作版本错误');fixture.employees[0]={...fixture.employees[0],...body,row_version:7};data=fixture.employees[0];
        }else if(path.endsWith('/followups/72/schedule')){assert(body.expected_version===following.row_version,'跟进版本错误');following={...following,...body,row_version:following.row_version+1};data=following;}
        else if(path==='/api/v1/enterprise/customer/31'&&req.method()==='DELETE'){fixture.customer=fixture.customer.filter(x=>x.customer_id!==31);data={customer_id:31,row_version:10};}
        else if(path.endsWith('/command'))data={token:'signed-test-receipt',action:'daily.create',target:{},fields:{report_date:'2026-10-18',submitted_content:'测试日报'},needs_clarification:false};
        else if(path.endsWith('/command/confirm'))data={report_id:19,row_version:1};
        else data={row_version:8,...body};
      }else{
        reads.push({path,query:u.search});
        if(path.endsWith('/customer/31/followups'))data={items:[following],total:1};
        else if(path.endsWith('/customer/31')){if(delayDetail){delayDetail=false;await new Promise(resolve=>setTimeout(resolve,350));}data=customer;}
        else if(path.endsWith('/customer/32'))data=fixture.customer[1];
        else if(path.endsWith('/assignments'))data={items:[],total:0};
        else if(/\/\d+$/.test(path)){
          const row=(fixture[resource]||[]).find(row=>Object.values(row).includes(Number(parts.at(-1))));
          data=row||{};
        }else data={items:fixture[resource]||[],total:(fixture[resource]||[]).length};
      }
      await route.fulfill({json:{code:0,message:'success',data}});
    });
    const dialog=p.getByRole('dialog');
    async function go(name){await p.goto('http://192.168.5.16:5173/enterprise/'+name+'.html');await p.locator('html[data-live-ready=true]').waitFor();}
    async function choose(resource,index=0){await p.locator('[data-resource="'+resource+'"] tbody button').nth(index).click();await dialog.getByRole('button',{name:'详情',exact:true}).waitFor();}
    async function tab(name){await dialog.locator('nav').getByRole('button',{name,exact:true}).click();}
    async function close(){await dialog.getByRole('button',{name:'关闭弹窗',exact:true}).click();await dialog.waitFor({state:'hidden'});}
    await go('customers');
    assert(await p.locator('#main-content details').count()===0,'页面仍逐接口展示折叠区');
    assert(await p.locator('[name=limit],[name=offset]').count()===0,'分页字段重新出现');
    await choose('customer');await tab('编辑');
    assert(await dialog.locator('[name=full_name]').inputValue()==='林同学','编辑未自动填入');
    assert(await dialog.locator('[name=expected_version],[name=customer_id]').count()===0,'内部编号或版本仍需手工填写');
    await dialog.locator('[name=full_name]').fill('林同学修订');
    await dialog.getByRole('button',{name:'保存',exact:true}).click();await dialog.getByText('测试暂不可用，请重试',{exact:true}).waitFor();
    await dialog.getByRole('button',{name:'保存',exact:true}).click();await dialog.getByText('保存成功，已读取最新记录。',{exact:true}).waitFor();
    assert(writes[0].key===writes[1].key&&writes[1].body.expected_version===3,'失败重试丢失幂等键或版本');
    assert(await p.locator('[data-resource=customer]').getByText('林同学修订',{exact:true}).count()===1,'列表未刷新');
    checks.push('组合弹窗编辑、隐藏内部字段、失败重试复用幂等键、保存刷新');
    await tab('编辑');conflict=true;await dialog.locator('[name=full_name]').fill('冲突修改');await dialog.getByRole('button',{name:'保存',exact:true}).click();
    await dialog.getByRole('button',{name:'重新读取记录',exact:true}).click();await tab('编辑');
    await dialog.locator('[name=full_name]').fill('刷新后修订');await dialog.getByRole('button',{name:'保存',exact:true}).click();await dialog.getByText('保存成功，已读取最新记录。',{exact:true}).waitFor();
    assert(writes.at(-1).body.expected_version===9,'冲突后仍使用旧版本');checks.push('409冲突重新读取最新版本');
    await tab('跟进记录');await dialog.getByRole('button',{name:'选择记录',exact:true}).click();await tab('调整跟进安排');
    await dialog.locator('[name=followup_status]').selectOption('done');await dialog.getByRole('button',{name:'保存',exact:true}).click();await dialog.getByText('保存成功，已读取最新记录。',{exact:true}).waitFor();
    assert(writes.at(-1).path.endsWith('/customer/31/followups/72/schedule'),'客户/跟进编号混淆');
    await tab('返回客户详情');await tab('编辑');assert(await dialog.locator('[name=full_name]').inputValue()==='刷新后修订','返回客户详情失败');
    checks.push('客户弹窗内跟进、调整安排及返回客户详情');
    await close();await p.getByRole('button',{name:'按电话查找客户',exact:true}).click();await dialog.locator('[name=phone]').fill('13800000000');
    await dialog.getByRole('button',{name:'提交',exact:true}).click();await dialog.getByRole('button',{name:'选择记录',exact:true}).click();await tab('编辑');await close();
    checks.push('电话查询结果直接进入客户组合弹窗');
    await p.getByRole('button',{name:'新增客户档案',exact:true}).click();
    assert(await dialog.locator('[name=full_name]').inputValue()==='','新增残留上一条数据');await dialog.locator('[name=full_name]').fill('新增测试客户');
    await dialog.getByRole('button',{name:'提交',exact:true}).click();await dialog.waitFor({state:'hidden'});assert(writes.at(-1).path.endsWith('/enterprise/customer'),'新增路径错误');
    checks.push('新增使用同款弹窗且不残留记录数据');
    delayDetail=true;await p.locator('[data-resource=customer] tbody button').nth(0).click();await dialog.getByRole('button',{name:'关闭弹窗'}).click();
    await choose('customer',1);await tab('编辑');assert(await dialog.locator('[name=full_name]').inputValue()==='陈同学','异步返回污染另一条记录');await close();
    checks.push('快速关闭并选择另一条记录不会串数据');
    await choose('customer');await tab('归档客户');const beforeDelete=writes.length;
    await dialog.getByRole('button',{name:'确认归档客户',exact:true}).click();assert(writes.length===beforeDelete,'未确认就归档');
    await dialog.locator('.enterprise-confirmation input').check();await dialog.locator('[name=reason]').fill('测试归档');await dialog.getByRole('button',{name:'确认归档客户',exact:true}).click();await dialog.waitFor({state:'hidden'});
    checks.push('归档先确认，成功关闭弹窗并刷新列表');
    fixture.customer.unshift(customer);
    await go('organization');assert(await p.locator('.enterprise-list').count()===2,'部门和员工没有分组');
    await choose('departments');await tab('编辑');assert(await dialog.locator('[name=department_name]').inputValue()==='教务服务部','部门编辑映射错误');
    await dialog.locator('[name=department_name]').fill('教务服务部修订');await dialog.getByRole('button',{name:'保存',exact:true}).click();await dialog.getByText('保存成功，已读取最新记录。',{exact:true}).waitFor();await close();
    await choose('employees');await tab('调整角色');assert(await dialog.locator('.enterprise-role-option input:checked').count()===2,'角色未回填');
    await dialog.locator('[name=reason]').fill('确认角色');await dialog.getByRole('button',{name:'保存',exact:true}).click();await dialog.getByText('保存成功，已读取最新记录。',{exact:true}).waitFor();
    assert(Array.isArray(writes.at(-1).body.role_codes)&&writes.at(-1).body.role_codes.includes('teacher'),'角色未按数组提交');await close();
    checks.push('组织页面按部门/员工分组，角色操作组合到员工弹窗');
    await go('academics');await choose('academic-events');await tab('编辑');assert(await dialog.locator('[name=due_at]').inputValue()==='2026-10-20T10:00','北京时间回填错误');
    await dialog.locator('[name=reason]').fill('考试调整');await dialog.getByRole('button',{name:'保存',exact:true}).click();await dialog.getByText('保存成功，已读取最新记录。',{exact:true}).waitFor();
    assert(writes.at(-1).body.expected_event_version===4&&writes.at(-1).body.due_at.endsWith('+08:00'),'节点版本或北京时间提交错误');await close();
    checks.push('学业节点专用版本和北京时间往返');
    await go('daily-reports');await choose('daily-report',1);assert(await dialog.locator('nav').getByRole('button',{name:'编辑',exact:true}).count()===0,'本人写权限暴露他人日报修改');await close();
    await go('todos');await choose('todos');assert(await dialog.locator('h2').innerText()==='服务工单详情','工单待办未映射工单');await tab('添加处理记录');await close();
    await choose('todos',1);assert(await dialog.locator('h2').innerText()==='客户跟进详情','跟进待办未映射跟进');await tab('调整跟进安排');await close();
    await choose('todos',2);assert(await dialog.locator('h2').innerText()==='学生请假详情','请假待办未映射请假');await tab('审批请假');
    await dialog.locator('[name=decision]').selectOption('approved');await dialog.getByRole('button',{name:'保存',exact:true}).click();await dialog.getByText('保存成功，已读取最新记录。',{exact:true}).waitFor();
    assert(writes.at(-1).path.endsWith('/leave/61/decision')&&writes.at(-1).body.expected_version===5,'请假审批编号或版本错误');await close();
    checks.push('本人日报限制、工单/跟进/请假待办映射实际业务弹窗');
    await go('assistant');await p.getByRole('button',{name:'解析工作指令',exact:true}).click();await dialog.locator('[name=text]').fill('提交今天日报');
    await dialog.getByRole('button',{name:'提交',exact:true}).click();await dialog.getByRole('button',{name:'继续确认办理',exact:true}).click();
    assert(!writes.some(write=>write.path.endsWith('/command/confirm')),'指令预览提前写入');await dialog.getByRole('button',{name:'确认办理',exact:true}).click();await dialog.waitFor({state:'hidden'});
    assert(writes.at(-1).body.token==='signed-test-receipt','确认未带签名凭证');checks.push('智能指令预览与显式确认分开');
    permissions=['enterprise.customer.read'];await go('customers');assert(await p.getByRole('button',{name:'新增客户档案',exact:true}).count()===0,'无权限仍可新增');
    await choose('customer');assert(await dialog.locator('nav button').allTextContents().then(names=>names.every(name=>['详情','跟进记录'].includes(name))),'无权限仍可写入');await close();
    checks.push('操作按当前权限显示');
    permissions=['enterprise.score.read','enterprise.academic.write'];await go('courses');assert(await p.getByRole('button',{name:'新增课程',exact:true}).count()===1,'课程写权限未使用教务维护权限');
    permissions=['enterprise.score.read','enterprise.score.write'];await go('courses');assert(await p.getByRole('button',{name:'新增课程',exact:true}).count()===0,'成绩写权限错误暴露课程维护');
    checks.push('课程维护权限与后端教务授权一致');
    permissions=[...enterprise,...internal];await go('customers');await choose('customer');await tab('编辑');
    await p.screenshot({path:'D:/project/StuProject/.runtime/enterprise-dialog-desktop.png',fullPage:true});
    await p.setViewportSize({width:390,height:844});
    assert(await dialog.evaluate(el=>el.getBoundingClientRect().width<=innerWidth),'移动弹窗超出屏幕');
    assert(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth+1),'移动弹窗横向溢出');
    await p.screenshot({path:'D:/project/StuProject/.runtime/enterprise-dialog-mobile.png',fullPage:true});
    await p.keyboard.press('Escape');await dialog.waitFor({state:'hidden'});checks.push('桌面/手机弹窗布局、Escape关闭');
    for(const name of ['students','scores','courses','bindings','application-progress','leave-review','warnings','knowledge','tickets']){
      await go(name);assert(await p.locator('#main-content details').count()===0,name+'仍有接口折叠区');
    }
    checks.push('其余企业业务页面使用列表组合界面');
    identity='admin';fixture.employees[0].position_title='老师';delete fixture.employees[0].role_codes;
    await go('organization');await choose('employees');await tab('调整角色');
    assert(await dialog.locator('.enterprise-role-option input:checked').count()===2,'管理员未按受控职位映射显示角色');await close();
    await go('leave-review');assert(await p.locator('[data-resource="internal/leave"]').count()===0,'平台管理员错误获得老师审批入口');
    checks.push('平台管理员职位映射及学生协作身份限制');
    assert(!errors.length,errors.join('; '));
    return {passed:true,checks,writes:writes.length,realDatabaseWritten:false,errors};
  }catch(error){throw Error('已完成：'+checks.join('；')+'；失败：'+error.message);}
  finally{await context.close();}
}
