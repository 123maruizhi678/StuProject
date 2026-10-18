import { request, createRequestId } from '../common/api.js';
import { operationsForPage } from '../workspace/pages.js';

const E='/api/v1/enterprise/', I='/api/v1/internal/student/';
const resources={
  customer:{name:'客户档案',id:'customer_id',path:E+'customer'},
  followups:{name:'客户跟进',id:'followup_id',path:E+'customer/{customer_id}/followups'},
  'daily-report':{name:'工作日报',id:'report_id',aliases:['daily_report_id'],path:E+'daily-report'},
  students:{name:'学生档案',id:'student_id',path:E+'students'},
  scores:{name:'学生成绩',id:'score_id',path:E+'scores'},
  tickets:{name:'服务工单',id:'ticket_id',path:E+'tickets'},
  knowledge:{name:'知识资料',id:'knowledge_id',path:E+'knowledge'},
  notifications:{name:'我的通知',id:'notification_id',path:E+'notifications'},
  employees:{name:'员工',id:'employee_id',path:E+'employees'},
  departments:{name:'部门',id:'department_id',path:E+'organization'},
  'student-bindings':{name:'学生服务关系',id:'binding_id',path:E+'student-bindings'},
  courses:{name:'课程',id:'course_id',path:E+'courses'},
  'student-courses':{name:'学生选课',id:'enrollment_id',path:E+'student-courses'},
  'academic-events':{name:'学业节点',id:'event_id',path:E+'academic-events'},
  'application-progress':{name:'申请进度',id:'progress_id',path:E+'application-progress'},
  'operation-logs':{name:'操作记录',id:'operation_log_id',path:E+'operation-logs'},
  todos:{name:'我的待办',id:'id',path:E+'todos'},
  'internal/leave':{name:'学生请假',id:'apply_id',path:I+'leave'},
  'internal/warnings':{name:'学生关怀',id:'warning_id',path:I+'warnings'},
};
const readPermissions={customer:'customer.read',followups:'customer.read','daily-report':'daily.read',students:'student.read',scores:'score.read',
  tickets:'ticket.read',knowledge:'knowledge.read',notifications:'notification.read_own',employees:'organization.read',departments:'organization.read',
  'student-bindings':'binding.manage',courses:'score.read','student-courses':'score.read','academic-events':'student.read',
  'application-progress':'customer.read','operation-logs':'audit.read',todos:'todo.read_own'};

export function resourceForPath(path){
  if(path.startsWith(E+'customer/')&&path.includes('/followups'))return 'followups';
  if(path.startsWith(E)){
    const key=path.slice(E.length).split('/')[0];
    return key==='organization'?'departments':resources[key]?key:null;
  }
  if(path.startsWith(I)){
    const key=path.slice(I.length).split('/')[0];
    return key==='academic'?'academic-events':key==='progress'?'application-progress':resources['internal/'+key]?'internal/'+key:null;
  }
  return null;
}

export function recordBindings(resource,row,parent={}){
  const config=resources[resource];
  const bindings={...parent};
  for(const [key,value]of Object.entries(row))if(/_id$|_code$/.test(key)&&value!==null)bindings[key]=value;
  if(config){
    const value=row[config.id]??(config.aliases||[]).map(key=>row[key]).find(value=>value!==undefined)??row.id;
    if(value!==undefined)bindings[config.id]=value;
  }
  return bindings;
}

