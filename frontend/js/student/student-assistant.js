import {renderShell,studentPages,guestNotice,footer,icon,mountDialog,esc,toast} from '../system.js';
import {api,tokenStore} from './api.js';

const requested=document.body.dataset.page;
const page=studentPages.some(p=>p[0]===requested)?requested:'overview';
const title=studentPages.find(p=>p[0]===page)[1];
renderShell(page,title);
const root=document.getElementById('page-content');
root.innerHTML=guestNotice();

let currentAccess=null;
if(tokenStore.get()){
 api('auth/me/access').then(access=>{
  currentAccess=access;
  document.getElementById('account-name').textContent=(access.identity_type==='student'?'学生':'系统')+'账号 #'+access.user_id;
  document.getElementById('account-role').textContent=access.identity_type==='student'?'学生专属空间':'当前账号非学生身份';
  if(access.identity_type!=='student'){
   const notice=document.createElement('div');notice.className='inline-notice error';notice.textContent='当前登录的不是学生账号。请切换为学生账号后办理本人业务。';root.prepend(notice);
  }
 }).catch(error=>{
  document.getElementById('account-role').textContent=error.code===401?'登录状态已失效':'账号服务暂不可用';
  if(error.code===401){document.getElementById('account-name').textContent='重新登录';}
 });
}
document.getElementById('account-link').addEventListener('click',e=>{
 if(!tokenStore.get())return;
 e.preventDefault();const dialog=mountDialog('当前登录账号',`<div class="row"><span class="avatar">${icon('user')}</span><div><h3>${esc(currentAccess?'账号 #'+currentAccess.user_id:'当前登录账号')}</h3><p class="muted small">${esc(currentAccess?.identity_type==='student'?'学生身份':'当前权限由服务端实时校验')}</p></div></div><div class="form-actions"><button type="button" class="button secondary" id="sign-out">退出登录 ${icon('logout')}</button></div>`);
 dialog.querySelector('#sign-out').onclick=()=>{tokenStore.clear();location.assign('/static/student/login.html');};
});
try{const module=await import('./'+page+'.js');await module.render(root);}catch(error){toast('页面暂时无法完成加载，请刷新后重试。',true);console.error('student page initialization failed',error.name);}
root.insertAdjacentHTML('beforeend',footer());
