// NODE_PATH=<temporary jsdom node_modules> node --experimental-vm-modules --test tests/student/workspace-enhancements.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const {JSDOM}=createRequire(import.meta.url)('jsdom');
const tick=()=>new Promise(resolve=>setTimeout(resolve,10));
const student=permissions=>({user_id:103,identity_type:'student',permissions});
async function harness(access,respond,page='student/chat.html'){
 const dom=new JSDOM(`<aside><a class="rail-link" href="/student/chat.html">聊天</a><a class="rail-link" href="/student/leave.html">请假</a><a class="rail-link" href="/enterprise/enterprise.html">企业</a></aside><div class="top-actions"><a href="/student/notifications.html"><span class="unread-dot"></span></a><span class="user-chip"><span class="avatar">林</span><span class="user-name">账号</span></span></div><main id="main-content"><div class="page-heading"><h1>学生服务</h1></div></main>`,{url:'http://localhost/'+page,runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window,requests=[],timers=[],cache=new Map();
 w.fetch=async(url,options={})=>{requests.push({url,options});const data=await respond(url,options);return {ok:true,status:200,json:async()=>url==='/openapi.json'?data:{code:0,data}};};
 w.setInterval=fn=>{timers.push(fn);return timers.length;};w.clearInterval=()=>{};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
 const context=dom.getInternalVMContext();
 async function load(file){file=path.resolve(file);if(cache.has(file))return cache.get(file);const module=new vm.SourceTextModule(await fs.readFile(file,'utf8'),{context,identifier:file,importModuleDynamically:async(spec,parent)=>{const imported=await load(path.resolve(path.dirname(parent.identifier),spec));if(imported.status!=='evaluated')await imported.evaluate();return imported;}});cache.set(file,module);await module.link((spec,parent)=>load(path.resolve(path.dirname(parent.identifier),spec)));return module;}
 async function run(file){const module=await load('frontend/js/'+file);if(module.status!=='evaluated')await module.evaluate();return module.namespace;}
 const common=await run('common/api.js');common.saveSession({access_token:'test-token',token_type:'bearer',expires_in:3600});(await run('student/access.js')).setAccess(access);
 return {w,dom,run,requests,timers,cache,common,main:w.document.querySelector('main'),close(){w.dispatchEvent(new w.Event('pagehide'));w.close();}};
}

test('student name and menus use real profile and permissions; unread updates and stops on identity change',async()=>{
 const access=student(['student.admin_service.read_own','student.profile.read_own','student.notification.read_own']);let total=3;
 const h=await harness(access,url=>url.includes('/profile')?{full_name:'真实同学'}:{items:[],total},'student/leave.html');
 try{const workspace=await h.run('student/workspace-enhancements.js');assert.equal(await workspace.initializeStudentWorkspace({access,main:h.main,page:'student/leave.html'}),false);await tick();assert.equal(h.w.document.querySelector('.user-name').textContent,'真实同学');assert.equal(h.w.document.querySelector('a[href="/student/chat.html"]').hidden,true);assert.equal(h.w.document.querySelector('a[href="/enterprise/enterprise.html"]').hidden,false);const badge=h.w.document.querySelector('.student-unread-count');assert.equal(badge.textContent,'3');total=0;h.w.dispatchEvent(new h.w.Event('student:notifications-changed'));await tick();assert.equal(badge.hidden,true);total=120;await h.timers[0]();assert.equal(badge.textContent,'99+');h.common.clearSession();h.w.dispatchEvent(new h.w.Event('auth:changed'));const count=h.requests.length;await h.timers[0]();assert.equal(h.requests.length,count);assert.equal(badge.hidden,true);}finally{h.close();}
});

test('operation filtering hides unavailable writes and rejects nonstudent identities',async()=>{
 const access=student(['student.admin_service.read_own']);const h=await harness(access,()=>({}));try{const {filterStudentOperations}=await h.run('student/workspace-enhancements.js');const operations=[{path:'/api/v1/student/leave',method:'GET'},{path:'/api/v1/student/leave',method:'POST'},{path:'/api/v1/student/leave/{id}',method:'DELETE'}];assert.equal(filterStudentOperations(operations,access).length,1);assert.equal(filterStudentOperations(operations,{...access,identity_type:'employee'}).length,0);}finally{h.close();}
});

test('history restores current account, paginates, and does not restore old confirmation buttons',async()=>{
 const access=student(['student.chat']);let blocked=false;const items=Array.from({length:25},(_,i)=>({message:'message-'+i,answer:'answer-'+i,had_action:true}));
 const h=await harness(access,url=>url.includes('/sessions/')?{items:url.includes('offset=20')?items.slice(0,5):items.slice(5),total:25,blocked,conversation_token:blocked?null:'fresh-token'}:{items:[{session_id:'own',title:'Conversation',updated_at:'2026-10-18T01:00:00Z'}],total:1});
 try{h.w.sessionStorage.setItem('stuproject.student.active-chat.103','own');await (await h.run('student/chat.js')).render(h.main);assert.match(h.main.querySelector('#chat-log').textContent,/message-5/);assert.equal(h.main.querySelector('#confirm-chat-action'),null);h.main.querySelector('#older-messages').click();await tick();assert.match(h.main.querySelector('#chat-log').firstElementChild.textContent,/message-0/);blocked=true;h.main.querySelector('#reload-chat').click();await tick();assert.equal(h.main.querySelector('#chat-message').disabled,true);blocked=false;h.main.querySelector('#reload-chat').click();await tick();assert.equal(h.main.querySelector('#chat-message').disabled,false);assert.equal(h.requests.filter(r=>r.options.method==='POST').length,0);}finally{h.close();}
});

test('continued chat uses recovered credential; unknown send results cannot trigger duplicate sends',async()=>{
 const access=student(['student.chat']);let fail=false;
 const h=await harness(access,(url,options)=>{if(url.endsWith('/student/chat')){if(fail)throw Error('timeout');return {session_id:'own',answer:'new-answer',conversation_token:'next-token'};}if(url.includes('/sessions/'))return {items:[{message:'old',answer:'reply'}],total:1,blocked:false,conversation_token:'fresh-token'};return {items:[{session_id:'own',title:'Conversation',updated_at:'2026-10-18T01:00:00Z'}],total:1};});
 try{await(await h.run('student/chat.js')).render(h.main);const input=h.main.querySelector('#chat-message'),form=h.main.querySelector('#chat-form');input.value='Continue';form.dispatchEvent(new h.w.Event('submit',{cancelable:true}));await tick();await tick();const sent=h.requests.find(r=>r.url.endsWith('/student/chat'));assert.equal(JSON.parse(sent.options.body).conversation_token,'fresh-token');assert.match(h.main.querySelector('#chat-log').textContent,/new-answer/);fail=true;input.value='Unknown';form.dispatchEvent(new h.w.Event('submit',{cancelable:true}));await tick();assert.equal(input.disabled,true);const count=h.requests.length;form.dispatchEvent(new h.w.Event('submit',{cancelable:true}));await tick();assert.equal(h.requests.length,count);}finally{h.close();}
});

test('shared live entry keeps enterprise path free of student imports and requests',async()=>{
 const access={user_id:102,identity_type:'employee',permissions:[]};const h=await harness(access,url=>url==='/openapi.json'?{paths:{},components:{schemas:{}}}:access,'enterprise/enterprise.html');
 try{await h.run('workspace/live.js');assert.equal(h.w.document.documentElement.dataset.liveReady,'true');assert.equal(h.requests.some(r=>r.url.includes('/student/')),false);assert.equal([...h.cache.keys()].some(p=>p.endsWith('workspace-enhancements.js')),false);}finally{h.close();}
});

test('shared student entry dispatches to live conversation while retaining main heading and navigation',async()=>{
 const access=student(['student.chat']);const h=await harness(access,url=>url==='/openapi.json'?{paths:{},components:{schemas:{}}}:url.includes('/auth/me/access')?access:{items:[],total:0});
 try{await h.run('workspace/live.js');assert.equal(h.w.document.documentElement.dataset.liveReady,'true');assert.ok(h.main.querySelector('#chat-form'));assert.ok(h.main.querySelector('.page-heading'));assert.ok(h.w.document.querySelector('a[href="/enterprise/enterprise.html"]'));}finally{h.close();}
});