export function operationPermission(op){
  const {path,method}=op,key=resourceForPath(path),tail=path.split('/').at(-1);
  if(path.startsWith(I)){
    if(path.includes('/leave'))return 'student.admin_service.'+(tail==='assign'||tail==='assignments'?'assign':'review');
    if(path.includes('/warnings'))return 'student.warning.'+(tail==='assign'||tail==='assignments'?'assign':method==='GET'?'read':'handle');
    if(path.includes('/academic/'))return 'student.academic.maintain';
    if(path.includes('/progress/'))return 'student.progress.maintain';
    return null;
  }
  if(!path.startsWith(E))return null;
  if(method==='GET')return readPermissions[key]?'enterprise.'+readPermissions[key]:null;
  let permission;
  if(path.includes('/command'))permission='command';
  else if(path.includes('/voice/'))permission='command';
  else if(path.endsWith('/onboarding/ask'))permission='knowledge.read';
  else if(path.endsWith('/nl2sql'))permission='query';
  else if(path.endsWith('/phone-candidates'))permission='customer.read';
  else if(key==='customer')permission='customer.'+(tail==='assign'?'assign':tail==='status'?'status':method==='DELETE'?'archive':method==='POST'?'create':'update');
  else if(key==='followups')permission='customer.followup';
  else if(key==='daily-report')permission='daily.write_own';
  else if(key==='scores')permission=method==='DELETE'?'score.void':'score.write';
  else if(['courses','student-courses'].includes(key))permission='academic.write';
  else if(key==='academic-events')permission='academic.write';
  else if(key==='application-progress')permission='progress.write';
  else if(key==='departments')permission='organization.manage';
  else if(key==='employees')permission=tail==='roles'?'role.manage':'employee.manage';
  else if(key==='student-bindings')permission='binding.manage';
  else if(key==='knowledge')permission=tail==='publish'?'knowledge.publish':'knowledge.manage';
  else if(key==='tickets')permission=tail==='assign'?'ticket.assign':'ticket.handle';
  else if(key==='notifications')permission='notification.read_own';
  return permission?'enterprise.'+permission:null;
}

function actionName(op){
  const tail=op.path.split('/').at(-1),key=resourceForPath(op.path);
  if(op.path===E+'command')return '解析工作指令';
  if(op.path===E+'command/confirm')return '确认办理';
  if(op.path.endsWith('/onboarding/ask'))return '知识问答';
  if(op.path.endsWith('/nl2sql'))return '业务查询';
  if(op.path.endsWith('/voice/transcribe'))return '语音转文字';
  if(tail==='phone-candidates')return '按电话查找客户';
  if(tail==='summary')return '生成日报摘要';
  if(op.path.startsWith(I+'academic/'))return '维护本地教务';
  if(op.path.startsWith(I+'progress/'))return '维护本地进度';
  if(key==='followups')return tail==='schedule'?'调整跟进安排':op.method==='GET'?'跟进记录':'添加跟进';
  const names={assign:'分派负责人',status:'调整状态',roles:'调整角色',publish:'发布资料',resolve:'解决工单',
    decision:'审批请假',ack:'接手关怀',follow:'添加跟进',close:'关闭关怀',read:'标记已读'};
  if(names[tail])return names[tail];
  if(key==='tickets'&&tail==='followups')return '添加处理记录';
  if(op.method==='DELETE')return key==='customer'?'归档客户':['daily-report','scores'].includes(key)?'作废记录':'停用记录';
  if(['PUT','PATCH'].includes(op.method))return '编辑';
  if(op.method==='POST')return '新增'+(resources[key]?.name||'记录');
  return '查看详情';
}

const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
const button=(text,run,cls='button secondary small')=>{const el=node('button',text,cls);el.type='button';el.onclick=run;return el;};
const pathNames=path=>[...path.matchAll(/\{([^}]+)\}/g)].map(match=>match[1]);
const bindPath=(path,bindings)=>path.replace(/\{([^}]+)\}/g,(_,key)=>{
  if(bindings[key]===undefined||bindings[key]===null)throw Error('缺少当前记录编号，请重新选择记录。');
  return encodeURIComponent(bindings[key]);
});
const rowsOf=data=>Array.isArray(data)?data:data?.items||data?.rows||[];
const destructive=op=>op.method==='DELETE'||op.path.endsWith('/close');

