import {$, text, request, requireEmployee, can, deny, navigate} from './api.js';
import {display} from './ui.js';
import {icon} from './icons.js';

async function metric(me,key,name,permission,unit){
  if(!can(me,permission))return;
  const card=text('article','','metric'),top=text('div','','metric-top');
  top.append(text('span',name),icon(key));
  const value=text('strong','…','metric-value');
  card.append(top,value,text('small',unit));$('metrics').append(card);
  try{const data=await request('/'+key+'?limit=1&offset=0');value.textContent=String(data.total ?? data.length ?? 0);}
  catch(error){value.textContent='—';card.append(text('small',error.message,'error'));}
}
function quick(me,key,title,subtitle,permission){
  if(!can(me,permission))return;
  const button=text('button','','quick-link');button.type='button';
  const mark=text('span','','quick-icon');mark.append(icon(key));
  const copy=text('span',title);copy.append(text('small',subtitle));
  button.append(mark,copy);button.onclick=()=>navigate(key);$('quick-links').append(button);
}
async function feed(me,key,permission){
  if(!can(me,permission))return;
  const isTodo=key==='todos',panel=$(isTodo?'todo-panel':'notification-panel'),box=$(isTodo?'todo-feed':'notification-feed');
  panel.hidden=false;box.append(text('p','正在加载…','loading'));
  try{
    const result=await request('/'+key+'?limit=5&offset=0');box.replaceChildren();
    const rows=(result.items || []).slice(0,5);
    if(!rows.length){box.append(text('p',isTodo?'暂无待办，继续保持有序的工作节奏。':'暂无新的工作通知。','empty'));return;}
    for(const row of rows){
      const line=text('div','','feed-row'),content=text('div','','feed-content');
      content.append(text('p',row.title),text('small',isTodo?display('type',row.type):display('sent_at',row.sent_at)));
      line.append(text('span','','feed-dot'),content);
      line.append(text('span',isTodo?(row.due_at?display('due_at',row.due_at):'待处理'):(row.read_at?'已读':'未读'),'status-pill '+(row.read_at?'good':'wait')));
      box.append(line);
    }
  }catch(error){box.replaceChildren(text('p',error.message,'error'));}
}
async function start(){
  const me=await requireEmployee();document.querySelector('main').hidden=false;
  $('open-assistant').hidden=!['command','query','knowledge.read'].some(p=>can(me,p));
  $('open-assistant').onclick=()=>navigate('assistant');
  $('all-todos').onclick=()=>navigate('todos');$('all-notifications').onclick=()=>navigate('notifications');
  quick(me,'customer','客户管理','档案与跟进','customer.read');
  quick(me,'daily-report','员工日报','记录工作进展','daily.read');
  quick(me,'students','学生档案','授权学生信息','student.read');
  quick(me,'scores','学生成绩','课程考核记录','score.read');
  quick(me,'tickets','投诉工单','推进服务处理','ticket.read');
  quick(me,'knowledge','知识资料','制度与业务经验','knowledge.read');
  quick(me,'courses','课程管理','课程目录维护','score.read');
  quick(me,'employees','组织通讯录','连接团队成员','organization.read');
  await Promise.allSettled([
    metric(me,'customer','客户档案','customer.read','位 · 可见客户'),
    metric(me,'students','学生档案','student.read','位 · 授权学生'),
    metric(me,'daily-report','工作日报','daily.read','份 · 可见日报'),
    metric(me,'tickets','服务工单','ticket.read','条 · 可见工单'),
    feed(me,'todos','todo.read_own'),feed(me,'notifications','notification.read_own')
  ]);
}
start().catch(deny);
