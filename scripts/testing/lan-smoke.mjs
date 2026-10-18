/** Browser smoke test against the real LAN address, default HTTP port and Vite proxy. */
import { chromium } from '@playwright/test';
import { mkdir,readFile,writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const base='http://192.168.5.12',dir='.runtime/lan-smoke';
await mkdir(dir,{recursive:true});
const fixture=JSON.parse(await readFile('.runtime/role-simulation/run.json','utf8'));
const browser=await chromium.launch({channel:'msedge',headless:true});
const checks=[],errors=[],requests=[];
try{
  for(const [name,username,password,landing]of [
    ['admin','root','root','/dashboard/dashboard.html'],
    ['student',fixture.accounts.student.username,fixture.accounts.student.password,'/student/student-assistant.html'],
  ]){
    const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
    page.on('pageerror',error=>errors.push({name,message:error.message}));
    page.on('request',request=>{
      if(new URL(request.url()).pathname.startsWith('/api/'))requests.push({name,url:request.url(),method:request.method()});
    });
    await page.goto(base+(name==='admin'?'/login.html':'/'));
    await page.locator('[name=username]').fill(username);
    await page.locator('[name=password]').fill(password);
    await page.getByRole('button',{name:'登录',exact:true}).click();
    await page.waitForURL(base+landing);
    await page.locator('html[data-live-ready=true]').waitFor();
    checks.push(name+' login and landing through LAN HTTP');
    const health=await context.request.get(base+'/health'),body=await health.json();
    assert.equal(health.status(),200);assert.equal(body.data.service,'StuProject');
    checks.push(name+' Vite health proxy');
    if(name==='student'){
      await page.goto(base+'/student/academics.html');
      await page.locator('html[data-live-ready=true]').waitFor();
      const card=page.locator('[data-operation="GET /api/v1/student/scores"]');
      const result=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/v1/student/scores');
      await card.evaluate(n=>n.open=true);
      const scores=await (await result).json();assert.equal(scores.code,0);
      assert.equal(scores.data.items.find(row=>row.score_id===fixture.ids.score).score_value,91);
      checks.push('student real MySQL score 91 through LAN UI');
      // Re-mark an already read notification: exercise a real write without
      // creating another fixture or changing an unfinished business workflow.
      await page.goto(base+'/student/notifications.html');
      await page.locator('html[data-live-ready=true]').waitFor();
      const read=page.locator('[data-operation="POST /api/v1/student/notifications/{notification_id}/read"]');
      await read.evaluate(n=>n.open=true);
      await read.locator('[name=notification_id]').fill(String(fixture.ids.notification));
      const written=page.waitForResponse(response=>response.request().method()==='POST'&&new URL(response.url()).pathname==='/api/v1/student/notifications/'+fixture.ids.notification+'/read');
      await read.getByRole('button',{name:'确认提交',exact:true}).click();
      const receipt=await written;assert.equal((await receipt.json()).code,0);
      assert.match(receipt.request().headers()['idempotency-key'],/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
      await read.locator('.live-status').filter({hasText:'操作成功'}).waitFor();
      checks.push('real LAN UI write with secure UUID fallback and Vite proxy');
    }else{
      await page.goto(base+'/admin/accounts.html');
      await page.locator('html[data-live-ready=true]').waitFor();
      if(!await page.locator('[data-operation="POST /api/v1/auth/register"]').count()){
        throw new Error('Admin page: '+await page.locator('main').innerText());
      }
      await page.locator('[data-operation="POST /api/v1/auth/register"]').waitFor({state:'attached'});
      checks.push('admin account management through LAN UI');
    }
    await page.screenshot({path:dir+'/'+name+'.png',fullPage:true});
    await context.close();
  }
  assert.deepEqual(errors,[]);assert.ok(requests.length>0);
  assert.ok(requests.every(request=>new URL(request.url).origin===base));
  checks.push('all browser API calls use LAN origin without explicit port');
  checks.push('no browser runtime errors');
  const result={status:'passed',base,checks,requests,errors,verified_at:new Date().toISOString()};
  await writeFile(dir+'/result.json',JSON.stringify(result,null,2));
  console.log(JSON.stringify({status:result.status,checks:checks.length,api_requests:requests.length}));
}finally{await browser.close();}
