// Unified input, explicit mutation confirmation, navigation and microphone lifecycle.
// Every business API is intercepted; no real business record or microphone is used.
async (page)=>{
  const browser=page.context().browser(),contexts=[],checks=[],requests=[],errors=[];
  const assert=(value,message)=>{if(!value)throw Error(message);};
  const permissions=['command','query','knowledge.read','access'].map(name=>'enterprise.'+name);
  const schema=await (await page.request.get('http://127.0.0.1:8000/openapi.json')).json();
  let failNext=false,voiceUnavailable=false;
  async function setup(origin,mockMic=true,browserRecognition=false){
    const context=await browser.newContext();contexts.push(context);const p=await context.newPage();
    await p.route('**/openapi.json',route=>route.fulfill({json:schema}));
    p.on('pageerror',error=>errors.push(error.message));
    await p.addInitScript(({mockMic,browserRecognition})=>{
      sessionStorage.setItem('stuproject.auth.session',JSON.stringify({accessToken:'isolated-assistant-test',expiresAt:Date.now()+3600000}));
      window.micRequests=0;window.trackStops=0;window.micMode='normal';
      Object.defineProperty(window,'SpeechRecognition',{value:undefined,configurable:true});
      Object.defineProperty(window,'webkitSpeechRecognition',{value:undefined,configurable:true});
      if(browserRecognition){
        window.nativeStarts=0;window.nativeAborts=0;
        window.SpeechRecognition=class{
          constructor(){window.nativeRecognition=this;}
          start(){window.nativeStarts++;queueMicrotask(()=>this.onstart?.());}
          stop(){this.onend?.();}
          abort(){window.nativeAborts++;this.onend?.();}
        };
      }
      if(mockMic){
        const getUserMedia=async()=>{window.micRequests++;if(window.micMode==='denied')throw new DOMException('denied','NotAllowedError');if(window.micMode==='pending')await new Promise(resolve=>window.resolveMicrophone=resolve);return {getTracks:()=>[{stop:()=>window.trackStops++}]};};
        Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia},configurable:true});
        window.MediaRecorder=class{
          static isTypeSupported(type){return type.startsWith('audio/webm');}
          constructor(){this.state='inactive';}
          start(){this.state='recording';}
          stop(){this.state='inactive';this.ondataavailable?.({data:new Blob(['isolated audio'],{type:'audio/webm'})});this.onstop?.();}
        };
      }
    },{mockMic,browserRecognition});
    await p.route('**/api/v1/**',async route=>{
      const req=route.request(),path=new URL(req.url()).pathname;let data;
      const routes={'/enterprise/enterprise.html':{title:'企业工作台',module:'employee_workspace'},'/enterprise/assistant.html':{title:'企业智能助手',module:'employee_workspace'},'/common/workspace.html':{title:'通知中心'}};
      if(path.endsWith('/auth/me/access'))data={identity_type:'employee',user_id:7,display_name:'测试员工',permissions,navigation:{routes,modules:[{id:'employee_workspace',title:'企业智能助手',entry:'/enterprise/enterprise.html',pages:Object.entries(routes).filter(([route])=>route.startsWith('/enterprise/')).map(([route,meta])=>({route,...meta}))}]}};
      else if(path.endsWith('/me/permissions'))data={employee_id:7,permissions};
      else if(req.method()==='POST'){
        const body=path.endsWith('/voice/transcribe')?null:req.postDataJSON();
        requests.push({path,body,key:req.headers()['idempotency-key'],raw:body?null:req.postData().slice(0,100)});
        if(path.endsWith('/voice/transcribe')){
          if(voiceUnavailable)return route.fulfill({status:503,json:{code:503,message:'本地语音依赖未安装'}});
          data={text:'查询今天工作日报',requires_user_review:true,business_written:false};
        }
        else if(failNext){failNext=false;return route.fulfill({status:503,json:{code:503,message:'隔离服务暂不可用'}});}
        else if(path.endsWith('/command/confirm'))data={report_id:19,row_version:1};
        else if(path.endsWith('/command'))data=body.text.includes('不完整')&&!body.text.includes('补充信息')?{needs_clarification:true,missing_fields:['full_name']}:{token:'signed-isolated-preview',action:'daily.create',target:{},fields:{report_date:'2026-10-18',submitted_content:'测试日报'},needs_clarification:false};
        else if(path.endsWith('/nl2sql'))data={rows:[{report_date:'2026-10-18',submitted_content:'只读查询测试结果'}],row_count:1};
        else if(path.endsWith('/onboarding/ask'))data={answer:'请在学生请假办理页面提交申请，由主班主任审批。',citations:[{id:19,version:1,title:'学生请假申请与审批流程',document_name:'学生请假申请与审批流程.docx'}],mode:'rag'};
        else throw Error('Unexpected write '+path);
      }else data={};
      return route.fulfill({json:{code:0,message:'success',data}});
    });
    await p.goto(origin+'/enterprise/assistant.html');await p.locator('html[data-live-ready=true]').waitFor();
    return p;
  }
  try{
    const p=await setup('http://localhost:5173');
    assert(await p.getByRole('textbox',{name:'有什么需要我帮你处理？'}).count()===1,'缺少统一输入框');
    for(const name of ['企业工作台','解析工作指令','业务查询','知识问答','语音转文字'])assert(await p.getByRole('button',{name,exact:true}).count()===0&&await p.getByRole('link',{name,exact:true}).count()===0,'仍存在旧入口 '+name);
    checks.push('统一输入框替代业务按钮，旧工作台菜单已移除');
    const input=p.locator('#enterprise-assistant-input'),send=p.getByRole('button',{name:'发送',exact:true});
    async function ask(text,path){await input.fill(text);const response=p.waitForResponse(r=>new URL(r.url()).pathname===path);await send.click();await response;await send.waitFor({state:'visible'});await p.waitForFunction(()=>!document.querySelector('.enterprise-assistant-controls button').disabled);}
    await ask('怎么请假','/api/v1/enterprise/onboarding/ask');assert(await p.getByText('请在学生请假办理页面提交申请，由主班主任审批。',{exact:true}).count()===1,'知识结果未显示');
    assert(await p.getByText('学生请假申请与审批流程.docx（版本 1）',{exact:true}).count()===1,'未显示实际文档名称和引用版本');
    assert(await p.getByText('rag',{exact:true}).count()===0,'仍向用户显示内部回答模式');
    await ask('统计今天新增了多少客户','/api/v1/enterprise/nl2sql');assert(requests.at(-1).body.question==='统计今天新增了多少客户'&&Object.keys(requests.at(-1).body.filters).length===0,'数据查询参数错误');
    await ask('新增客户张三','/api/v1/enterprise/command');assert(!requests.some(r=>r.path.endsWith('/command/confirm')),'指令未经确认写入');
    await p.getByRole('button',{name:'核对并确认办理',exact:true}).click();const dialog=p.getByRole('dialog',{name:'确认办理',exact:true});await dialog.getByRole('button',{name:'确认办理',exact:true}).click();await dialog.waitFor({state:'hidden'});assert(requests.at(-1).body.token==='signed-isolated-preview','确认未携带签名凭证');
    checks.push('知识和统计自动路由，数据变更先预览再确认');
    await ask('新增客户信息不完整','/api/v1/enterprise/command');await ask('姓名李四','/api/v1/enterprise/command');assert(requests.at(-1).body.text.includes('补充信息：姓名李四'),'补充信息未保留原请求');
    failNext=true;await ask('提交今天日报，已回访三位客户','/api/v1/enterprise/command');const key=requests.at(-1).key;assert(await input.inputValue()==='提交今天日报，已回访三位客户','失败丢失输入');await ask('提交今天日报，已回访三位客户','/api/v1/enterprise/command');assert(requests.at(-1).key===key,'失败重试更换幂等键');checks.push('补充信息和失败重试保持请求上下文');
    const mic=p.getByRole('button',{name:'语音输入',exact:true});assert(await p.evaluate(()=>window.micRequests)===0,'页面加载时申请了麦克风');
    await input.fill('原有文字');const beforeVoice=requests.length;await mic.click();await p.getByRole('button',{name:'完成并转文字'}).waitFor({state:'visible'});await p.waitForFunction(()=>!document.querySelector('.enterprise-voice-actions button:last-child').disabled);
    assert(await p.evaluate(()=>window.micRequests)===1,'未申请麦克风权限');await p.getByRole('button',{name:'完成并转文字'}).click();await p.getByText('文字已填入输入框，请核对后发送。',{exact:true}).waitFor();
    assert(await input.inputValue()==='原有文字\n查询今天工作日报','识别文字未追加到输入框');assert(await p.evaluate(()=>window.trackStops)>0,'识别后麦克风未释放');assert(requests.length===beforeVoice+1&&requests.at(-1).path.endsWith('/voice/transcribe'),'转写自动触发了业务请求');
    await p.getByRole('button',{name:'取消',exact:true}).click();
    voiceUnavailable=true;await mic.click();await p.waitForFunction(()=>!document.querySelector('.enterprise-voice-actions button:last-child').disabled);await p.getByRole('button',{name:'完成并转文字'}).click();await p.getByText('语音转写服务未就绪，请联系管理员启动本地语音服务。',{exact:true}).waitFor();assert(!await send.isDisabled(),'转写服务未安装时没有恢复文字输入');await p.getByRole('button',{name:'取消',exact:true}).click();voiceUnavailable=false;
    await p.evaluate(()=>window.micMode='denied');await mic.click();await p.getByText('麦克风权限未允许，请在浏览器站点设置中允许麦克风后重试。',{exact:true}).waitFor();assert(await input.inputValue()==='原有文字\n查询今天工作日报','拒绝权限丢失文字');await p.getByRole('button',{name:'取消',exact:true}).click();
    await p.evaluate(()=>window.micMode='pending');const beforeCancel=requests.length;await mic.click();await p.getByRole('button',{name:'取消',exact:true}).click();const stopped=await p.evaluate(()=>window.trackStops);await p.evaluate(()=>window.resolveMicrophone());await p.waitForFunction(previous=>window.trackStops>previous,stopped);assert(requests.length===beforeCancel,'取消后仍上传录音');
    await p.evaluate(()=>window.micMode='normal');await mic.click();await p.waitForFunction(()=>document.querySelector('.enterprise-microphone').dataset.state==='recording');const beforeHide=requests.length;await p.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true})));assert(await mic.isVisible(),'页面恢复时丢失麦克风入口');assert(requests.length===beforeHide,'离开页面仍上传录音');
    checks.push('麦克风按点击申请权限，转写保留文字，取消和拒绝权限不提交业务');
    await p.goto('http://localhost:5173/enterprise/enterprise.html');await p.waitForURL('**/enterprise/assistant.html');await p.locator('#enterprise-assistant-input').waitFor();checks.push('旧工作台地址自动进入助手');
    await p.setViewportSize({width:1440,height:1000});await p.screenshot({path:'D:/project/StuProject/.runtime/enterprise-assistant-desktop.png',fullPage:true});
    await p.setViewportSize({width:390,height:844});assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'小屏界面横向溢出');await p.getByRole('button',{name:'语音输入',exact:true}).click();await p.getByRole('button',{name:'完成并转文字'}).waitFor();await p.screenshot({path:'D:/project/StuProject/.runtime/enterprise-assistant-mobile.png',fullPage:true});await p.getByRole('button',{name:'取消',exact:true}).click();
    const insecure=await setup('http://192.168.5.16:5173',false);await insecure.getByRole('button',{name:'语音输入',exact:true}).click();await insecure.getByRole('link',{name:'打开本机语音输入页面',exact:true}).waitFor();assert(await insecure.evaluate(()=>window.micRequests)===0,'HTTP 非安全页面仍尝试麦克风');checks.push('HTTP 地址提供本机安全入口，小屏浮窗不溢出');
    const native=await setup('http://localhost:5173',true,true),nativeInput=native.locator('#enterprise-assistant-input');
    await nativeInput.fill('原始文字');const beforeNative=requests.length;
    await native.getByRole('button',{name:'语音输入',exact:true}).click();await native.waitForFunction(()=>document.querySelector('.enterprise-microphone').dataset.state==='recording');
    await native.getByRole('button',{name:'完成并转文字'}).click();await native.getByText('文字已填入输入框，请核对后发送。',{exact:true}).waitFor();
    assert(await nativeInput.inputValue()==='原始文字\n查询今天工作日报','录音结果未填入文字');
    assert(requests.length===beforeNative+1&&requests.at(-1).path.endsWith('/voice/transcribe'),'录音未经过转写接口');
    assert(await native.evaluate(()=>nativeStarts)===0,'仍然调用无法连通的浏览器在线语音服务');
    assert(await native.evaluate(()=>micRequests)===1,'未使用麦克风录音');
    checks.push('浏览器即使提供在线语音接口，也统一使用本地录音转写路径');
    assert(!errors.length,errors.join('; '));return {passed:true,checks,businessApiCalls:requests.length,realDatabaseWritten:false,realMicrophoneUsed:false,errors};
  }finally{for(const context of contexts)await context.close();}
}
