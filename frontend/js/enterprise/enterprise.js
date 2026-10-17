import {$, text, request, setToken, hasToken, can} from './api.js';
import {resources} from './catalog.js';
import {icon} from './icons.js';

let me, currentKey;
const groups = [
  ['工作空间', ['overview','todos','assistant','notifications']],
  ['客户协作', ['customer','application-progress','tickets']],
  ['教务管理', ['students','courses','student-courses','scores','academic-events']],
  ['团队协作', ['daily-report','knowledge']],
  ['组织管理', ['employees','departments','student-bindings','operation-logs']]
];
const pages = new Map(resources.map(item=>[item.path.slice(1),item]));
pages.set('overview',{name:'工作概览'});
pages.set('assistant',{name:'智能助手',permission:['command','query','knowledge.read']});
const names={employee:'员工',consultant:'顾问',manager:'部门主管',teacher:'老师',academic:'教务',admin:'企业配置管理员'};
function allowed(page) {
  return !page.permission || (Array.isArray(page.permission) ? page.permission.some(p=>can(me,p)) : can(me,page.permission));
}
function menuOpen(open) {
  $('sidebar').classList.toggle('is-open',open);
  $('nav-backdrop').hidden=!open;
  $('toggle-nav').setAttribute('aria-expanded',String(open));
}
function selectPage() {
  if (!me) return;
  const key=location.hash.replace(/^#\/?/,'') || 'overview';
  const page=pages.get(key);
  if (!page || !allowed(page)) { location.replace('#/overview'); return; }
  if (key===currentKey) return;
  currentKey=key;
  $('page-title').textContent=page.name;
  document.title=page.name+' · 企业管理';
  // 新页面使用新的容器，移除上一页的文档及子框架历史，避免一次后退落到旧内容。
  const frame=document.createElement('iframe');
  frame.id='module-frame';frame.name='enterprise-module';frame.title=page.name;
  frame.referrerPolicy='same-origin';frame.src='/static/enterprise/pages/'+key+'.html';
  $('module-frame').replaceWith(frame);
  document.querySelectorAll('#navigation a').forEach(link=>{
    const active=link.dataset.page===key;
    link.classList.toggle('active',active);
    if(active)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');
  });
  menuOpen(false);
}
function buildNavigation() {
  $('navigation').replaceChildren();
  for (const [name,keys] of groups) {
    const visible=keys.filter(key=>allowed(pages.get(key)));
    if(!visible.length)continue;
    const group=text('div','','nav-group');
    group.append(text('p',name,'nav-caption'));
    for (const key of visible) {
      const link=text('a','','nav-link');link.href='#/'+key;link.dataset.page=key;
      const iconName=key==='operation-logs'?'audit':key==='daily-report'?'todos':key;
      link.append(icon(iconName),text('span',pages.get(key).name));group.append(link);
    }
    $('navigation').append(group);
  }
  if(me.is_admin){const link=text('a','账户管理 ↗','nav-link');link.href='/admin/accounts';$('navigation').append(link);}
}
function reset() {
  setToken(null);me=null;currentKey=null;
  $('module-frame').src='about:blank';$('workspace').hidden=true;$('login').hidden=false;
}
async function start() {
  const access=await request('/api/v1/auth/me/access');
  if(!['employee','admin'].includes(access.identity_type))throw Error('企业工作台仅对员工和管理员开放。');
  me=await request('/me/permissions');
  $('identity').textContent=me.is_admin?'最高管理员 · 账号 '+me.user_id:'员工 '+me.employee_id+' · 部门 '+me.department_id;
  $('role-label').textContent=(me.roles || []).map(role=>names[role] || role).join(' / ');
  buildNavigation();$('login').hidden=true;$('workspace').hidden=false;
  $('notifications-shortcut').hidden=!can(me,'notification.read_own');selectPage();
}
$('login-form').onsubmit=async event=>{
  event.preventDefault();const button=event.submitter;button.disabled=true;$('login-error').textContent='';
  try {
    const form=event.currentTarget,input=new FormData(form);
    const result=await request('/api/v1/auth/login',{method:'POST',body:{username:input.get('username'),password:input.get('password')}});
    setToken(result.access_token);form.reset();await start();
  }catch(error){reset();$('login-error').textContent=error.message;}
  finally{button.disabled=false;}
};
$('logout').append(icon('logout'));$('toggle-nav').append(icon('menu'));$('notifications-shortcut').append(icon('notifications'));
$('logout').onclick=reset;
$('toggle-nav').onclick=()=>menuOpen(!$('sidebar').classList.contains('is-open'));
$('nav-backdrop').onclick=()=>menuOpen(false);
$('notifications-shortcut').onclick=()=>{location.hash='#/notifications';};
window.addEventListener('keydown',event=>{if(event.key==='Escape')menuOpen(false);});
window.addEventListener('hashchange',selectPage);
window.addEventListener('message',event=>{
  if(event.origin!==location.origin || event.source!==$('module-frame').contentWindow)return;
  if(event.data?.type==='enterprise:logout')reset();
  if(event.data?.type==='enterprise:navigate' && pages.has(event.data.key) && allowed(pages.get(event.data.key)))location.hash='#/'+event.data.key;
});
$('today').textContent=new Date().toLocaleDateString('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',weekday:'short'});
if(hasToken())start().catch(error=>{reset();$('login-error').textContent=error.message;});
