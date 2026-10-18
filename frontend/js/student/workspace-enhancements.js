import {api,tokenStore} from './api.js';
import {setAccess,can,studentPermissions} from './access.js';
const filePage={ 'student-assistant':'overview','leave-detail':'leave','ticket-detail':'tickets','action-preview':'chat' };
const pageKey=path=>{const name=path.split('/').at(-1).replace(/\.html$/,'');return filePage[name]||name;};
const allowed=(access,key)=>access.identity_type==='student'&&(studentPermissions[key]||[]).some(p=>access.permissions.includes(p));
export function filterStudentOperations(operations,access){
 const permissions=new Set(access.permissions||[]);
 const required=op=>{
  const path=op.path.replace('/api/v1/student/',''),method=op.method;
  if(path==='chat'||path.startsWith('chat/'))return 'student.chat';
  if(path==='actions/confirm')return 'student.action.confirm';
  if(path==='profile')return 'student.profile.read_own';
  if(path==='complaint')return 'service_ticket.create';
  if(path.startsWith('leave'))return method==='GET'?'student.admin_service.read_own':method==='DELETE'?'student.admin_service.withdraw_own':'student.admin_service.create';
  if(path.startsWith('tickets'))return method==='GET'?'service_ticket.read_own':path.endsWith('/reply')?'student.ticket.reply_own':path.endsWith('/rating')?'student.ticket.rate_own':'student.ticket.confirm_own';
  return {courses:'student.course.read_own',scores:'student.score.read_own',academic:'student.academic.read_own',progress:'student.progress.read_own',reminders:'student.reminder.manage_own',notifications:'student.notification.read_own',mental:'student.mental.create_own'}[path.split('/')[0]];
 };
 return access.identity_type==='student'?operations.filter(op=>permissions.has(required(op))):[];
}
export function startUnread(bell){
 const token=tokenStore.get();bell.querySelectorAll('.unread-dot').forEach(n=>n.remove());
 const badge=document.createElement('span');badge.className='student-unread-count';badge.hidden=true;badge.setAttribute('aria-hidden','true');bell.append(badge);
 let stopped=false,running=false;
 async function refresh(){if(stopped||running||document.hidden||tokenStore.get()!==token)return;running=true;
  try{const r=await api('student/notifications?limit=1&offset=0&unread=true');if(stopped||tokenStore.get()!==token)return;badge.textContent=r.total>99?'99+':String(r.total);badge.hidden=!r.total;bell.setAttribute('aria-label',`消息中心，${r.total} 条未读消息`);bell.title=`${r.total} 条未读消息`;}catch{badge.hidden=true;bell.title='未读数量暂不可用';}finally{running=false;}}
 const timer=setInterval(refresh,30000);
 function stop(){stopped=true;clearInterval(timer);badge.hidden=true;document.removeEventListener('visibilitychange',refresh);window.removeEventListener('student:notifications-changed',refresh);window.removeEventListener('auth:changed',stop);window.removeEventListener('auth:expired',stop);}
 document.addEventListener('visibilitychange',refresh);window.addEventListener('student:notifications-changed',refresh);window.addEventListener('auth:changed',stop);window.addEventListener('auth:expired',stop);window.addEventListener('pagehide',stop,{once:true});refresh();return {refresh,stop};
}
export async function initializeStudentWorkspace({access,main,page}){
 setAccess(access);
 const style=document.createElement('link');style.rel='stylesheet';style.href='/css/student/workspace-enhancements.css';document.head.append(style);
 document.querySelectorAll('.rail-link[href]').forEach(link=>{const path=new URL(link.href,location.href).pathname;if(path.includes('/student/'))link.hidden=!allowed(access,pageKey(path));});
 const bell=document.querySelector('.top-actions a[href*="student/notifications"]');
 if(bell){bell.hidden=!allowed(access,'notifications');if(!bell.hidden)startUnread(bell);}
 if(!allowed(access,pageKey(page))){const p=document.createElement('p');p.className='live-error';p.textContent='当前账号没有此学生页面权限，请返回已授权的工作空间。';main.append(p);return true;}
 if(can('student.profile.read_own')){
  try{const profile=await api('student/profile');document.querySelectorAll('.user-name').forEach(n=>{n.textContent=profile.full_name||'学生 #'+access.user_id;});document.querySelectorAll('.user-chip .avatar').forEach(n=>{n.textContent=(profile.full_name||'学生').slice(0,1);});}catch{/* 姓名不可用时保留公共账号编号，不阻止业务。 */}
 }
 const token=tokenStore.get();window.addEventListener('auth:changed',()=>{if(tokenStore.get()!==token){setAccess(null);main.replaceChildren();const link=document.createElement('a');link.href='/login.html';link.textContent='登录状态已变化，请重新登录。';main.append(link);}},{once:true});
 if(pageKey(page)==='notifications'){
  const region=document.createElement('section');region.className='student-live';main.append(region);const notifications=await import('./notifications.js');await notifications.render(region);return true;
 }
 if(pageKey(page)==='care'){
  const region=document.createElement('section');region.className='student-live';main.append(region);
  const care=await import('./care-workspace.js');await care.render(region);return true;
 }
 if(pageKey(page)==='chat'){
  const region=document.createElement('section');region.className='student-live';main.append(region);const chat=await import('./chat.js');await chat.render(region);return true;
 }
 return false;
}
