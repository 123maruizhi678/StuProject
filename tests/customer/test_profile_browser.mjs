/** 客户模块浏览器回归，所有网络业务请求均被模拟。 */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdir,writeFile } from 'node:fs/promises';
import { chromium,expect } from '@playwright/test';
import { createServer } from 'vite';

const output='C:/Users/Windows/Documents/ChatGPT/StuProject/customer_profile_revision/review';await mkdir(output,{recursive:true});
const script=String.raw`import json
from app.core.common.authorization import permissions_for
from app.core.common.navigation import navigation_for
from app.services.customer.profile_rules import catalog,evaluate_profile
p=permissions_for('admin');m={'customer.source.read','customer.result.read','customer.rule.read'}
sg=dict(full_name='演示小林',age=18,education_level='高中毕业',preferred_countries=['新加坡'],study_abroad_willingness=True,education_goal=True,family_support=True)
de=dict(full_name='演示小周',age=24,education_level='本科毕业',preferred_countries=['德国'],study_abroad_willingness=True,employment_goal=True,family_support=True,practical_ability=True,logical_ability=True,german_learning_willingness=True,german_expression_ability=True,closed_training_willingness=True,german_level='A2')
def row(f,index):return dict(facts=f,row_number=index,warnings=[],error=None,evaluation=evaluate_profile(f))
data=dict(catalog=catalog(),sg=row(sg,1),de=row(de,2),de36=evaluate_profile({**de,'age':36}),access={'admin':dict(user_id=101,identity_type='admin',display_name='演示管理员',permissions=sorted(p),navigation=navigation_for(p,'admin')),'manager':dict(user_id=102,identity_type='employee',roles=['manager'],display_name='演示主管',permissions=sorted(m),navigation=navigation_for(m,'employee'))})
print(json.dumps(data,ensure_ascii=False))`;
const run=spawnSync('C:/Users/Windows/anaconda3/python.exe',['-c',script],{encoding:'utf8',windowsHide:true,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1',PYTHONUTF8:'1',LOG_DIR:output+'/logs'}});assert.equal(run.status,0,run.stderr);const fixture=JSON.parse(run.stdout);
const server=await createServer({configFile:false,root:'frontend',appType:'mpa',cacheDir:output+'/vite-cache',server:{host:'127.0.0.1',port:4197,strictPort:true,open:false}});await server.listen();const base='http://127.0.0.1:4197';const browser=await chromium.launch({channel:'msedge',headless:true});const passed=[];
const KEY='stuproject.customer.document-profile.v1';
const initial={items:[fixture.sg,fixture.de],input_name:'合成客户.xlsx',created_at:new Date().toISOString(),rule_version:fixture.catalog.rule_version};
async function contextFor(role='admin',mobile=false){
 const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1440,height:1000},reducedMotion:'reduce',acceptDownloads:true});
 const state={offline:false,failAnalyze:false,empty:false,calls:[],writes:[]};
 await context.addInitScript(({key,data})=>{sessionStorage.setItem('stuproject.auth.session',JSON.stringify({accessToken:'fake-profile-token',expiresAt:Date.now()+3600000,accountName:'fixture'}));if(!sessionStorage.getItem(key))sessionStorage.setItem(key,JSON.stringify({ownerToken:'fake-profile-token',data}));},{key:KEY,data:initial});
 await context.route('**/api/**',async route=>{const req=route.request(),u=new URL(req.url()),p=u.pathname,method=req.method();const headers={'access-control-allow-origin':'*','access-control-allow-headers':'authorization,content-type,accept','access-control-allow-methods':'GET,POST,OPTIONS'};const ok=data=>route.fulfill({headers,json:{code:0,message:'success',data}});state.calls.push({path:p,port:u.port,method});
  if(method==='OPTIONS')return route.fulfill({status:204,headers});
  if(p.endsWith('/auth/me/access'))return ok(fixture.access[role]);
  if(method!=='GET'){assert.equal(role,'admin');state.writes.push({p,port:u.port,body:req.postData()});}
  if(p.includes('/profile')&&state.offline)return route.fulfill({status:503,headers,json:{code:503,message:'模拟客户服务不可用'}});
  if(p.endsWith('/profile/catalog')){assert.equal(u.port,'8003');return ok(fixture.catalog);}
  if(p.endsWith('/profile/analyze')){if(state.failAnalyze)return route.fulfill({status:400,headers,json:{code:400,message:'PDF 没有文字层，请先 OCR'}});return ok({...initial,success_count:2,failed_count:0,total:2,persisted:false});}
  if(p.endsWith('/profile/evaluate')){const body=req.postDataJSON();assert.equal(body.facts.age,36);assert.equal(typeof body.facts.family_support,'boolean');return ok(fixture.de36);}
  if(p.endsWith('/source/1/profile'))return ok({source:{id:1,file_name:'客户简历.pdf',status:'parsed',row_version:2},items:initial.items,total:2});
  if(p.endsWith('/source')&&method==='POST'){assert.notEqual(u.port,'8003');return ok({id:1,status:'pending',row_version:1});}
  if(p.endsWith('/source'))return ok({items:state.empty?[]:[{id:1,file_name:'客户简历.pdf',source_type:'pdf',status:'parsed',row_version:2,created_at:'2026-10-18T08:00:00'}],total:state.empty?0:1});
  throw new Error('Unexpected API: '+method+' '+u.href);
 });
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));return {context,page,state,errors};
}
async function visit(page,path){await page.goto(base+'/customer/'+path);await page.waitForSelector('html[data-customer-ready=true]');}
async function check(name,fn){await fn();passed.push(name);console.log('PASS',name);}
try{
 const {context,page,state,errors}=await contextFor();
 await check('九页面使用教育产品规则，无理财养老险示例',async()=>{for(const path of ['customer.html','extract.html','sources.html','source-detail.html?source_id=1','results.html','result-detail.html?row=1','rules.html','rule-detail.html?product=SG-EDUCATION','products.html']){await visit(page,path);await expect(page.locator('main h1')).toBeVisible();assert.doesNotMatch(await page.locator('main').innerText(),/稳健理财|养老险|布局预览/);}});
 await check('主页面优先录入，显示两个教育产品',async()=>{await visit(page,'customer.html');await expect(page.getByRole('button',{name:'开始双产品研判'})).toBeVisible();await expect(page.locator('main')).toContainText('新加坡国际本硕升学计划');await expect(page.locator('main')).toContainText('中德精英人才共建计划');await page.screenshot({path:output+'/profile-desktop.png',fullPage:true});});
 await check('文本一次研判同时返回两个产品，使用本机服务',async()=>{await page.getByRole('button',{name:'新加坡示例',exact:true}).click();await page.getByRole('button',{name:'开始双产品研判'}).click();await expect(page.locator('#input-feedback')).toContainText('完成 2 位');assert.equal(state.writes.at(-1).port,'8003');await expect(page.locator('#analysis-results tbody tr')).toHaveCount(2);});
 await check('保存来源仍使用原有后端，避免改变其他模块连接',async()=>{await page.getByRole('button',{name:'保存本次原始资料'}).click();await expect(page.locator('#save-feedback')).toContainText('已保存');assert.notEqual(state.writes.at(-1).port,'8003');});
 await check('上传切换、模板下载、真实文件表单',async()=>{await page.getByRole('button',{name:'上传资料',exact:true}).click();await expect(page.locator('textarea[name=text]')).toBeDisabled();const download=page.waitForEvent('download');await page.getByRole('button',{name:'下载 Excel / CSV 表头模板'}).click();assert.match((await download).suggestedFilename(),/模板.csv/);await page.locator('input[type=file]').setInputFiles({name:'客户.csv',mimeType:'text/csv',buffer:Buffer.from('姓名,年龄,学历\n甲,18,高中毕业')});await page.getByRole('button',{name:'开始双产品研判'}).click();await expect(page.locator('#input-feedback')).toContainText('完成 2 位');assert.match(state.writes.at(-1).body,/客户.csv/);});
 await check('扫描 PDF 错误可见，失败不显示假成功',async()=>{state.failAnalyze=true;await page.getByRole('button',{name:'开始双产品研判'}).click();await expect(page.locator('#input-feedback')).toContainText('OCR');await expect(page.locator('#analysis-results tbody')).toHaveCount(0);state.failAnalyze=false;});
 await check('结果详情有路径、依据和 B1 阶段说明',async()=>{await visit(page,'result-detail.html?row=1');await expect(page.locator('main')).toContainText('A2');await expect(page.locator('main')).toContainText('取得德语 B1');await expect(page.locator('main')).toContainText('核对项目');assert.doesNotMatch(await page.locator('main').innerText(),/匹配度.*%|录取概率/);await page.screenshot({path:output+'/profile-result.png',fullPage:true});});
 await check('补充核实信息后，两个产品重新研判',async()=>{await page.getByRole('button',{name:'核对 / 补充事实后重判'}).click();await page.getByRole('spinbutton',{name:'年龄',exact:true}).fill('36');await page.getByRole('button',{name:'确认事实并重新研判两个产品'}).click();await expect(page.getByRole('dialog')).toHaveCount(0);await expect(page.locator('main')).toContainText('暂不符合目标画像');await expect(page.locator('main')).toContainText('人工核实信息');});
 await check('导出包含两个产品',async()=>{await visit(page,'results.html');const download=page.waitForEvent('download');await page.getByRole('button',{name:'导出双产品结果'}).click();assert.equal((await download).suggestedFilename(),'两个教育产品画像研判.csv');});
 await check('规则解释明确近似年龄与非评分口径',async()=>{await visit(page,'rules.html');await expect(page.locator('main')).toContainText('大约');await expect(page.locator('main')).toContainText('不输出虚构匹配分数');await expect(page.locator('main')).toContainText('18—35');});
 await check('已有来源可读取并按两个产品实时查看',async()=>{await visit(page,'source-detail.html?source_id=1');await expect(page.locator('main')).toContainText('演示小林');await page.getByRole('button',{name:'按两个产品查看结果'}).click();await page.waitForURL('**/results.html');await page.waitForSelector('html[data-customer-ready=true]');await expect(page.locator('#analysis-results tbody tr')).toHaveCount(2);});
 await check('空来源和无编号详情提供可操作入口',async()=>{state.empty=true;await visit(page,'sources.html');await expect(page.locator('.cw-empty')).toContainText('暂无已保存资料');state.empty=false;await visit(page,'source-detail.html');await expect(page.locator('.cw-empty')).toContainText('请先选择来源');});
 await check('服务中断可重试，不回退到旧金融产品',async()=>{state.offline=true;await visit(page,'customer.html');await expect(page.getByRole('alert')).toContainText('模拟客户服务不可用');state.offline=false;await page.getByRole('button',{name:'重新连接'}).click();await expect(page.getByRole('button',{name:'开始双产品研判'})).toBeVisible();});
 await check('客户输入作为文本显示，避免注入',async()=>{await page.evaluate(({key,data})=>{data.items[0].facts.full_name='<img src=x onerror="window.profileXss=1">';sessionStorage.setItem(key,JSON.stringify({ownerToken:'fake-profile-token',data}));},{key:KEY,data:initial});await visit(page,'results.html');await expect(page.locator('main')).toContainText('<img');assert.equal(await page.evaluate(()=>window.profileXss),undefined);});
 await check('本次结果缓存不会跨登录会话复用',async()=>{await page.evaluate(({key,data})=>sessionStorage.setItem(key,JSON.stringify({ownerToken:'a-different-session',data})),{key:KEY,data:initial});await visit(page,'results.html');await expect(page.locator('.cw-empty')).toContainText('还没有本次研判结果');});
 assert.deepEqual(errors,[]);await context.close();
 await check('只读主管没有提交、保存和更正入口',async()=>{const view=await contextFor('manager');for(const path of ['customer.html','results.html','result-detail.html?row=1']){await visit(view.page,path);await expect(view.page.getByRole('button',{name:/开始双产品研判|保存本次原始资料|核对 \/ 补充事实后重判/})).toHaveCount(0);}assert.equal(view.state.writes.length,0);assert.deepEqual(view.errors,[]);await view.context.close();});
 await check('手机九页面没有整页横向溢出',async()=>{const view=await contextFor('admin',true);for(const path of ['customer.html','extract.html','sources.html','source-detail.html?source_id=1','results.html','result-detail.html?row=1','rules.html','rule-detail.html?product=DE-VOCATIONAL','products.html']){await visit(view.page,path);assert.ok(await view.page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),path);}await visit(view.page,'customer.html');await view.page.getByRole('button',{name:'打开导航'}).click();await expect(view.page.locator('body')).toHaveClass(/rail-open/);await view.page.keyboard.press('Escape');await expect(view.page.locator('body')).not.toHaveClass(/rail-open/);await view.page.screenshot({path:output+'/profile-mobile.png',fullPage:true});assert.deepEqual(view.errors,[]);await view.context.close();});
 await writeFile(output+'/browser-results.json',JSON.stringify({passed:passed.length,checks:passed},null,2));console.log('Customer profile browser checks:',passed.length);
}finally{await browser.close();await server.close();}
