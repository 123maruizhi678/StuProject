// 通用业务页控制器。页面只声明 data-resource；字段和接口集中在 catalog.js。
import {$, text, request, requireEmployee, can, deny} from './api.js';
import {resources, labels, enums} from './catalog.js';
import {display, pageMeta} from './ui.js';

const key=document.body.dataset.resource;
const resource=resources.find(item=>item.path==='/'+key);
const state={me:null,offset:0,total:0,rows:[],loading:false};
const pageSize=20;
const primaryKeys={customer:'customer_id','daily-report':'daily_report_id',students:'student_id',scores:'score_id',tickets:'ticket_id',knowledge:'knowledge_id',notifications:'notification_id',employees:'employee_id',departments:'department_id','student-bindings':'binding_id',courses:'course_id','student-courses':'enrollment_id','academic-events':'id','application-progress':'id','operation-logs':'operation_log_id',todos:'id'};
const pk=row=>row[primaryKeys[key]];
const authorized=permission=>can(state.me,permission);
const statusOptions={customer:['new','contacting','qualified','signed','lost'],courses:['active','disabled'],'student-courses':['active','disabled'],employees:['active','disabled','left']};
const optional=new Set(['phone','education_level','target_country_code','position_title','work_email','parent_department_id','function_description','course_scope_code','is_primary','valid_to','access_department_id','source_reference','question','answer','content_text','expires_at','next_followup_at','detail','lost_reason']);
const positiveFields=new Set(['student_id','employee_id','department_id','parent_department_id','access_department_id','attempt_no','max_score']);

