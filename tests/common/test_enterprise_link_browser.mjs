/** 在当前公共导航及隔离 API 下复用企业弹窗回归；不写真实数据库。 */
import assert from 'node:assert/strict';
import { readFile, mkdir } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { chromium } from '@playwright/test';
import { createServer } from 'vite';
const python=process.env.STUPROJECT_PYTHON||'D:/anaconda3/envs/SST/python.exe';
const generated=spawnSync(python,['-c',`import json,contextlib,io
with contextlib.redirect_stdout(io.StringIO()):
 from app.main import app
 from app.core.common.authorization import load_access_control
 payload={'schema':app.openapi(),'catalog':load_access_control()['navigation']}
print(json.dumps(payload))`],{encoding:'utf8',windowsHide:true,env:{...process.env,PYTHONUTF8:'1',PYTHONDONTWRITEBYTECODE:'1',PYTHONPATH:[process.cwd(),path.resolve('.runtime/backend-deps')].join(path.delimiter)}});
assert.equal(generated.status,0,generated.stderr);
const {schema,catalog}=JSON.parse(generated.stdout.trim().split('\n').at(-1));
function navigationFor(identity,permissions){
 const routes=Object.fromEntries(catalog.pages.filter(page=>(!page.identities||page.identities.includes(identity))&&
  (!page.any_permissions||page.any_permissions.some(permission=>permissions.includes(permission))))
  .map(page=>[page.route,{title:page.title,module:page.module,menu:page.menu}]));
 const modules=catalog.modules.flatMap(module=>{
  const pages=Object.entries(routes).filter(([,page])=>page.module===module.id&&page.menu!==false).map(([route,page])=>({route,...page}));
  return pages.length?[{...module,pages,entry:pages[0].route}]:[];
 });
 return {routes,modules};
}
const server=await createServer({configFile:'vite.config.mjs',server:{host:'127.0.0.1',port:4174,strictPort:true,open:false}});
await server.listen();
const browser=await chromium.launch({channel:'msedge',headless:true});
const newContext=browser.newContext.bind(browser);
browser.newContext=async options=>{
 const context=await newContext(options);
 await context.route('**/openapi.json',route=>route.fulfill({json:schema}));
 return context;
};
await mkdir('.runtime/enterprise-review',{recursive:true});
try{
 let source=await readFile('tests/enterprise/enterprise_workspace.browser.js','utf8');
 source=source.replaceAll('http://192.168.5.16:5173','http://127.0.0.1:4174')
  .replaceAll('D:/project/StuProject/.runtime/','.runtime/enterprise-review/')
  .replace('data={identity_type:identity,user_id:7,permissions};',
   'data={identity_type:identity,user_id:7,display_name:"企业联动测试",permissions,navigation:navigationFor(identity,permissions)};');
 const run=Function('navigationFor','return ('+source+')')(navigationFor);
 const result=await run({context:()=>({browser:()=>browser})});
 console.log(JSON.stringify(result));
}finally{await browser.close();await server.close()}
