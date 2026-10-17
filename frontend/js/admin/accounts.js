"use strict";
const $=id=>document.getElementById(id);
const state={token:sessionStorage.getItem('enterprise.token'),options:null,offset:0,total:0,pending:null};
const identities={admin:'平台管理员',employee:'员工',student:'学生',customer:'客户'};
const profileKeys={employee:'employee_id',student:'student_id',customer:'customer_id'};
const fields={
  employee:[['employee_no','工号','text',true],['full_name','姓名','text',true],['department_id','所属部门','department',true],['position_title','职位','position',true],['joined_date','入职日期','date',false],['work_email','工作邮箱','email',false]],
  student:[['student_no','学号','text',true],['full_name','姓名','text',true],['department_id','所属部门','department',true],['customer_id','关联客户ID（可选）','number',false]],
  customer:[['full_name','姓名','text',true],['department_id','所属部门','department',true],['employee_id','顾问员工ID（可选）','number',false],['phone','联系电话（可选）','text',false],['education_level','学历（可选）','text',false],['target_country_code','意向国家码（可选）','text',false]]
};
function text(tag,value){const node=document.createElement(tag);node.textContent=value??'—';return node;}
function resetView(){for(const id of ['workspace','denied'])$(id).hidden=true;$('login').hidden=false;}
function logout(){sessionStorage.removeItem('enterprise.token');state.token=null;state.pending=null;resetView();}
async function request(path,{method='GET',body,key}={}){
  const headers={};if(state.token)headers.Authorization='Bearer '+state.token;
  if(body)headers['Content-Type']='application/json';if(key)headers['Idempotency-Key']=key;
  const response=await fetch('/api/v1'+path,{method,headers,body:body?JSON.stringify(body):undefined});
  let payload;try{payload=await response.json();}catch{throw Error('服务暂不可用，请稍后重试');}
  if(!response.ok||(payload.code!==undefined&&payload.code!==0)){
    if(response.status===401||payload.code===401)logout();
    throw Error(payload.message||payload.detail||'请求未完成');
  }
  return payload.code===undefined?payload:payload.data;
}
function inputField(key,label,type,required){
  const wrapper=text('label',label);let input;
  if(type==='department'||type==='position'){
    input=document.createElement('select');
    const options=type==='department'?state.options.departments.map(d=>[d.department_id,d.department_name]):Object.keys(state.options.positions).map(p=>[p,p]);
    for(const [value,name]of options){const option=text('option',name);option.value=value;input.append(option);}
  }else{input=document.createElement('input');input.type=type;if(type==='number'){input.min='1';input.step='1';}if(type==='date')input.value=state.options.today_beijing;}
  input.name=key;input.required=required;wrapper.append(input);return wrapper;
}
function renderFields(){
  const identity=$('identity-type').value;const mode=$('profile-mode').value;
  $('profile-fields').replaceChildren();$('mode-label').hidden=identity==='admin';$('register-error').textContent='';state.pending=null;
  if(identity==='admin'){$('profile-hint').textContent='平台管理员只创建用户账户，不绑定员工、学生或客户档案。';return;}
  if(mode==='existing')$('profile-fields').append(inputField(profileKeys[identity],identities[identity]+'档案ID','number',true));
  else for(const field of fields[identity])$('profile-fields').append(inputField(...field));
  $('profile-hint').textContent=identity==='student'?'学生必须有效且未归档；已绑定账户的档案不能重复开户。':identity==='employee'?'员工业务角色由档案职位自动确定；主管范围取所属部门。':'已归档客户不能开户，顾问须为同部门有效人员。';
}
async function loadAccounts(){
  try{const data=await request('/admin/accounts?limit=20&offset='+state.offset);state.total=data.total;$('account-count').textContent='共 '+data.total+' 个';$('account-rows').replaceChildren();
    for(const row of data.items){const tr=document.createElement('tr');for(const value of [row.user_id,row.username,identities[row.identity_type],row.employee_id,row.student_id,row.customer_id])tr.append(text('td',value));$('account-rows').append(tr);}
    $('previous').disabled=state.offset===0;$('next').disabled=state.offset+20>=state.total;$('page-info').textContent='第 '+(state.offset/20+1)+' 页';$('list-error').textContent='';
  }catch(error){$('list-error').textContent=error.message;}
}
async function start(){
  const me=await request('/auth/me/access');
  if(me.identity_type!=='admin'&&!me.is_admin){$('login').hidden=true;$('workspace').hidden=true;$('denied').hidden=false;$('employee-link').hidden=me.identity_type!=='employee';return;}
  state.options=await request('/admin/accounts/options');$('password-note').textContent='新账户初始密码统一为 '+state.options.initial_password+'，无需填写密码。';
  $('identity').textContent='平台管理员 · 账户 '+me.user_id;$('login').hidden=true;$('denied').hidden=true;$('workspace').hidden=false;renderFields();await loadAccounts();
}
function resultView(result){
  const panel=$('registration-result');panel.className='';panel.replaceChildren();
  for(const [label,value]of [['用户名',result.username],['账户ID',result.user_id],['身份',identities[result.identity_type]],['员工ID',result.employee_id],['学生ID',result.student_id],['客户ID',result.customer_id],['部门ID',result.department_id],['业务角色',result.role_codes.join('、')||'按身份授权']]){
    if(value===null||value===undefined)continue;const line=document.createElement('div');line.className='result-field';line.append(text('strong',label),text('span',value));panel.append(line);
  }
}
$('login-form').onsubmit=async event=>{event.preventDefault();const form=event.currentTarget,button=event.submitter;button.disabled=true;$('login-error').textContent='';try{const input=new FormData(form);const result=await request('/auth/login',{method:'POST',body:{username:input.get('username'),password:input.get('password')}});state.token=result.access_token;sessionStorage.setItem('enterprise.token',state.token);form.reset();await start();}catch(error){$('login-error').textContent=error.message;}finally{button.disabled=false;}};
$('register-form').onsubmit=async event=>{
  event.preventDefault();const button=event.submitter;button.disabled=true;$('register-error').textContent='';
  try{
    const identity=$('identity-type').value,body={identity_type:identity,username:$('new-username').value.trim()};
    if(identity!=='admin'){
      const profile={};for(const input of $('profile-fields').querySelectorAll('input,select'))if(input.value!=='')profile[input.name]=(input.type==='number'||input.name==='department_id')?Number(input.value):input.value;
      if($('profile-mode').value==='existing')Object.assign(body,profile);else body.profile=profile;
    }
    const fingerprint=JSON.stringify(body);if(!state.pending||state.pending.fingerprint!==fingerprint)state.pending={fingerprint,key:crypto.randomUUID()};
    const result=await request('/auth/register',{method:'POST',body,key:state.pending.key});resultView(result);state.pending=null;$('new-username').value='';state.offset=0;await loadAccounts();
  }catch(error){$('register-error').textContent=error.message;}finally{button.disabled=false;}
};
$('identity-type').onchange=renderFields;$('profile-mode').onchange=renderFields;
$('logout').onclick=logout;$('denied-logout').onclick=logout;$('refresh').onclick=loadAccounts;
$('previous').onclick=()=>{state.offset=Math.max(0,state.offset-20);loadAccounts();};$('next').onclick=()=>{state.offset+=20;loadAccounts();};
$('show-docs').onclick=async()=>{try{const schema=await request('/admin/openapi.json');$('registration-schema').textContent=JSON.stringify({request:schema.paths['/api/v1/auth/register'],schemas:schema.components.schemas},null,2);$('admin-docs').hidden=false;$('docs-error').textContent='';}catch(error){$('docs-error').textContent=error.message;}};
if(state.token)start().catch(error=>{resetView();$('login-error').textContent=error.message;});
