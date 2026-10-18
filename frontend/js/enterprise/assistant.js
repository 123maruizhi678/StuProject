import {createRequestId} from '../common/api.js';
import {inferEnterpriseIntent} from './assistant-intent.js';
import {mountVoiceInput} from './voice-input.js';

const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
const names={command:'办理预览',query:'查询结果',knowledge:'知识解答'};
export function mountEnterpriseAssistant({main,api,available,renderResult,openConfirmation,label}){
  const section=node('section',undefined,'section-card enterprise-assistant');
  const form=node('form',undefined,'enterprise-assistant-form'),caption=node('label','有什么需要我帮你处理？');caption.htmlFor='enterprise-assistant-input';
  const input=node('textarea');input.id='enterprise-assistant-input';input.name='message';input.rows=4;input.required=true;input.maxLength=10000;input.placeholder='例如：怎么请假？查询本周日报；新增客户张三，意向英国留学。';
  const hint=node('p','直接描述需求，系统自动识别业务。涉及数据变更时，会先展示内容供你确认。','enterprise-assistant-hint');
  const controls=node('div',undefined,'enterprise-assistant-controls'),send=node('button','发送','button');send.type='submit';controls.append(node('span','Ctrl + Enter 发送','enterprise-assistant-hint'),send);
  const state=node('p','','live-status');state.setAttribute('role','status');
  const history=node('div',undefined,'enterprise-assistant-history');history.setAttribute('aria-label','助手回复');
  form.append(caption,input,hint,controls,state);section.append(form,history);main.append(section);
  let sending=false,voiceActive=false,pending=null,retry=null;
  const update=()=>{send.disabled=sending||voiceActive;input.disabled=sending;};
  input.addEventListener('keydown',event=>{if(event.key==='Enter'&&(event.ctrlKey||event.metaKey)){event.preventDefault();form.requestSubmit();}});
  async function submit(event){
    event.preventDefault();if(sending||voiceActive||!form.reportValidity())return;
    const raw=input.value.trim();if(!raw){state.textContent='请先输入需要办理或咨询的内容。';return;}
    const inferred=inferEnterpriseIntent(raw),kind=inferred||(pending?'command':'knowledge');
    if(!available[kind]){state.textContent='当前账号没有处理这项需求的权限，请联系管理员核实。';return;}
    const text=kind==='command'&&pending&&!inferred?pending+'\n补充信息：'+raw:raw;
    if(text.length>(kind==='command'?10000:2000)){state.textContent=kind==='command'?'办理内容过长，请将内容缩短至 10000 字以内。':'问题过长，请将内容缩短至 2000 字以内。';return;}
    const path=kind==='command'?'/api/v1/enterprise/command':kind==='query'?'/api/v1/enterprise/nl2sql':'/api/v1/enterprise/onboarding/ask';
    const body=kind==='command'?{text}:kind==='query'?{question:text,filters:{}}:{question:text};
    const signature=JSON.stringify({path,body});
    if(retry?.signature!==signature)retry={signature,key:createRequestId()};
    sending=true;update();state.textContent='正在理解并处理你的需求……';
    const article=node('article',undefined,'enterprise-assistant-turn');article.append(node('p',raw,'enterprise-assistant-question'),node('h2',names[kind]));const result=node('div',undefined,'live-result');article.append(result);history.prepend(article);
    try{
      const data=await api(path,{method:'POST',body,headers:{'Idempotency-Key':retry.key},timeoutMs:60000});retry=null;
      if(kind==='knowledge'&&typeof data?.answer==='string'){
        result.append(node('p',data.answer,'enterprise-assistant-answer'));
        const citations=Array.isArray(data.citations)?data.citations:[];
        if(citations.length){
          result.append(node('h3','参考资料'));
          const list=node('ul');
          const seen=new Set();
          for(const citation of citations){
            const title=citation.document_name||citation.title||'知识条目 '+citation.id;
            const name=title+(citation.version?'（版本 '+citation.version+'）':'');
            if(!seen.has(name)){list.append(node('li',name));seen.add(name);}
          }
          result.append(list);
        }
      }else renderResult(result,data);
      pending=kind==='command'&&data?.needs_clarification?text:null;
      if(pending){const missing=(data.missing_fields||[]).map(label).join('、');result.append(node('p',missing?'请在输入框补充：'+missing+'。':'请在输入框补充具体对象和需要办理的内容。','live-status'));}
      if(kind==='command'&&data?.token&&!data.needs_clarification&&available.confirm){
        const confirm=node('button','核对并确认办理','button');confirm.type='button';confirm.onclick=()=>openConfirmation(data);result.append(confirm);
      }
      state.textContent=kind==='command'&&!pending?'已生成办理预览，请核对后确认。':pending?'等待补充信息。':'已完成。';input.value='';
    }catch(error){result.append(node('p',error.message,'live-error'));state.textContent='处理未完成，输入内容已保留，可重试。';}
    finally{sending=false;update();}
  }
  form.addEventListener('submit',submit);
  let voice=null;
  if(available.voice)voice=mountVoiceInput({
    onTranscript:text=>{input.value+=(input.value.trim()?'\n':'')+text;input.dispatchEvent(new Event('input',{bubbles:true}));input.focus();},
    onActiveChange:value=>{voiceActive=value;update();},
    transcribe:(audio,filename)=>{const body=new FormData();body.append('file',audio,filename);return api('/api/v1/enterprise/voice/transcribe',{method:'POST',body,timeoutMs:180000});},
  });
  return {input,voice};
}
