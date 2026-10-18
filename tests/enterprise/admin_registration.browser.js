// 管理员页面浏览器回归：真实HTML/JS，独立上下文拦截接口，不写业务库。
async (page) => {
  const context=await page.context().browser().newContext();
  try {
    const testPage=await context.newPage(),errors=[],writes=[],accounts=[{user_id:1,username:'admin',identity_type:'admin'}];
    let failFirst=true;
    testPage.on('pageerror',e=>errors.push(e.message));
    await testPage.addInitScript(()=>sessionStorage.setItem('enterprise.token','registration-browser-test'));
    await testPage.route('**/api/v1/**',async route=>{
      const request=route.request(),path=new URL(request.url()).pathname;let data;
      if(path.endsWith('/auth/me/access'))data={user_id:1,identity_type:'admin',permissions:['account.manage']};
      else if(path.endsWith('/accounts/options'))data={initial_password:'123456',positions:{普通员工:['employee'],部门主管:['employee','manager']},departments:[{department_id:1,department_name:'测试部门'}],today_beijing:'2026-10-17'};
      else if(path.endsWith('/auth/register')){
        const body=request.postDataJSON();writes.push({body,key:request.headers()['idempotency-key']});
        if(failFirst){failFirst=false;return route.fulfill({json:{code:503,message:'测试临时失败',data:null}});}
        data={user_id:100+accounts.length,username:body.username,identity_type:body.identity_type,employee_id:body.identity_type==='employee'?20:null,student_id:body.identity_type==='student'?(body.student_id||30):null,customer_id:body.identity_type==='customer'?40:null,department_id:body.identity_type==='admin'?null:1,role_codes:body.identity_type==='employee'?['employee','manager']:[]};accounts.push(data);
      }else if(path.endsWith('/admin/accounts'))data={items:accounts,total:accounts.length};
      else if(path.endsWith('/admin/openapi.json'))return route.fulfill({json:{paths:{'/api/v1/auth/register':{post:{summary:'管理员统一注册'}}},components:{schemas:{AdminRegistration:{type:'object'}}}}});
      else data={};
      await route.fulfill({json:{code:0,message:'success',data}});
    });
    await testPage.goto('http://127.0.0.1:8000/admin/accounts');
    await testPage.locator('#workspace').waitFor({state:'visible',timeout:10000});
    const checks=[];
    await testPage.locator('#new-username').fill('browser-manager');
    for(const [name,value]of [['employee_no','E_DEMO'],['full_name','浏览器测试主管']])await testPage.locator('#profile-fields [name="'+name+'"]').fill(value);
    await testPage.locator('#profile-fields [name="position_title"]').selectOption({label:'部门主管'});
    const submit=testPage.getByRole('button',{name:'创建账户',exact:true});
    await submit.click();await testPage.locator('#register-error').getByText('测试临时失败',{exact:true}).waitFor();
    await submit.click();await testPage.locator('#registration-result').getByText('browser-manager',{exact:true}).waitFor();
    if(writes[0].key!==writes[1].key)throw Error('同一次失败重试未保持幂等键');
    if(writes[1].body.profile.position_title!=='部门主管'||writes[1].body.profile.department_id!==1)throw Error('员工职位或部门提交错误');
    checks.push('主管开户字段、职位映射输入与失败重试幂等键通过');
    for(const [identity,username]of [['student','browser-student'],['customer','browser-customer'],['admin','browser-admin']]){
      await testPage.locator('#identity-type').selectOption(identity);await testPage.locator('#new-username').fill(username);
      if(identity!=='admin'){
        await testPage.locator('#profile-fields [name="full_name"]').fill('浏览器测试档案');
        if(identity==='student')await testPage.locator('#profile-fields [name="student_no"]').fill('S_DEMO');
      }
      await submit.click();await testPage.locator('#registration-result').getByText(username,{exact:true}).waitFor();checks.push(identity+'新档案开户表单通过');
    }
    await testPage.locator('#identity-type').selectOption('student');await testPage.locator('#profile-mode').selectOption('existing');await testPage.locator('#new-username').fill('browser-existing-student');
    await testPage.locator('#profile-fields [name="student_id"]').fill('10');await submit.click();await testPage.locator('#registration-result').getByText('browser-existing-student',{exact:true}).waitFor();
    if(writes.at(-1).body.student_id!==10||writes.at(-1).body.profile)throw Error('绑定已有学生仍提交了新档案');checks.push('已有学生ID绑定通过');
    if(writes.some(w=>'password' in w.body||'role_codes' in w.body||w.body.profile&&'role_codes' in w.body.profile))throw Error('客户端提交了密码或自定义角色');
    await testPage.locator('#show-docs').click();await testPage.locator('#admin-docs').waitFor({state:'visible'});checks.push('管理员受保护文档展示通过');
    await testPage.setViewportSize({width:390,height:844});if(await testPage.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('手机页面出现横向溢出');checks.push('手机布局通过');
    await testPage.unroute('**/api/v1/**');
    await testPage.route('**/api/v1/**',route=>route.fulfill({json:{code:0,data:{user_id:2,identity_type:'employee',permissions:[]}}}));
    await testPage.reload();await testPage.locator('#denied').waitFor({state:'visible'});if(await testPage.locator('#workspace').isVisible())throw Error('非管理员显示了开户表单');checks.push('员工身份隐藏开户入口通过');
    if(errors.length)throw Error(errors.join('; '));
    return {passed:true,checks,uncaught_errors:errors,real_database_written:false};
  }finally{await context.close();}
}