export async function mountEnterpriseWorkspace({main,page,schema,access,options,field,readFields,resolve,setValue,format,label,privateField,selection={}}){
  const employee=await request('/enterprise/me/permissions');
  const grants=new Set([...(access?.permissions||[]),...(employee.permissions||[])]);
  const allowed=op=>{
    const permission=operationPermission(op);
    return Boolean(permission&&(!op.path.startsWith(I)||access.identity_type==='employee')&&grants.has(permission));
  };
  const all=Object.entries(schema.paths).flatMap(([path,methods])=>Object.entries(methods)
    .filter(([method])=>['get','post','put','patch','delete'].includes(method)).map(([method,op])=>({...op,path,method:method.toUpperCase()}))).filter(allowed);
  const pageOps=operationsForPage(page,schema.paths).filter(allowed);
  const controllers=[];
  const notification=node('div');notification.setAttribute('aria-live','polite');main.append(notification);
  const notify=(text,error=false)=>notification.replaceChildren(node('p',text,error?'live-error':'live-status'));
  const api=(path,options)=>request(path.slice('/api/v1'.length),options);
  const findOp=(method,path)=>all.find(op=>op.method===method&&op.path===path);

  const dialog=node('dialog',undefined,'enterprise-dialog');dialog.setAttribute('aria-labelledby','enterprise-dialog-title');
  const head=node('header',undefined,'enterprise-dialog-head'),title=node('h2');title.id='enterprise-dialog-title';
  const close=button('×',()=>dialog.close(),'icon-button enterprise-dialog-close');close.setAttribute('aria-label','关闭弹窗');
  const feedback=node('div',undefined,'enterprise-dialog-feedback');feedback.setAttribute('aria-live','polite');
  const tabs=node('nav',undefined,'enterprise-dialog-tabs');tabs.setAttribute('aria-label','记录操作');
  const content=node('div',undefined,'enterprise-dialog-content');
  const scroll=node('div',undefined,'enterprise-dialog-scroll');
  head.append(title,close);scroll.append(head,feedback,tabs,content);dialog.append(scroll);document.body.append(dialog);
  let generation=0,busy=false,returnFocus=null;
  function message(text,error=false){feedback.replaceChildren(node('p',text,error?'live-error':'live-status'));}
  function setBusy(value){busy=value;close.disabled=value;tabs.querySelectorAll('button').forEach(el=>el.disabled=value);dialog.setAttribute('aria-busy',String(value));}
  dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();});
  dialog.addEventListener('close',()=>{if(dialog.open)return;generation++;document.body.classList.remove('enterprise-modal-open');returnFocus?.focus();});
  function begin(titleText){
    generation++;title.textContent=titleText;feedback.replaceChildren();tabs.replaceChildren();content.replaceChildren();setBusy(false);
    if(!dialog.open){returnFocus=document.activeElement;dialog.showModal();document.body.classList.add('enterprise-modal-open');}
    return generation;
  }
  function active(g){return dialog.open&&g===generation;}
  function nav(items){
    tabs.replaceChildren();
    for(const item of items){
      const tab=button(item.name,()=>{if(busy)return;tabs.querySelectorAll('button').forEach(el=>el.setAttribute('aria-pressed',String(el===tab)));content.replaceChildren();item.show();},'button secondary small');
      tab.setAttribute('aria-pressed','false');tabs.append(tab);
    }
    tabs.querySelector('button')?.click();
  }
  function detail(context){
    if(!context)return;
    const name=context.row.full_name||context.row.title||context.row.course_name||context.row.department_name||context.row.application_name;
    if(name)content.append(node('h3',name,'enterprise-record-name'));
    renderObject(content,context.row);
  }
  function renderValue(root,value,key=''){
    if(Array.isArray(value)){
      if(!value.length){root.append(node('span','—'));return;}
      const list=node('ol',undefined,'enterprise-nested-list');
      for(const item of value){const entry=node('li');renderValue(entry,item,key);list.append(entry);}root.append(list);
    }else if(value&&typeof value==='object')renderObject(root,value);
    else root.append(node('span',typeof value==='string'&&['missing_fields','columns'].includes(key)?label(value):format(value)));
  }
  function renderObject(root,data){
    const entries=Object.entries(data).filter(([key])=>!privateField(key));
    if(!entries.length){root.append(node('span','—'));return;}
    const list=node('dl');
    for(const [key,value]of entries){const item=node('dd');renderValue(item,value,key);list.append(node('dt',label(key)),item);}
    root.append(list);
  }
  function bodySpec(op){return resolve(op.requestBody?.content?.['application/json']?.schema);}
  function contextFor(key,row,parent={}){return {key,row:{...row},bindings:recordBindings(key,row,parent),views:new Map()};}
  async function refreshLists(){return Promise.allSettled(controllers.map(controller=>controller.load()));}

  function tableValue(value,key){
    if(Array.isArray(value))return value.length?value.map(item=>tableValue(item,key)).join('；'):'—';
    if(value&&typeof value==='object')return Object.entries(value).filter(([name])=>!privateField(name)).map(([name,item])=>`${label(name)}：${tableValue(item,name)}`).join('；');
    return typeof value==='string'&&['missing_fields','columns'].includes(key)?label(value):format(value);
  }

  function table(target,data,path,onChoose){
    target.replaceChildren();const rows=rowsOf(data);
    target.append(node('p',`共 ${data?.total??rows.length} 条记录。${onChoose?'选择记录可在弹窗中查看详情并办理业务。':''}`,'enterprise-list-count'));
    if(!rows.length){target.append(node('p','暂无记录。','live-status'));return;}
    const priority=['full_name','department_name','course_name','title','report_date','status','approval_status'];
    const keys=[...new Set(rows.flatMap(row=>Object.keys(row)))].filter(key=>!privateField(key));
    keys.sort((a,b)=>(priority.includes(a)?priority.indexOf(a):99)-(priority.includes(b)?priority.indexOf(b):99));
    const visible=keys.slice(0,8),wrap=node('div',undefined,'table-wrap enterprise-table-wrap'),el=node('table',undefined,'data-table enterprise-record-table');
    // Give dates and timestamps more room; narrow layouts may wrap them, but never truncate them.
    const timeColumns=new Map(visible.map(key=>{
      const sample=rows.map(row=>row[key]).find(value=>typeof value==='string'&&/^(?:\d{4}-\d{2}-\d{2}(?:[T ].*)?|\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)$/.test(value));
      const kind=sample?(sample.length===10?'date':'time'):/_(?:date)$/.test(key)?'date':/(?:_(?:at|time|datetime|timestamp)|^deadline)$/.test(key)?'time':'';
      return [key,kind];
    }));
    const weight=key=>timeColumns.get(key)==='time'?2.4:timeColumns.get(key)==='date'?1.1:1;
    const totalWeight=visible.reduce((sum,key)=>sum+weight(key),0);
    const thead=node('thead'),tr=node('tr');for(const key of visible){const th=node('th',label(key));th.scope='col';th.style.width=`${100*weight(key)/totalWeight}%`;tr.append(th);}if(onChoose){const th=node('th','操作','enterprise-record-action');th.scope='col';tr.append(th);}thead.append(tr);el.append(thead);
    const tbody=node('tbody');for(const row of rows){
      const tr=node('tr');for(const key of visible){const cell=node('td');cell.dataset.label=label(key);cell.dataset.field=key;const value=node('span',tableValue(row[key],key),'enterprise-cell-value');if(timeColumns.get(key))value.classList.add('enterprise-cell-time');else value.title=value.textContent;cell.append(value);tr.append(cell);}
      if(onChoose){const td=node('td',undefined,'enterprise-record-action');td.dataset.label='操作';td.append(button('选择记录',()=>onChoose(row)));tr.append(td);}tbody.append(tr);
    }
    el.append(tbody);wrap.append(el);target.append(wrap);
  }

  async function latest(context){
    const config=resources[context.key],detailPath=config.path+'/{'+config.id+'}';
    const op=findOp('GET',detailPath);
    if(op)return contextFor(context.key,await api(bindPath(op.path,context.bindings)),context.bindings);
    if(context.key==='followups'){
      const list=findOp('GET',config.path);
      if(list){
        const rows=await allRows(list,context.bindings);
        const row=rows.find(row=>String(row.followup_id??row.id)===String(context.bindings.followup_id));
        if(!row)throw Error('此跟进记录已不可访问，请刷新列表。');
        return contextFor(context.key,row,context.bindings);
      }
    }
    // Configuration resources without a detail route still obtain their current version from the list.
    const controller=controllers.find(item=>item.key===context.key);
    if(controller){
      const row=controller.rows.find(row=>String(recordBindings(context.key,row)[config.id])===String(context.bindings[config.id]));
      if(row)return contextFor(context.key,row,context.bindings);
    }
    return context;
  }
  function recordOps(context){
    return all.filter(op=>{
      const key=resourceForPath(op.path),paths=pathNames(op.path);
      const same=key===context.key||(context.key==='customer'&&key==='followups');
      if(!same||!paths.every(key=>context.bindings[key]!==undefined))return false;
      if(context.key==='daily-report'&&op.method!=='GET'&&!employee.is_admin&&String(context.row.employee_id)!==String(employee.employee_id))return false;
      if(context.key==='employees'&&op.path.endsWith('/roles')&&String(context.bindings.employee_id)===String(employee.employee_id))return false;
      if(!paths.length)return context.key==='daily-report'&&op.path===E+'daily-report/summary';
      if(op.method==='GET')return !op.path.endsWith('}')&&op.path!==resources[context.key].path;
      return true;
    });
  }
  function showRecord(context,g,success=''){
    if(!active(g))return;setBusy(false);
    title.textContent=resources[context.key].name+'详情';
    if(success)message(success);
    const items=[{name:'详情',show:()=>detail(context)}];
    if(context.parentContext)items.push({name:'返回客户详情',show:()=>openRecord(context.parentContext.key,context.parentContext.row,context.parentContext.bindings)});
    for(const op of recordOps(context))items.push({name:actionName(op),show:()=>{
      if(op.method==='GET')showRelated(op,context,g);
      else{
        const key=op.method+' '+op.path;
        if(!context.views.has(key))context.views.set(key,actionForm(op,context,g));
        content.append(context.views.get(key));
      }
    }});
    nav(items);
  }
  async function openRecord(key,row,parent={},parentContext=null){
    const g=begin(resources[key].name+'详情');content.append(node('p','正在读取记录……','live-status'));
    const context=contextFor(key,row,parent);
    try{const fresh=await latest(context);fresh.parentContext=parentContext;showRecord(fresh,g);}catch(error){
      if(!active(g))return;content.replaceChildren();message(error.message,true);
      content.append(button('重新读取记录',()=>openRecord(key,row,parent)));
    }
  }
  async function showRelated(op,parent,g){
    const target=node('div',undefined,'enterprise-related');content.append(target);target.append(node('p','正在读取记录……','live-status'));
    try{
      const path=bindPath(op.path,parent.bindings),data=await api(path+'?limit=20&offset=0');
      if(!active(g)||!target.isConnected)return;
      table(target,data,path,row=>openRecord(resourceForPath(op.path),row,parent.bindings,parent));
    }catch(error){if(active(g)&&target.isConnected)target.replaceChildren(node('p',error.message,'live-error'));}
  }

  function versionValue(name,op,context){
    if(!context)return undefined;
    const row=context.row;
    if(name==='expected_event_version')return row.event_version;
    if(name==='expected_updated_at')return row.updated_at;
    if(name==='expected_version')return op.path.startsWith(I+'academic/')?row.event_version:row.row_version??row.version;
    if(name==='report_id'&&op.path.endsWith('/summary'))return context.bindings.report_id;
    if(name==='id'&&op.path.startsWith(I))return row.id;
    return undefined;
  }
  function actionForm(op,context,g,{receipt}={}){
    const form=node('form',undefined,'live-form enterprise-action-form'),spec=bodySpec(op),properties=spec.properties||{};
    const automatic={},arrays=[],initial=new Map();
    const prefill=Boolean(context&&(['PUT','PATCH'].includes(op.method)||op.path.endsWith('/publish')));
    if(context)form.append(node('p',`当前记录：${context.row.full_name||context.row.title||resources[context.key].name}。`,'wide enterprise-form-context'));
    for(const parameter of op.parameters||[]){
      if(parameter.in==='query'&&!['limit','offset','unread_only','manage'].includes(parameter.name))field(form,parameter.name,parameter.schema,parameter.required);
    }
    // Tool upload schemas use multipart/form-data rather than JSON.
    const multipart=op.requestBody?.content?.['multipart/form-data'];
    const inputSpec=multipart?resolve(multipart.schema):spec;
    const entries=Object.entries(inputSpec.properties||{}).sort(([a],[b])=>Number(a==='reason')-Number(b==='reason'));
    for(const [name,raw]of entries){
      const required=(inputSpec.required||[]).includes(name)||name==='reason'&&destructive(op);
      if(receipt&&Object.hasOwn(receipt,name)){automatic[name]=receipt[name];continue;}
      if(['expected_version','expected_event_version','expected_updated_at'].includes(name)||name==='id'&&op.path.startsWith(I)||name==='report_id'&&op.path.endsWith('/summary')){
        const value=versionValue(name,op,context);
        if(value!==undefined)automatic[name]=value;
        else if(required){form.append(node('p','当前记录缺少最新版本，请重新读取记录。','live-error wide'));form.dataset.missingVersion='true';}
        continue;
      }
      const resolved=resolve(raw);
      if(name==='role_codes'&&resolved.items?.enum){
        const group=node('fieldset');group.append(node('legend',label(name)));
        const currentRoles=context?.row.role_codes??options.positions?.[context?.row.position_title]??[];
        const roleNames={employee:'员工',consultant:'顾问',manager:'经理',teacher:'教师',academic:'教务',admin:'企业管理员',analyst:'分析人员',reviewer:'审核人员',counselor:'关怀老师'};
        const inputs=[];for(const value of resolved.items.enum){
          const caption=node('label',undefined,'enterprise-role-option'),input=node('input');input.type='checkbox';input.value=value;input.checked=currentRoles.includes(value);caption.append(input,node('span',roleNames[value]||value));group.append(caption);inputs.push(input);
        }
        form.append(group,node('p','角色需与职位配置一致；如需变更职位，请在“编辑”中调整。','wide enterprise-form-context'));arrays.push({name,inputs,min:resolved.minItems||0});continue;
      }
      field(form,name,raw,required||Boolean(prefill&&context.row[name]&&['full_name','department_name','course_name','title'].includes(name)));
      const input=form.querySelector('[name="'+name+'"]');
      if(input&&prefill&&Object.hasOwn(context.row,name)&&!['reason','note','comment','content'].includes(name)){
        setValue(input,context.row[name]);initial.set(name,input.value);
      }
      if(input&&name==='position_title'&&context?.key==='employees'&&String(context.bindings.employee_id)===String(employee.employee_id))input.disabled=true;
    }
    if(receipt){const preview=node('div',undefined,'wide enterprise-preview');renderObject(preview,{action:receipt.action,target:receipt.target,fields:receipt.fields});form.prepend(preview);}
    const confirmation=node('label',undefined,'wide enterprise-confirmation');
    const confirmInput=node('input');confirmInput.type='checkbox';
    confirmation.append(confirmInput,node('span','我已确认，要对当前记录执行此操作。'));confirmation.hidden=!destructive(op);form.append(confirmation);
    const result=node('div',undefined,'wide enterprise-action-result');result.setAttribute('aria-live','polite');
    const actions=node('div',undefined,'form-actions'),submit=node('button',destructive(op)?'确认'+actionName(op):op.path.endsWith('/confirm')?'确认办理':context?'保存':'提交','button');submit.type='submit';
    actions.append(button('取消',()=>{if(!busy)dialog.close();}),submit);form.append(actions,result);
    let signature=null,key=null,sending=false;
    form.addEventListener('submit',async event=>{
      event.preventDefault();if(sending||!active(g)||!form.reportValidity()||form.dataset.missingVersion)return;
      let values;
      try{
        values={...readFields(form),...automatic};
        for(const array of arrays){values[array.name]=array.inputs.filter(input=>input.checked).map(input=>input.value);if(values[array.name].length<array.min)throw Error('请至少选择一个'+label(array.name)+'。');}
        for(const [name,before]of initial){
          const input=form.querySelector('[name="'+name+'"]');
          if(before!==''&&input?.value===''&&properties[name]?.anyOf?.some(item=>item.type==='null'))values[name]=null;
        }
        const needsConfirmation=destructive(op)||['disabled','left'].includes(values.status)||values.event_status==='cancelled';
        if(needsConfirmation&&!confirmInput.checked){confirmation.hidden=false;result.replaceChildren(node('p','请勾选确认后再提交。','live-error'));confirmInput.focus();return;}
        const path=bindPath(op.path,context?.bindings||{}),query=new URLSearchParams();
        for(const parameter of op.parameters||[])if(parameter.in==='query'&&values[parameter.name]!==undefined){query.set(parameter.name,String(values[parameter.name]));delete values[parameter.name];}
        const currentSignature=JSON.stringify({path,values,query:String(query)});
        if(currentSignature!==signature){signature=currentSignature;key=createRequestId();}
        let payload=values;
        if(multipart){payload=new FormData();for(const [name,value]of Object.entries(values))payload.append(name,String(value));for(const input of form.querySelectorAll('input[type=file]'))if(input.files[0])payload.append(input.name,input.files[0]);}
        sending=true;submit.disabled=true;setBusy(true);result.replaceChildren(node('p','正在提交……','live-status'));
        const data=await api(path+(query.size?'?'+query:''),{method:op.method,body:payload,headers:{'Idempotency-Key':key},timeoutMs:20000});
        key=null;signature=null;
        if(!active(g))return;
        if(op.path===E+'command'){
          result.replaceChildren();renderObject(result,data);
          const confirmationOp=findOp('POST',E+'command/confirm');
          if(data?.token&&!data.needs_clarification&&confirmationOp){
            result.append(button('继续确认办理',()=>{
              content.replaceChildren(actionForm(confirmationOp,null,g,{receipt:data}));message('请核对办理内容，点击确认后才会执行。');
            },'button'));
          }
          return;
        }
        if(op.path.endsWith('/phone-candidates')){
          result.replaceChildren();table(result,data,path,row=>openRecord('customer',row));return;
        }
        if(!context&&['onboarding/ask','nl2sql','voice/transcribe'].some(suffix=>op.path.endsWith(suffix))){
          result.replaceChildren();if(Array.isArray(data?.rows)||Array.isArray(data?.items)||Array.isArray(data))table(result,data,path);else if(data&&typeof data==='object')renderObject(result,data);else result.append(node('p',String(data??'操作成功。')));return;
        }
        const refreshResults=await refreshLists();
        const failed=refreshResults.some(item=>item.status==='rejected'||item.value===false);
        if(!active(g))return;
        if(!context||destructive(op)){
          dialog.close();notify(failed?'操作已保存，但列表刷新失败，请重新查询。':'操作成功，列表已更新。',failed);return;
        }
        context.views.clear();
        if(data&&typeof data==='object'&&!Array.isArray(data))context.row={...context.row,...data};
        try{
          const fresh=await latest(context);
          fresh.parentContext=context.parentContext;
          if(active(g))showRecord(fresh,g,failed?'操作已保存，但部分列表刷新失败，请重新查询。':'保存成功，已读取最新记录。');
        }catch(error){if(active(g)){content.replaceChildren(button('重新读取记录',()=>openRecord(context.key,context.row,context.bindings)));message('操作已保存，重新读取记录失败：'+error.message,true);}}
      }catch(error){
        if(!active(g))return;result.replaceChildren(node('p',error.message,'live-error'));
        if(error.code===409&&context)result.append(button('重新读取记录',()=>openRecord(context.key,context.row,context.bindings)));
      }finally{sending=false;submit.disabled=false;if(active(g))setBusy(false);}
    });
    return form;
  }

  function openTool(op){
    const g=begin(actionName(op));content.append(actionForm(op,null,g));
  }
  function openCreate(op){const g=begin(actionName(op));content.append(actionForm(op,null,g));}

  async function allRows(op,bindings={},isCurrent=()=>true){
    const rows=[];let offset=0;
    while(isCurrent()){
      const data=await api(bindPath(op.path,bindings)+`?limit=20&offset=${offset}`),items=rowsOf(data);rows.push(...items);offset+=items.length;
      if(!items.length||data.total===undefined||offset>=data.total)return rows;
    }
    return [];
  }
  async function openTodo(row){
    if(row.type==='ticket'||row.type==='leave'){
      const key=row.type==='ticket'?'tickets':'internal/leave',config=resources[key];
      if(!findOp('GET',config.path+'/{'+config.id+'}')){begin(config.name+'详情');message('当前账号没有此业务的查看和办理权限，请由负责人员处理。',true);return;}
      return openRecord(key,{[config.id]:row.id});
    }
    if(row.type!=='followup')return openRecord('todos',row);
    const g=begin('客户跟进详情');content.append(node('p','正在定位跟进记录……','live-status'));
    try{
      const customers=findOp('GET',E+'customer'),followups=findOp('GET',E+'customer/{customer_id}/followups');
      if(!customers||!followups)throw Error('当前账号没有客户跟进访问权限。');
      const customerRows=await allRows(customers,{},()=>active(g));
      for(const customer of customerRows){
        if(!active(g))return;
        const bindings=recordBindings('customer',customer);
        const records=await allRows(followups,bindings,()=>active(g));
        const found=records.find(item=>String(item.followup_id??item.id)===String(row.id));
        if(found){const context=contextFor('followups',found,bindings);context.parentContext=contextFor('customer',customer);showRecord(context,g);return;}
      }
      throw Error('未找到可访问的跟进记录，请刷新待办列表。');
    }catch(error){if(active(g)){content.replaceChildren();message(error.message,true);}}
  }

  function listCard(op){
    const key=resourceForPath(op.path),config=resources[key];
    const section=node('section',undefined,'section-card enterprise-list');section.dataset.resource=key;
    const header=node('div',undefined,'section-title'),heading=node('h2',config.name+(op.path.endsWith('/assignments')?' · 待分派':'')),toolbar=node('div',undefined,'enterprise-list-actions');
    header.append(heading,toolbar);
    const create=all.find(item=>item.method==='POST'&&item.path===op.path);
    if(create)toolbar.append(button('新增'+config.name,()=>openCreate(create),'button small'));
    const body=node('div',undefined,'live-body'),filters=node('form',undefined,'live-form live-pagination-query'),output=node('div',undefined,'live-result'),state=node('div');state.setAttribute('aria-live','polite');
    const parameters=(op.parameters||[]).filter(parameter=>parameter.in==='query'&&!['limit','offset','unread_only','manage','tree'].includes(parameter.name));
    for(const parameter of parameters)field(filters,parameter.name,parameter.schema,parameter.required);
    if(key==='knowledge'&&grants.has('enterprise.knowledge.manage')){
      const parameter=(op.parameters||[]).find(item=>item.name==='manage');if(parameter)field(filters,'manage',parameter.schema,false);
    }
    if(key==='notifications'){
      const parameter=(op.parameters||[]).find(item=>item.name==='unread_only');if(parameter)field(filters,'unread_only',parameter.schema,false);
    }
    const refresh=button('查询',()=>controller.load(),'button secondary small');toolbar.append(refresh);
    if(parameters.length||filters.childElementCount){const actions=node('div',undefined,'form-actions'),submit=node('button','应用筛选','button secondary small');submit.type='submit';actions.append(submit);filters.append(actions);body.append(filters);}
    body.append(state,output);section.append(header,body);main.append(section);
    const controller={key,rows:[],sequence:0,async load(){
      const sequence=++this.sequence;refresh.disabled=true;
      try{
        if(!filters.reportValidity())return false;
        const query=new URLSearchParams(readFields(filters));
        if((op.parameters||[]).some(item=>item.name==='limit'))query.set('limit','20');
        if((op.parameters||[]).some(item=>item.name==='offset'))query.set('offset','0');
        const data=await api(op.path+(query.size?'?'+query:''));
        if(sequence!==this.sequence)return true;this.rows=rowsOf(data);
        state.replaceChildren();table(output,data,op.path,row=>key==='todos'?openTodo(row):openRecord(key,row));return true;
      }catch(error){if(sequence===this.sequence){this.rows=[];output.replaceChildren();state.replaceChildren(node('p',error.message,'live-error'));}return false;}
      finally{if(sequence===this.sequence)refresh.disabled=false;}
    }};
    filters.addEventListener('submit',event=>{event.preventDefault();controller.load();});controllers.push(controller);return controller;
  }

  const lists=pageOps.filter(op=>op.method==='GET'&&!op.path.includes('{')&&resources[resourceForPath(op.path)]);
  const tools=pageOps.filter(op=>op.method==='POST'&&!op.path.includes('{')&&(
    !resources[resourceForPath(op.path)]||op.path.endsWith('/phone-candidates'))&&!op.path.endsWith('/confirm'));
  if(tools.length){
    const section=node('section',undefined,'section-card enterprise-tools'),toolbar=node('div',undefined,'enterprise-list-actions');
    section.append(node('h2','业务办理'));for(const op of tools)toolbar.append(button(actionName(op),()=>openTool(op),'button secondary'));section.append(toolbar);main.append(section);
  }
  for(const op of lists)listCard(op);
  // Pages used only for creation or confirmation keep their entry in the same dialog workflow.
  if(!lists.length&&!tools.length){
    const creates=pageOps.filter(op=>op.method==='POST'&&!op.path.includes('{')&&!op.path.endsWith('/confirm'));
    for(const op of creates)main.append(button(actionName(op),()=>openCreate(op),'button'));
    if(!creates.length)main.append(node('p','当前账号没有可用的业务操作。','live-status'));
  }
  await Promise.allSettled(controllers.map(controller=>controller.load()));
  // 通知中心和刷新详情页沿用公共记录定位，展示前仍重新读取最新授权记录。
  const detailResources={
    'enterprise/customer-detail.html':'customer','enterprise/student-detail.html':'students',
    'enterprise/daily-report-detail.html':'daily-report','enterprise/ticket-detail.html':'tickets',
    'enterprise/knowledge-detail.html':'knowledge','enterprise/leave-detail.html':'internal/leave',
    'enterprise/warning-detail.html':'internal/warnings',
  };
  const target=page==='enterprise/followups.html'&&selection.followup_id?'followups':detailResources[page];
  if(target){
    const config=resources[target],id=selection[config.id];
    if(Number.isSafeInteger(Number(id))&&Number(id)>0&&all.some(op=>op.method==='GET'&&resourceForPath(op.path)===target)){
      await openRecord(target,{[config.id]:Number(id)},selection);
    }
  }
  return {dialog,refresh:refreshLists};
}
