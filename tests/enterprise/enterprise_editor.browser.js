// 加载真实独立页面，隔离上下文拦截API；不读取凭据、不写业务库。
async (page) => {
  const context=await page.context().browser().newContext({viewport:{width:1440,height:1000}});
  try{
    const testPage=await context.newPage(),errors=[],writes=[],checks=[];
    const permissions=['score.read','score.write','score.void','daily.read','daily.write_own','knowledge.read','knowledge.manage','student.read','academic.write','customer.read','customer.update','progress.write','ticket.read','ticket.handle','todo.read_own','notification.read_own','organization.read','command','query'];
    const fixtures={
      scores:{score_id:91,student_id:3,employee_id:1,course_code:'DEMO_MATH',assessment_code:'DEMO_MIDTERM',score_value:86,max_score:100,status:'valid',row_version:7},
      'daily-report':{daily_report_id:92,employee_id:1,submitted_content:'测试日报正文',status:'submitted',row_version:2},
      customer:{customer_id:93,full_name:'测试客户',status:'new',row_version:3},
      knowledge:{knowledge_id:94,title:'测试知识',entry_type:'faq',question:'测试问题',answer:'测试答案',status:'draft',row_version:4},
      'academic-events':{id:95,student_id:3,title:'测试考试',due_at:'2026-10-20T02:00:00',event_status:'active',event_version:5},
      'application-progress':{id:96,student_id:3,stage_status:'pending',detail:'测试进度',row_version:6},
      tickets:{ticket_id:97,student_id:3,employee_id:1,status:'assigned',row_version:1}
    };
    let rejectWrite=false;
    testPage.on('pageerror',error=>errors.push(error.message));
    await testPage.addInitScript(()=>sessionStorage.setItem('enterprise.token','ui-regression-token'));
    await testPage.route('**/api/v1/**',async route=>{
      const request=route.request(),path=new URL(request.url()).pathname,resource=path.split('/')[4];let data;
      if(path.endsWith('/auth/me/access'))data={identity_type:'employee',user_id:7};
      else if(path.endsWith('/me/permissions'))data={employee_id:1,department_id:1,roles:['academic','teacher'],permissions:permissions.map(p=>'enterprise.'+p)};
      else if(request.method()!=='GET'){
        writes.push({path,body:request.postDataJSON(),key:request.headers()['idempotency-key']});
        if(rejectWrite)return route.fulfill({json:{code:409,message:'记录已变更，请刷新后重试。',data:null}});
        data=fixtures[resource]||{};
      }else data=/\/\d+$/.test(path)?fixtures[resource]:{items:fixtures[resource]?[fixtures[resource]]:[],total:fixtures[resource]?1:0};
      await route.fulfill({json:{code:0,message:'success',data}});
    });
    await testPage.goto('http://127.0.0.1:8000/enterprise#/scores');
    const frame=testPage.frameLocator('#module-frame');
    async function openEditor(tab,action='编辑'){
      await testPage.getByRole('link',{name:tab,exact:true}).click();
      await frame.locator('#page-title').getByText(tab,{exact:true}).waitFor();
      await frame.getByRole('button',{name:action,exact:true}).click();
      await frame.locator('#editor').waitFor({state:'visible'});
    }
    await openEditor('学生成绩');
    if(await frame.locator('[name="score_value"]').inputValue()!=='86')throw Error('成绩未回填');
    if(await frame.locator('[name="reason"]').evaluate(el=>el.tagName)!=='TEXTAREA')throw Error('更正原因不是文本域');
    await frame.locator('[name="score_value"]').fill('95');await frame.locator('[name="reason"]').fill('测试成绩更正');
    await frame.locator('#edit-form').getByRole('button',{name:'保存',exact:true}).click();
    await frame.locator('#editor').waitFor({state:'hidden'});
    const write=writes[0];
    if(writes.length!==1||write.path!=='/api/v1/enterprise/scores/91'||write.body.expected_version!==7||write.body.score_value!==95||write.body.max_score!==100||write.body.reason!=='测试成绩更正'||!write.key)throw Error('成绩保存目标或参数不正确');
    checks.push('成绩回填、更正原因、版本、幂等键和保存请求通过');
    for(const [tab,action]of [['员工日报','编辑'],['客户管理','编辑'],['知识资料','编辑'],['学业节点','编辑'],['申请进度','编辑'],['投诉工单','人工回应'],['学生成绩','作废']]){
      await openEditor(tab,action);await frame.locator('#close-editor').click();checks.push(tab+action+'弹窗通过');
    }
    rejectWrite=true;await openEditor('学生成绩');await frame.locator('[name="reason"]').fill('并发修改测试');
    await frame.locator('#edit-form').getByRole('button',{name:'保存',exact:true}).click();
    await frame.locator('#edit-error').getByText('记录已变更，请刷新后重试。',{exact:true}).waitFor();
    if(!await frame.locator('#editor').isVisible())throw Error('写入失败时编辑内容丢失');
    await frame.locator('#close-editor').click();checks.push('并发冲突提示并保留表单通过');
    await frame.getByRole('button',{name:'查看',exact:true}).click();await frame.locator('#detail-dialog').waitFor({state:'visible'});
    await testPage.getByRole('link',{name:'客户管理',exact:true}).click();await frame.locator('#page-title').getByText('客户管理',{exact:true}).waitFor();
    if(await frame.locator('#detail-dialog').isVisible())throw Error('上一模块详情残留');checks.push('切换模块卸载详情通过');
    if(errors.length)throw Error(errors.join('; '));
    return {passed:true,checks,uncaught_errors:errors,real_database_written:false};
  }finally{await context.close();}
}