function setNotice(message){$('notice').textContent=message;}
function version(row){return key==='academic-events'?{expected_event_version:row.event_version}:{expected_version:row.row_version};}
function tableRows() {
  const query=$('table-search').value.trim().toLowerCase();
  const rows=state.rows.filter(row=>!query || resource.columns.some(col=>display(col,row[col]).toLowerCase().includes(query)));
  $('table-body').replaceChildren();
  for (const row of rows) {
    const tr=document.createElement('tr');
    for (const column of resource.columns) {
      const td=text('td',display(column,row[column]));td.title=td.textContent;
      if(/status$/.test(column)){
        const style=['active','valid','signed','completed','published','submitted'].includes(row[column])?'good':['disabled','void','lost','cancelled','blocked','closed'].includes(row[column])?'bad':'wait';
        td.replaceChildren(text('span',display(column,row[column]),'status-pill '+style));
      }
      tr.append(td);
    }
    const actions=text('td','','action-cell');
    function action(name,handler,destructive=false){
      const button=text('button',name,destructive?'destructive':undefined);button.type='button';
      button.onclick=async()=>{button.disabled=true;try{await handler();}catch(error){setNotice(error.message);}finally{button.disabled=false;}};
      actions.append(button);
    }
    action('查看',()=>details(row));
    const ownDaily=state.me.is_admin||key!=='daily-report'||row.employee_id===state.me.employee_id;
    if(resource.edit && authorized(resource.write) && ownDaily)action('编辑',()=>edit(row));
    if(key==='customer'){
      if(authorized('customer.followup'))action('跟进',()=>openForm('追加客户跟进',['content','channel','followup_at','next_followup_at'],{},values=>request('/customer/'+pk(row)+'/followups',{method:'POST',body:values})));
      if(authorized('customer.status'))action('状态',()=>openForm('更新客户状态',['status','lost_reason'],row,values=>request('/customer/'+pk(row)+'/status',{method:'PUT',body:{...values,...version(row)}})));
      if(authorized('customer.assign'))action('转派',()=>openForm('转派客户',['employee_id','reason'],{},values=>request('/customer/'+pk(row)+'/assign',{method:'POST',body:{...values,...version(row)}})));
      action('跟进记录',()=>followupHistory(row));
    }
    if(key==='daily-report' && authorized('daily.write_own') && ownDaily && row.status==='submitted')action('摘要',async()=>{await request('/daily-report/summary',{method:'POST',body:{report_id:pk(row)}});setNotice('日报摘要已生成。');await load(false);});
    if(key==='tickets'){
      if(authorized('ticket.assign'))action('分派',()=>openForm('分派工单',['employee_id','reason'],{},values=>request('/tickets/'+pk(row)+'/assign',{method:'POST',body:{...values,...version(row)}})));
      if(authorized('ticket.handle'))for(const [title,suffix]of [['人工回应','followups'],['给出方案','resolve']])action(title,()=>openForm(title,['content'],{},values=>request('/tickets/'+pk(row)+'/'+suffix,{method:'POST',body:{...values,...version(row),visibility:'student_visible'}})));
    }
    if(key==='knowledge' && authorized('knowledge.publish'))action('发布',()=>openForm('审核发布',['effective_from','expires_at'],{},values=>request('/knowledge/'+pk(row)+'/publish',{method:'POST',body:{...values,...version(row)}})));
    if(key==='employees' && authorized('role.manage'))action('角色',()=>openForm('配置业务角色',['role_codes','reason'],row,values=>request('/employees/'+pk(row)+'/roles',{method:'PUT',body:{...values,...version(row)}})));
    if(key==='notifications' && !row.read_at)action('标为已读',async()=>{await request('/notifications/'+pk(row)+'/read',{method:'POST'});await load();});
    const removal={customer:['customer.archive','归档'],'daily-report':['daily.write_own','作废'],scores:['score.void','作废'],knowledge:['knowledge.manage','停用'],departments:['organization.manage','停用'],'student-bindings':['binding.manage','停用']}[key];
    if(removal && authorized(removal[0]) && ownDaily)action(removal[1],()=>openForm(removal[1]+resource.name,['reason'],{},values=>request(resource.path+'/'+pk(row),{method:'DELETE',body:{...values,...version(row)}})),true);
    tr.append(actions);$('table-body').append(tr);
  }
  $('empty').hidden=rows.length!==0;
  $('empty-title').textContent=state.rows.length && !rows.length?'本页没有匹配的记录':'当前没有记录';
  $('empty-description').textContent=state.rows.length && !rows.length?'调整筛选内容，或切换到其他页查找。':'当前授权范围内的业务记录会显示在这里。';
}
async function load(clearNotice=true) {
  if(state.loading)return;
  state.loading=true;$('refresh').disabled=true;$('table-loading').hidden=false;
  if(clearNotice)setNotice('');
  try {
    const path=resource.readPath || resource.path;
    const result=await request(path+'?limit='+pageSize+'&offset='+state.offset+(key==='knowledge' && authorized('knowledge.manage')?'&manage=true':''));
    state.total=Array.isArray(result)?result.length:(result.total ?? result.items?.length ?? 0);
    state.rows=Array.isArray(result)?result.slice(state.offset,state.offset+pageSize):result.items || [];
    $('list-count').textContent='共 '+state.total+' 条';tableRows();
    $('previous').disabled=state.offset===0;$('next').disabled=state.offset+pageSize>=state.total;
    $('page-info').textContent='第 '+(state.offset/pageSize+1)+' / '+Math.max(1,Math.ceil(state.total/pageSize))+' 页';
  } catch(error){state.rows=[];$('table-body').replaceChildren();$('empty').hidden=true;setNotice(error.message);}
  finally{state.loading=false;$('refresh').disabled=false;$('table-loading').hidden=true;}
}
function showDetails(title,row) {
  $('detail-title').textContent=title;$('detail-content').replaceChildren();
  for(const [field,value]of Object.entries(row)) {
    if(['row_version','event_version','request_key','parameters_hash','operation_key'].includes(field))continue;
    const line=text('div','','preview-field');line.append(text('strong',labels[field] || field),text('span',display(field,value)));$('detail-content').append(line);
  }
  $('detail-dialog').showModal();
}
async function details(row) {
  const noDetail=['todos','operation-logs','student-bindings','departments'];
  const detail=noDetail.includes(key)?row:await request(resource.path+'/'+pk(row));
  showDetails('记录详情',detail);
}
function fieldOptions(field) {
  if(field==='status' && statusOptions[key])return Object.fromEntries(statusOptions[key].map(value=>[value,enums.status[value]]));
  if(field==='position_title')return Object.fromEntries(['普通员工','顾问','招生顾问','咨询顾问','部门主管','部门经理','老师','教师','班主任','教务','教务专员','企业管理员','企业配置管理员'].map(value=>[value,value]));
  return enums[field];
}
function openForm(title,fields,initial,save) {
  $('edit-title').textContent=title;$('fields').replaceChildren();$('edit-error').textContent='';
  for(const field of fields) {
    const label=text('label',labels[field] || field), options=fieldOptions(field);
    let input;
    if(options){
      input=document.createElement('select');
      for(const [value,name]of Object.entries(options)){const option=text('option',name);option.value=value;input.append(option);}
    }else{
      const multiline=['content','submitted_content','content_text','answer','question','reason','function_description','detail'].includes(field);
      input=document.createElement(multiline?'textarea':'input');
      if(multiline)label.classList.add('wide');
      else input.type=field==='is_primary'?'checkbox':/_at$|_from$|_to$/.test(field)?'datetime-local':/_date$/.test(field)?'date':positiveFields.has(field)||field==='score_value'?'number':field==='work_email'?'email':'text';
      if(input.type==='number'){input.step=field==='score_value'||field==='max_score'?'any':'1';input.min=field==='score_value'?'0':field==='max_score'?'0.01':'1';}
    }
    input.name=field;
    if(!optional.has(field))input.required=true;
    if(input.type==='checkbox')input.checked=Boolean(initial[field]);
    else if(initial[field]!==null && initial[field]!==undefined)input.value=Array.isArray(initial[field])?initial[field].join(','):String(initial[field]);
    if(input.type==='datetime-local' && initial[field]){
      const raw=String(initial[field]),date=new Date(/Z$|[+-]\d\d:\d\d$/.test(raw)?raw:raw+'Z');
      if(!Number.isNaN(date.getTime()))input.value=new Date(date.getTime()+8*3600000).toISOString().slice(0,16);
    }
    if(field==='report_date' && !input.value)input.value=new Date(Date.now()+8*3600000).toISOString().slice(0,10);
    if(field==='attempt_no' && !input.value)input.value='1';
    if(field==='max_score' && !input.value)input.value='100';
    if(field==='role_codes')input.placeholder='employee,manager';
    label.append(input);
    if(field==='position_title')label.append(text('span','职位变更会同步对应业务角色。'));
    if(field==='role_codes')label.append(text('span','业务角色须与员工职位对应；多个角色使用英文逗号分隔。'));
    if(input.type==='datetime-local')label.append(text('span','按北京时间填写。'));
    if(field==='phone' && authorized('customer.read')){
      const check=text('button','检查重复客户','secondary');check.type='button';const hint=text('span','');
      check.onclick=async()=>{try{check.disabled=true;const result=await request('/customer/phone-candidates',{method:'POST',body:{phone:input.value}});hint.textContent=result.total?'发现 '+result.total+' 位同号码候选：'+result.items.map(item=>item.full_name+'（'+item.customer_id+'）').join('、')+'。请核对。':'当前授权范围内未发现同号码客户。';}catch(error){hint.textContent=error.message;}finally{check.disabled=false;}};
      label.append(check,hint);
    }
    $('fields').append(label);
  }
  $('edit-form').onsubmit=async event=>{
    event.preventDefault();const button=event.submitter;button.disabled=true;$('edit-error').textContent='';
    try{
      const values={};
      for(const input of $('fields').querySelectorAll('input,select,textarea')){
        if(input.type==='checkbox')values[input.name]=input.checked;
        else if(input.value!==''){
          if(input.type==='number')values[input.name]=Number(input.value);
          else if(input.name==='role_codes')values[input.name]=input.value.split(',').map(item=>item.trim()).filter(Boolean);
          else if(input.type==='datetime-local')values[input.name]=input.value+(input.value.length===16?':00':'')+'+08:00';
          else values[input.name]=input.value;
        }
      }
      await save(values);$('editor').close();setNotice('操作已完成。');await load(false);
    }catch(error){$('edit-error').textContent=error.message;}
    finally{button.disabled=false;}
  };
  $('editor').showModal();
}
function edit(row) {openForm('编辑'+resource.name,resource.edit,row,values=>request(resource.path+'/'+pk(row),{method:'PUT',body:{...values,...version(row)}}));}
async function followupHistory(customer) {
  const result=await request('/customer/'+customer.customer_id+'/followups?limit=100&offset=0');
  $('detail-title').textContent='客户跟进记录';$('detail-content').replaceChildren();
  if(!result.items.length)$('detail-content').append(text('p','暂无跟进记录。','empty'));
  for(const row of result.items){
    const block=text('section','','panel');block.append(text('p',row.content),text('p',display('followup_at',row.followup_at)+' · '+row.channel,'muted'),text('p','下次跟进：'+display('next_followup_at',row.next_followup_at)+' · '+({pending:'待跟进',done:'已完成',cancelled:'已取消',none:'未安排'})[row.followup_status],'muted'));
    if(authorized('customer.followup')){
      const actions=text('div','','actions');
      for(const [name,status]of [['标为完成','done'],['取消安排','cancelled'],['重新安排','pending']]){
        const button=text('button',name,'secondary');button.type='button';
        button.onclick=()=>{try{$('detail-dialog').close();openForm(name,status==='pending'?['next_followup_at','reason']:['reason'],{},values=>request('/customer/'+customer.customer_id+'/followups/'+row.followup_id+'/schedule',{method:'PUT',body:{...values,followup_status:status,expected_version:row.row_version}}));}catch(error){setNotice(error.message);}};
        actions.append(button);
      }
      block.append(actions);
    }
    $('detail-content').append(block);
  }
  $('detail-dialog').showModal();
}
async function start(){
  if(!resource)throw Error('页面配置不存在。');
  state.me=await requireEmployee(resource.permission);
  $('page-title').textContent=resource.name;$('list-title').textContent=resource.name;
  $('page-group').textContent=pageMeta[key][0]+' / ENTERPRISE';$('page-description').textContent=pageMeta[key][1];
  const head=text('tr','');for(const column of [...resource.columns,'_actions'])head.append(text('th',labels[column]||{_actions:'操作',type:'事项类型',due_at:'到期时间'}[column]||column));$('table-head').append(head);
  $('new-record').hidden=!resource.create||!authorized(resource.create);
  $('new-record').onclick=()=>{try{openForm('新增'+resource.name,resource.fields,{},values=>request(resource.path,{method:'POST',body:values}));}catch(error){setNotice(error.message);}};
  $('refresh').onclick=()=>load();$('table-search').oninput=tableRows;
  $('previous').onclick=()=>{if(state.loading)return;state.offset=Math.max(0,state.offset-pageSize);$('table-search').value='';load();};
  $('next').onclick=()=>{if(state.loading)return;state.offset+=pageSize;$('table-search').value='';load();};
  $('close-editor').onclick=()=>$('editor').close();$('cancel-editor').onclick=()=>$('editor').close();$('close-detail').onclick=()=>$('detail-dialog').close();
  document.querySelector('main').hidden=false;await load();
}
start().catch(deny);
