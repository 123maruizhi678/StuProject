/** Regression: select the same real daily report after each edit, without reloading. */
import { chromium } from '@playwright/test';
import { readFile,writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const dir='.runtime/role-simulation',run=JSON.parse(await readFile(dir+'/run.json','utf8'));
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],calls=[];
page.on('pageerror',error=>errors.push(error.message));
try{
  await page.goto('http://127.0.0.1:5173/common/login.html');
  await page.locator('[name=username]').fill(run.accounts.employee.username);
  await page.locator('[name=password]').fill(run.accounts.employee.password);
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await page.waitForURL('**/enterprise/enterprise.html');
  await page.goto('http://127.0.0.1:5173/enterprise/daily-reports.html');
  await page.locator('html[data-live-ready=true]').waitFor();
  const list=page.locator('[data-operation="GET /api/v1/enterprise/daily-report"]');
  const edit=page.locator('[data-operation="PUT /api/v1/enterprise/daily-report/{report_id}"]');
  await list.locator('tbody tr').waitFor();
  assert.equal(await list.locator('tbody tr').count(),1);
  // Establish the current version from the actual frontend; no API fixture setup.
  await list.getByRole('button',{name:'选择记录',exact:true}).click();
  await edit.evaluate(n=>n.open=true);
  const initialVersion=Number(await edit.locator('[name=expected_version]').inputValue());
  let current=initialVersion;
  for(let round=1;round<=2;round++){
    assert.equal(Number(await edit.locator('[name=report_id]').inputValue()),run.ids.daily);
    assert.equal(Number(await edit.locator('[name=expected_version]').inputValue()),current);
    await edit.locator('[name=submitted_content]').fill('完成学生材料整理、课程说明与日常回访。页面连续修改核验第'+round+'次，版本'+current+'。');
    await edit.locator('[name=reason]').fill('真实业务页面连续修改回归核验');
    const mutation=page.waitForResponse(r=>r.request().method()==='PUT'&&new URL(r.url()).pathname==='/api/v1/enterprise/daily-report/'+run.ids.daily);
    const refreshed=page.waitForResponse(r=>r.request().method()==='GET'&&new URL(r.url()).pathname==='/api/v1/enterprise/daily-report');
    await edit.getByRole('button',{name:'确认提交',exact:true}).click();
    const response=await mutation,body=await response.json();assert.equal(body.code,0);
    calls.push({role:'employee',operation:'PUT /api/v1/enterprise/daily-report/{report_id}',code:body.code,http:response.status(),request_key:response.request().headers()['idempotency-key']});
    const query=await (await refreshed).json();assert.equal(query.code,0);
    current++;
    assert.equal(query.data.items.find(r=>r.daily_report_id===run.ids.daily).row_version,current);
    await page.waitForFunction(({version})=>{
      const table=document.querySelector('[data-operation="GET /api/v1/enterprise/daily-report"] table');
      const columns=[...table.querySelectorAll('thead th')].map(n=>n.textContent);
      const index=columns.indexOf('当前版本');
      return index>=0&&table.querySelector('tbody tr').children[index].textContent===String(version);
    },{version:current});
    await list.getByRole('button',{name:'选择记录',exact:true}).click();
    assert.equal(Number(await edit.locator('[name=expected_version]').inputValue()),current);
    await edit.getByRole('button',{name:'确认提交',exact:true}).waitFor({state:'visible'});
    await page.waitForFunction(()=>!document.querySelector('[data-operation="PUT /api/v1/enterprise/daily-report/{report_id}"] button[type=submit]').disabled);
  }
  assert.deepEqual(errors,[]);
  await page.screenshot({path:dir+'/employee-daily-after-consecutive-edits.png',fullPage:true});
  const result={status:'passed',initial_version:initialVersion,final_version:current,checks:['two real UI edits succeeded','list refreshed automatically after each edit','selecting the same record kept the newest version','no browser runtime errors'],calls};
  await writeFile(dir+'/ui-refresh.json',JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
}finally{await browser.close();}
