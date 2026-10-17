import {api,tokenStore} from './api.js';
import {esc,icon,empty,mountDialog,busy,toast,dateText,loginUrl} from '../common/student-shell.js';

const names={pending:'待审批',approved:'已批准',rejected:'已驳回',cancelled:'已取消',personal:'事假',sick:'病假',open:'待受理',assigned:'已分派',processing:'处理中',awaiting_student:'待你确认',closed:'已关闭',reopened:'重新跟进',sent:'已送达',queued:'待送达',active:'有效',inactive:'已停用',valid:'有效',complaint:'投诉',suggestion:'建议',application:'申请',visa:'签证',teaching:'教学',service:'服务',other:'其他',exam:'考试',ddl:'截止日期',document_review:'文书审核',school_application:'院校申请',visa_process:'签证办理',submitted:'已提交',student_reply:'学生补充',confirm:'确认解决',reopen:'重新跟进',rating:'满意度评价'};
export const label=value=>names[value]||String(value??'—');
export function badge(value,display){const type=['approved','closed','sent','valid','active'].includes(value)?'good':['rejected','cancelled','inactive'].includes(value)?'bad':['processing','assigned','queued'].includes(value)?'blue':'wait';return `<span class="pill ${type}">${esc(display||label(value))}</span>`;}
export function heading(title,description,action=''){return `<div class="page-heading"><div class="kicker"><span class="dot"></span> STUDENT SERVICES</div><div class="page-title-row"><h1>${esc(title)}</h1>${action}</div><p>${esc(description)}</p></div>`;}
export function tabs(options,selected){return `<div class="tabs">${options.map(([key,text])=>`<button class="tab ${key===selected?'active':''}" type="button" data-tab="${esc(key)}" aria-pressed="${key===selected}">${esc(text)}</button>`).join('')}</div>`;}
export function bindTabs(root,onChange){root.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{root.querySelectorAll('[data-tab]').forEach(t=>{t.classList.toggle('active',t===b);t.setAttribute('aria-pressed',String(t===b));});onChange(b.dataset.tab);});}
export function table(headers,rows){return `<div class="table-wrap"><table><thead><tr>${headers.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;}
export function details(fields){return `<dl class="detail-grid">${fields.filter(([,v])=>v!==null&&v!==undefined).map(([k,v,wide])=>`<div ${wide?'class="wide"':''}><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>`;}
export function createList(container,{fetchPage,render,emptyTitle='暂无记录',emptyText='后续业务动态会在这里展示。',iconName='folder',afterRender=()=>{}}){
 let offset=0,total=0,rows=[],sequence=0;
 container.innerHTML=`<div data-list-body></div><div class="pager"><span data-page-info>正在读取</span><div class="pager-actions"><button type="button" class="button ghost compact" data-prev>上一页</button><button type="button" class="button ghost compact" data-next>下一页</button></div></div>`;
 const body=container.querySelector('[data-list-body]'),prev=container.querySelector('[data-prev]'),next=container.querySelector('[data-next]'),info=container.querySelector('[data-page-info]');
 function update(){prev.disabled=offset===0;next.disabled=offset+rows.length>=total;info.textContent=total?`共 ${total} 条 · 第 ${Math.floor(offset/10)+1} 页`:'共 0 条';}
 async function load(reset=false){if(reset)offset=0;const current=++sequence;prev.disabled=next.disabled=true;
  if(!tokenStore.get()){body.innerHTML=empty('登录后查看本人记录','你的课程、申请和消息会在这里安全呈现。',iconName)+`<div style="text-align:center;padding-bottom:24px"><a class="button secondary compact" href="${loginUrl()}">登录账号</a></div>`;rows=[];total=0;update();return;}
  body.innerHTML='<div class="loading-line"></div>'+empty('正在读取记录','正在同步你的最新业务状态。',iconName);
  try{const data=await fetchPage(10,offset);if(current!==sequence)return;rows=data.items;total=data.total;if(offset>=total&&offset>0){offset=Math.max(0,Math.floor(Math.max(0,total-1)/10)*10);return load();}body.innerHTML=rows.length?render(rows):empty(emptyTitle,emptyText,iconName);update();afterRender(body,rows,data);}catch(error){if(current!==sequence)return;rows=[];total=0;body.innerHTML=empty('记录暂时不可用',error.message,iconName,true);body.querySelector('[data-retry]').onclick=()=>load();info.textContent='加载未完成';prev.disabled=next.disabled=true;}
 }
 prev.onclick=()=>{offset=Math.max(0,offset-10);load();};next.onclick=()=>{offset+=10;load();};
 return {load,get rows(){return rows;}};
}
export function formDialog(title,fields,onSubmit,{submit='确认提交',hint=''}={}){const dialog=mountDialog(title,`<form>${hint?`<p class="form-hint" style="margin-bottom:20px">${esc(hint)}</p>`:''}${fields}<p class="field-error" role="alert"></p><div class="form-actions"><button class="button ghost" type="button" data-cancel>取消</button><button class="button" type="submit">${esc(submit)} ${icon('arrow')}</button></div></form>`);const form=dialog.querySelector('form');form.querySelector('[data-cancel]').onclick=()=>dialog.close();form.onsubmit=async e=>{e.preventDefault();if(!form.reportValidity())return;const error=form.querySelector('.field-error');error.textContent='';await busy(form.querySelector('[type=submit]'),async()=>{try{await onSubmit(new FormData(form),dialog);dialog.close();}catch(e){error.textContent=e.message;}});};return dialog;}
export function confirmDialog(title,description,onConfirm,submit='确认操作'){return formDialog(title,`<p class="muted small">${esc(description)}</p>`,onConfirm,{submit});}
export const errorToast=error=>toast(error.message,true);
export {api,tokenStore,esc,icon,empty,busy,toast,dateText,mountDialog};
