import {$, text, request, requireEmployee, can, deny} from './api.js';
import {labels} from './catalog.js';
import {display} from './ui.js';

const modes={command:{name:'办理业务',permission:'command',path:'/command',example:'提交今天的日报，完成客户回访和项目资料整理。'},query:{name:'查询数据',permission:'query',path:'/nl2sql',example:'查看我能访问的客户跟进记录。'},knowledge:{name:'制度问答',permission:'knowledge.read',path:'/onboarding/ask',example:'新员工如何提交日报？'}};
let me,previewGeneration=0;
async function start(){
  me=await requireEmployee();
  for(const [key,mode]of Object.entries(modes))if(can(me,mode.permission)){
    const option=text('option',mode.name);option.value=key;$('assistant-mode').append(option);
    const button=text('button',mode.example,'suggestion');button.type='button';button.onclick=()=>{$('assistant-mode').value=key;updateMode();$('assistant-text').value=mode.example;$('assistant-text').focus();};$('suggestions').append(button);
  }
  if(!$('assistant-mode').options.length)throw Error('当前账户没有智能助手的访问权限。');
  $('voice-control').hidden=!can(me,'command');updateMode();document.querySelector('main').hidden=false;
}
function updateMode(){
  previewGeneration++;
  const key=$('assistant-mode').value;$('assistant-text').maxLength=key==='command'?10000:2000;
  $('assistant-text').placeholder=modes[key].example;
  // 更换模式即丢弃旧的确认预览。
  $('assistant-result').replaceChildren();$('assistant-result').hidden=true;
}
$('assistant-mode').onchange=updateMode;
$('assistant-text').addEventListener('input',()=>{previewGeneration++;$('assistant-result').replaceChildren();$('assistant-result').hidden=true;});
$('assistant-form').onsubmit=async event=>{
  event.preventDefault();const button=event.submitter,modeKey=$('assistant-mode').value,mode=modes[modeKey];
  const generation=++previewGeneration;
  button.disabled=true;$('assistant-result').hidden=false;$('assistant-result').replaceChildren(text('p','正在处理…','muted'));
  try{
    const input=$('assistant-text').value;
    const result=await request(mode.path,{method:'POST',body:modeKey==='command'?{text:input}:{question:input}});
    if(generation!==previewGeneration)return;
    const panel=$('assistant-result');panel.replaceChildren(text('h2',modeKey==='command'?'请核对办理内容':modeKey==='query'?'查询结果':'制度解答'));
    if(modeKey==='command'){
      if(result.action)panel.append(text('p','业务动作：'+result.action,'muted'));
      if(result.target && Object.keys(result.target).length)panel.append(text('p','办理对象：'+JSON.stringify(result.target),'muted'));
      for(const [field,value]of Object.entries(result.fields || {})){
        const line=text('div','','preview-field');line.append(text('strong',labels[field]||field),text('span',display(field,value)));panel.append(line);
      }
      if(result.needs_clarification)panel.append(text('p','请补充信息后重新发送：'+(result.missing_fields||[]).map(field=>labels[field]||field).join('、'),'muted'));
      else if(result.token){
        const confirm=text('button','确认办理'),confirmationKey=crypto.randomUUID();
        confirm.type='button';confirm.onclick=async()=>{
          confirm.disabled=true;panel.querySelector('.error')?.remove();
          try{await request('/command/confirm',{method:'POST',key:confirmationKey,body:{token:result.token,action:result.action,target:result.target,fields:result.fields}});panel.replaceChildren(text('h2','办理成功'),text('p','相关记录已更新，可前往业务页面查看。','muted'));}
          catch(error){panel.append(text('p',error.message,'error'));confirm.disabled=false;}
        };panel.append(confirm);
      }
    }else if(modeKey==='knowledge'){
      panel.append(text('pre',result.answer));
      for(const citation of result.citations || [])panel.append(text('p','来源 '+citation.id+' · 版本 '+citation.version,'muted'));
    }else{
      const rows=result.rows || [];
      if(!rows.length)panel.append(text('p','当前范围内没有匹配数据。','muted'));
      else{
        const scroll=text('div','','table-scroll'),table=document.createElement('table'),head=document.createElement('thead'),tr=document.createElement('tr'),body=document.createElement('tbody'),columns=Object.keys(rows[0]);
        for(const field of columns)tr.append(text('th',labels[field]||field));head.append(tr);
        for(const row of rows){const line=document.createElement('tr');for(const field of columns)line.append(text('td',display(field,row[field])));body.append(line);}
        table.append(head,body);scroll.append(table);panel.append(scroll);
      }
    }
  }catch(error){if(generation===previewGeneration)$('assistant-result').replaceChildren(text('p',error.message,'error'));}
  finally{button.disabled=false;}
};
$('audio').onchange=async event=>{
  const file=event.target.files[0];if(!file)return;
  try{
    if(file.size>20*1024*1024)throw Error('语音文件不能超过20MB。');
    $('audio').disabled=true;$('notice').textContent='正在转写语音…';
    const body=new FormData();body.append('file',file);
    const result=await request('/voice/transcribe',{method:'POST',body,form:true});
    previewGeneration++;$('assistant-result').replaceChildren();$('assistant-result').hidden=true;
    $('assistant-text').value=result.text;$('notice').textContent='语音已转写，请核对文字后发送。';
  }catch(error){$('notice').textContent=error.message;}
  finally{$('audio').disabled=false;event.target.value='';}
};
start().catch(deny);
