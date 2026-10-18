const micSvg='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/></svg>';
const element=(tag,text,cls)=>{const el=document.createElement(tag);if(text)el.textContent=text;if(cls)el.className=cls;return el;};

export function mountVoiceInput({onTranscript,transcribe,onActiveChange=()=>{}}) {
  const host=element('div',null,'enterprise-voice');
  const trigger=element('button',null,'enterprise-microphone');trigger.type='button';trigger.innerHTML=micSvg;trigger.setAttribute('aria-label','语音输入');trigger.setAttribute('aria-expanded','false');trigger.title='语音输入';
  const panel=element('section',null,'enterprise-voice-panel');panel.hidden=true;panel.setAttribute('role','dialog');panel.setAttribute('aria-labelledby','enterprise-voice-title');
  const title=element('h2','语音输入');title.id='enterprise-voice-title';
  const status=element('p','点击麦克风后开始录音。','enterprise-voice-status');status.setAttribute('aria-live','polite');
  const note=element('p','识别后填入输入框，核对后再发送。','enterprise-assistant-hint');
  const actions=element('div',null,'enterprise-voice-actions');
  const finish=element('button','完成并转文字','button small');finish.type='button';finish.disabled=true;
  const cancel=element('button','取消','button secondary small');cancel.type='button';
  actions.append(cancel,finish);panel.append(title,status,note,actions);host.append(panel,trigger);document.body.append(host);
  let generation=0,stream=null,recorder=null,timer=null,elapsed=null,chunks=[],cancelled=false,disposed=false,phase='idle';
  function setPhase(value){phase=value;onActiveChange(['requesting','recording','transcribing'].includes(value));trigger.dataset.state=value;trigger.setAttribute('aria-label',value==='recording'?'结束录音':'语音输入');}
  function release(){clearTimeout(timer);clearInterval(elapsed);timer=elapsed=null;stream?.getTracks().forEach(track=>track.stop());stream=null;}
  function show(text){status.textContent=text;panel.hidden=false;trigger.setAttribute('aria-expanded','true');}
  function stop(){
    if(phase!=='recording')return;
    finish.disabled=true;
    if(recorder?.state==='recording')recorder.stop();
  }
  function dismiss(){
    generation++;cancelled=true;
    if(recorder?.state==='recording')recorder.stop();
    release();setPhase('idle');panel.hidden=true;trigger.setAttribute('aria-expanded','false');trigger.focus();
  }
  async function start(){
    if(disposed||['requesting','transcribing'].includes(phase))return;
    const current=++generation;cancelled=false;finish.disabled=true;
    show('正在申请麦克风权限，请在浏览器提示中选择允许。');
    if(!window.isSecureContext){
      setPhase('idle');show('当前 HTTP 地址无法调用麦克风。请使用 HTTPS，或在本机 localhost 页面登录后使用。');
      if(location.port){const link=element('a','打开本机语音输入页面');link.href=`http://localhost:${location.port}/enterprise/assistant.html`;status.append(document.createElement('br'),link);}
      return;
    }
    note.textContent='录音由语音转写服务识别。完成后核对文字再发送。';
    if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){setPhase('idle');show('当前浏览器不支持麦克风录音，请使用最新版 Edge 或 Chrome。');return;}
    setPhase('requesting');
    try{
      const acquired=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true},video:false});
      if(disposed||current!==generation){acquired.getTracks().forEach(track=>track.stop());return;}
      stream=acquired;chunks=[];
      const type=['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'].find(type=>MediaRecorder.isTypeSupported(type));
      if(!type)throw Error('当前浏览器没有可用的录音格式，请使用 Edge 或 Chrome。');
      recorder=new MediaRecorder(stream,{mimeType:type});
      let size=0;
      recorder.ondataavailable=event=>{
        if(!event.data.size||current!==generation)return;
        size+=event.data.size;
        if(size>20*1024*1024){cancelled=true;stop();release();setPhase('idle');show('录音超过大小限制，请缩短后重试。');return;}
        chunks.push(event.data);
      };
      recorder.onerror=()=>{if(current===generation){cancelled=true;release();setPhase('idle');finish.disabled=true;show('录音中断，请检查麦克风后重试。');}};
      recorder.onstop=async()=>{
        if(current!==generation)return;
        release();
        if(cancelled||disposed||current!==generation)return;
        const audio=new Blob(chunks,{type});chunks=[];
        if(!audio.size){setPhase('idle');show('没有录到声音，请重新录音。');return;}
        setPhase('transcribing');show('正在识别录音……');
        try{
          const extension=type.includes('mp4')?'m4a':type.includes('ogg')?'ogg':'webm';
          const data=await transcribe(audio,'voice-input.'+extension);
          if(disposed||current!==generation)return;
          const text=data?.text?.trim();
          if(!text){show('没有识别到文字，请靠近麦克风后重试。');return;}
          onTranscript(text);show('文字已填入输入框，请核对后发送。');
        }catch(error){if(!disposed&&current===generation)show(/语音依赖未安装|语音模型/.test(error.message)?'语音转写服务未就绪，请联系管理员启动本地语音服务。':'语音识别失败：'+error.message);}
        finally{if(!disposed&&current===generation)setPhase('idle');}
      };
      recorder.start(1000);setPhase('recording');finish.disabled=false;
      const started=Date.now();const update=()=>show(`正在录音 ${Math.floor((Date.now()-started)/1000)} 秒，完成后点击“完成并转文字”。`);update();elapsed=setInterval(update,1000);
      timer=setTimeout(stop,60000);
    }catch(error){
      if(disposed||current!==generation)return;
      release();setPhase('idle');
      const message=error.name==='NotAllowedError'?'麦克风权限未允许，请在浏览器站点设置中允许麦克风后重试。':error.name==='NotFoundError'?'未找到麦克风，请连接设备后重试。':error.name==='NotReadableError'?'麦克风正被其他程序占用，请关闭占用程序后重试。':error.message;
      show(message);
    }
  }
  trigger.onclick=()=>phase==='recording'?stop():start();finish.onclick=stop;cancel.onclick=dismiss;
  const escape=event=>{if(event.key==='Escape'&&!panel.hidden){dismiss();}};
  const hide=()=>dismiss();
  const dispose=()=>{disposed=true;dismiss();document.removeEventListener('keydown',escape);window.removeEventListener('pagehide',hide);host.remove();};
  document.addEventListener('keydown',escape);window.addEventListener('pagehide',hide);
  return {dispose,cancel:dismiss};
}
