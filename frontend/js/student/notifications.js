import {createList,api,esc,dateText,busy,errorToast} from './ui.js';

export async function render(root) {
 let selected='all';
 root.innerHTML=`<section class="panel student-notification-list" aria-label="我的通知">
  <div class="student-notification-toolbar"><div class="student-notification-tabs" role="group" aria-label="筛选通知">
   <button class="button secondary active" type="button" data-filter="all" aria-pressed="true">全部通知</button>
   <button class="button secondary" type="button" data-filter="unread" aria-pressed="false">未读通知</button>
   <button class="button secondary" type="button" data-filter="read" aria-pressed="false">已读通知</button>
  </div><button class="button secondary" type="button" data-refresh>刷新通知</button></div>
  <div id="notification-list"></div><p class="visually-hidden" role="status" data-notification-status></p>
 </section>`;
 const list=createList(root.querySelector('#notification-list'),{
  fetchPage:(limit,offset)=>api(`student/notifications?limit=${limit}&offset=${offset}${selected==='all'?'':'&unread='+(selected==='unread')}`),
  iconName:'bell',emptyTitle:'暂无符合条件的通知',emptyText:'你可以切换到全部通知，或稍后刷新查看。',
  render:rows=>rows.map(r=>`<article class="student-notification-row ${r.read_at?'':'unread'}" data-notification-id="${esc(r.notification_id)}">
   <div class="student-notification-copy"><h3>${esc(r.title)}</h3><p>${esc(r.content||'这条通知没有补充内容。')}</p>
   <div class="student-notification-meta">通知编号：${esc(r.notification_id)} · ${esc(dateText(r.sent_at||r.created_at))} · ${r.read_at?'已读':'未读'}</div></div>
   <button class="button ${r.read_at?'secondary':''} student-notification-action" type="button" data-read="${esc(r.notification_id)}" aria-label="${esc((r.read_at?'已读：':'标记已读：')+r.title)}" ${r.read_at?'disabled':''}>${r.read_at?'已读':'标记已读'}</button>
  </article>`).join(''),
  afterRender:body=>body.querySelectorAll('[data-read]:not(:disabled)').forEach(button=>{
   button.onclick=()=>busy(button,async()=>{
    try {
     await api('student/notifications/'+button.dataset.read+'/read',{method:'POST',body:{}});
     root.querySelector('[data-notification-status]').textContent='通知 '+button.dataset.read+' 已标记为已读。';
     await list.load();
    } catch(error) { errorToast(error); }
   });
  }),
 });
 root.querySelectorAll('[data-filter]').forEach(button=>button.onclick=()=>{
  selected=button.dataset.filter;
  root.querySelectorAll('[data-filter]').forEach(item=>{item.classList.toggle('active',item===button);item.setAttribute('aria-pressed',String(item===button));});
  list.load(true);
 });
 root.querySelector('[data-refresh]').onclick=()=>list.load();
 await list.load();
}
