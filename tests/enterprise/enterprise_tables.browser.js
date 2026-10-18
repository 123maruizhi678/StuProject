// 验证企业表格文本单行省略、日期时间完整显示及无需水平滚动；不访问真实业务数据。
async (page) => {
  const context=await page.context().browser().newContext();
  const assert=(ok,message)=>{if(!ok)throw Error(message);};
  try{
    const p=await context.newPage(),errors=[],checks=[];
    p.on('pageerror',error=>errors.push(error.message));
    await p.addInitScript(()=>sessionStorage.setItem('stuproject.auth.session',JSON.stringify({accessToken:'isolated-table-layout',expiresAt:Date.now()+3600000})));
    const permissions=['customer.read','daily.read','organization.read','knowledge.read'].map(key=>'enterprise.'+key);
    const longText='这是一段需要省略显示但弹窗保留完整内容的业务记录'.repeat(12);
    const fixtures={
      customer:{customer_id:31,customer_no:'KH-000031',full_name:'长客户姓名'.repeat(12),education_level:'本科',target_country_code:'GB',status:'contacting',source_channel:'local',created_at:'2026-10-18T02:00:00.123456',row_version:2},
      'daily-report':{daily_report_id:4,report_date:'2026-10-18',employee_id:7,department_id_at_submit:1,submitted_content:longText,ai_summary:'辅助摘要'.repeat(20),submitted_at:'2026-10-18T02:00:00.123456',status:'submitted',row_version:2},
      employees:{employee_id:9,employee_no:'EMP-000009',full_name:'周老师',department_id:1,position_title:'顾问'.repeat(20),work_email:'very-long-email-address-for-layout-check@example.test',status:'active',row_version:2},
      organization:{department_id:1,department_code:'EDU',department_name:'教务部门',function_description:longText,status:'active',created_at:'2026-10-18T02:00:00.123456',row_version:2},
      knowledge:{knowledge_id:13,title:'业务制度名称'.repeat(12),entry_code:'DOC-000013',entry_type:'document',content_text:longText,source_reference:'https://example.test/'+('long-reference-'.repeat(15)),status:'published',row_version:2},
      followups:{followup_id:72,customer_id:31,employee_id:7,content:longText,channel:'电话',followup_at:'2026-10-18T02:00:00.123456',next_followup_at:'2026-10-20T02:00:00.123456',followup_status:'pending',row_version:2},
    };
    await p.route('**/api/v1/**',route=>{
      const path=new URL(route.request().url()).pathname,resource=path.split('/')[4];let data;
      if(path.endsWith('/auth/me/access'))data={identity_type:'employee',user_id:7,permissions};
      else if(path.endsWith('/me/permissions'))data={employee_id:7,permissions};
      else if(path.endsWith('/followups'))data={items:[fixtures.followups],total:1};
      else{const row=fixtures[resource]||{};data=/\/\d+$/.test(path)?row:{items:[row],total:1};}
      return route.fulfill({json:{code:0,data}});
    });
    async function checkTables(root){
      const result=await root.locator('.enterprise-table-wrap').evaluateAll(wrappers=>wrappers.map(wrap=>{
        const box=wrap.getBoundingClientRect(),table=wrap.querySelector('table');
        const buttons=[...wrap.querySelectorAll('tbody button')];
        const values=[...wrap.querySelectorAll('.enterprise-cell-value')];
        const textEllipsis=values.filter(value=>!value.classList.contains('enterprise-cell-time')).every(value=>{
          const style=getComputedStyle(value);return style.whiteSpace==='nowrap'&&style.textOverflow==='ellipsis'&&style.overflowX==='hidden'&&value.getBoundingClientRect().height<=parseFloat(style.lineHeight)+1;
        });
        const timesComplete=values.filter(value=>value.classList.contains('enterprise-cell-time')).every(value=>{
          const style=getComputedStyle(value),range=document.createRange();range.selectNodeContents(value);
          const box=value.getBoundingClientRect();return style.overflowX==='visible'&&style.textOverflow!=='ellipsis'&&[...range.getClientRects()].every(r=>r.left>=box.left-1&&r.right<=box.right+1&&r.top>=box.top-1&&r.bottom<=box.bottom+1);
        });
        return {scrollWidth:wrap.scrollWidth,clientWidth:wrap.clientWidth,scrollLeft:wrap.scrollLeft,
          tableWidth:table.getBoundingClientRect().width,textEllipsis,timesComplete,
          actionVisible:buttons.every(button=>{const r=button.getBoundingClientRect();return r.left>=box.left-.5&&r.right<=box.right+.5&&r.right<=innerWidth+.5&&button.scrollWidth<=button.clientWidth+1;})};
      }));
      assert(result.length>0,'没有找到记录表格');
      for(const table of result)assert(table.scrollWidth<=table.clientWidth+1&&table.scrollLeft===0&&table.actionVisible&&table.textEllipsis&&table.timesComplete,'表格截断、时间显示或操作可见性异常：'+JSON.stringify(table));
      const submitted=root.locator('[data-field=submitted_at] .enterprise-cell-time');
      if(await submitted.count()){
        assert(await submitted.first().textContent()===fixtures['daily-report'].submitted_at,'时间值被截短或改写');
        if(p.viewportSize().width>=1440){const metrics=await submitted.first().evaluate(el=>({height:el.getBoundingClientRect().height,line:parseFloat(getComputedStyle(el).lineHeight),width:el.getBoundingClientRect().width,columns:[...el.closest('table').querySelectorAll('th')].map(th=>({label:th.textContent,width:th.getBoundingClientRect().width,style:th.style.width}))}));assert(metrics.height<=metrics.line+1,'宽屏时间仍折行：'+JSON.stringify(metrics));}
      }
      return result.length;
    }
    for(const width of [1440,390]){
      await p.setViewportSize({width,height:1000});
      for(const [name,key]of [['customers','customer'],['daily-reports','daily-report'],['organization','employees'],['knowledge','knowledge']]){
        await p.goto('http://192.168.5.16:5173/enterprise/'+name+'.html');await p.locator('html[data-live-ready=true]').waitFor();
        const count=await checkTables(p.locator('#main-content'));
        const button=p.locator('[data-resource="'+key+'"] tbody button').first();await button.click();
        const dialog=p.getByRole('dialog');await dialog.locator('dl').first().waitFor();
        if(key==='daily-report')assert(await dialog.getByText(longText,{exact:true}).count()===1,'弹窗未保留完整工作内容');
        if(key==='customer'){
          await dialog.locator('nav').getByRole('button',{name:'跟进记录',exact:true}).click();await dialog.locator('tbody button').waitFor();
          await checkTables(dialog);await dialog.locator('tbody button').click();await dialog.locator('h2').filter({hasText:'客户跟进详情'}).waitFor();
        }
        await dialog.getByRole('button',{name:'关闭弹窗'}).click();
        checks.push({width,page:name,tables:count,selectionClickable:true});
      }
    }
    for(const width of [1920,1024,768,320]){
      await p.setViewportSize({width,height:1000});await p.goto('http://192.168.5.16:5173/enterprise/daily-reports.html');await p.locator('html[data-live-ready=true]').waitFor();
      await checkTables(p.locator('#main-content'));checks.push({width,page:'daily-reports',noHorizontalScroll:true});
    }
    await p.setViewportSize({width:1440,height:1000});await p.reload();await p.locator('html[data-live-ready=true]').waitFor();
    await p.screenshot({path:'D:/project/StuProject/.runtime/enterprise-compact-tables-desktop.png',fullPage:true});
    await p.setViewportSize({width:390,height:844});await p.screenshot({path:'D:/project/StuProject/.runtime/enterprise-compact-tables-mobile.png',fullPage:true});
    assert(!errors.length,errors.join('; '));return {passed:true,checks,realDatabaseWritten:false,errors};
  }finally{await context.close();}
}
