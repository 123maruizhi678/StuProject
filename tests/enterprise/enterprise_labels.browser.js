// 中文字段显示及原始提交字段隔离验证；所有业务 API 均使用虚构数据。
async (page) => {
  const context=await page.context().browser().newContext();
  const assert=(ok,message)=>{if(!ok)throw Error(message);};
  try{
    const p=await context.newPage(),writes=[],errors=[],checks=[];
    p.on('pageerror',error=>errors.push(error.message));
    await p.addInitScript(()=>sessionStorage.setItem('stuproject.auth.session',JSON.stringify({accessToken:'isolated-field-labels',expiresAt:Date.now()+3600000})));
    const grants=['customer.read','customer.update','ticket.read','knowledge.read','knowledge.manage','todo.read_own','notification.read_own','command','query','academic.write','student.read'].map(key=>'enterprise.'+key);
    const customer={customer_id:31,customer_no:'CUS31',full_name:'中文字段测试客户',row_version:3,status_changed_at:'2026-10-18T02:00:00',
      last_followup_at:'2026-10-17T03:00:00',external_updated_at:null,is_archived:false};
    const ticket={ticket_id:12,ticket_no:'TK12',row_version:2,first_response_at:null,response_due_at:'2026-10-20T02:00:00',resolution_due_at:'2026-10-21T02:00:00',
      records:[{ticket_record_id:1,record_type:'note',content:'嵌套记录保留',employee_id:9,created_at:'2026-10-18T02:00:00',phone_ciphertext:'must-stay-hidden',
        sla_snapshot:{policy_version:'v1',started_at:'2026-10-18T02:00:00',clock:'continuous',hours:{response_hours:24,resolution_hours:72}}}]};
    const knowledge={knowledge_id:13,title:'制度资料',version_no:2,index_status:'ready',external_document_id:'doc-13',reviewer_employee_id:9,row_version:2};
    const warning={id:62,student_id:1,trigger_reason:'测试关怀',risk_level:'high',follower_status:'pending',acknowledged_at:null,handling_result:null,row_version:2};
    await p.route('**/api/v1/**',async route=>{
      const req=route.request(),u=new URL(req.url()),path=u.pathname;let data;
      if(path.endsWith('/auth/me/access'))data={identity_type:'employee',user_id:7,permissions:[...grants,'student.warning.read']};
      else if(path.endsWith('/me/permissions'))data={permissions:grants};
      else if(req.method()!=='GET'){
        const body=req.postDataJSON();writes.push({path,body});
        if(path.endsWith('/command'))data={action:'customer.update',target:{id:31},fields:{full_name:'字段预览',expected_version:3},needs_clarification:false,expires_in:300,token:'hidden-receipt'};
        else data={...customer,...body,row_version:4};
      }else{
        const row=path.includes('/tickets')?ticket:path.includes('/knowledge')?knowledge:path.includes('/warnings')?warning:customer;
        data=/\/\d+$/.test(path)?row:{items:[row],total:1};
      }
      await route.fulfill({json:{code:0,data}});
    });
    const dialog=p.getByRole('dialog');
    async function open(pageName,resource){
      await p.goto('http://192.168.5.16:5173/enterprise/'+pageName+'.html');await p.locator('html[data-live-ready=true]').waitFor();
      await p.locator('[data-resource="'+resource+'"] tbody button').first().click();await dialog.locator('dl').first().waitFor();
      const labels=await dialog.locator('dt,label,legend,th').allTextContents();
      assert(labels.every(value=>!/[a-zA-Z]/.test(value)),'仍有英文字段：'+labels.filter(value=>/[a-zA-Z]/.test(value)).join(','));
      return labels;
    }
    const labels=await open('customers','customer');
    for(const value of ['状态变更时间','最近跟进时间','外部更新时间','是否归档'])assert(labels.includes(value),'缺少 '+value);
    assert(await dialog.locator('dd').filter({hasText:'CUS31'}).count()===1,'业务编号值被修改');
    await dialog.locator('nav').getByRole('button',{name:'编辑',exact:true}).click();await dialog.locator('[name=full_name]').fill('中文显示不改变请求字段');
    await dialog.getByRole('button',{name:'保存',exact:true}).click();await dialog.getByText('保存成功，已读取最新记录。',{exact:true}).waitFor();
    assert(writes.at(-1).body.full_name==='中文显示不改变请求字段'&&writes.at(-1).body.expected_version===3,'原始请求字段发生改变');
    assert(!Object.keys(writes.at(-1).body).some(key=>/[\u3400-\u9fff]/.test(key)),'中文名称被作为请求字段提交');checks.push('客户字段中文显示、编号值及英文提交字段保持正确');
    await open('tickets','tickets');assert(await dialog.getByText('嵌套记录保留',{exact:true}).count()===1,'嵌套处理记录丢失');
    assert(await dialog.getByText('must-stay-hidden',{exact:true}).count()===0,'嵌套敏感字段泄漏');checks.push('工单嵌套记录字段中文显示且继续隐藏敏感字段');
    await open('knowledge','knowledge');checks.push('知识资料字段中文显示');
    await open('warnings','internal/warnings');checks.push('学生关怀字段中文显示');
    await p.goto('http://192.168.5.16:5173/enterprise/assistant.html');await p.locator('html[data-live-ready=true]').waitFor();
    await p.getByRole('button',{name:'解析工作指令',exact:true}).click();await dialog.locator('[name=text]').fill('修改客户');await dialog.getByRole('button',{name:'提交',exact:true}).click();
    await dialog.getByRole('button',{name:'继续确认办理',exact:true}).waitFor();
    const previewLabels=await dialog.locator('dt').allTextContents();assert(previewLabels.includes('办理对象')&&previewLabels.includes('姓名')&&previewLabels.includes('有效时长（秒）'),'嵌套指令预览标签未翻译');
    assert(!previewLabels.some(label=>/[a-zA-Z]/.test(label)),'指令预览仍有英文字段');assert(!await dialog.getByText('hidden-receipt',{exact:true}).count(),'确认凭证被显示');checks.push('指令预览及嵌套确认内容的字段中文显示');
    assert(!errors.length,errors.join('; '));return {passed:true,checks,realDatabaseWritten:false,errors};
  }finally{await context.close();}
}
