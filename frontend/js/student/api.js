import {tokenStore} from '../common/api.js';
export class StudentApiError extends Error{constructor(message,code){super(message);this.code=code;}}
const pendingKeys=new Map();
export function requestId(){if(crypto.randomUUID)return crypto.randomUUID();return Array.from(crypto.getRandomValues(new Uint8Array(20)),b=>b.toString(16).padStart(2,'0')).join('');}
export async function api(path,{method='GET',body,authenticated=true,key}={}){
 const headers={Accept:'application/json'};if(authenticated){const token=tokenStore.get();if(!token)throw new StudentApiError('请先登录，再查看或办理本人业务。',401);headers.Authorization='Bearer '+token;}if(body!==undefined)headers['Content-Type']='application/json';
 const signature=JSON.stringify([method,path,body]);if(method!=='GET'){if(!pendingKeys.has(signature))pendingKeys.set(signature,requestId());headers['Idempotency-Key']=key||pendingKeys.get(signature);}
 const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),90000);
 try{let response;try{response=await fetch('/api/v1/'+path.replace(/^\//,''),{method,headers,credentials:'omit',cache:'no-store',signal:controller.signal,body:body===undefined?undefined:JSON.stringify(body)});}catch{throw new StudentApiError(method==='GET'?'暂时无法连接服务，请稍后重新加载。':'请求结果尚未确认，请保持原内容重试，系统会核对原请求。',0);}let envelope;try{envelope=await response.json();}catch{throw new StudentApiError('服务返回格式异常，请稍后核实。',response.status);}if(!response.ok||envelope.code!==0){const code=envelope.code||response.status;if(code===401&&authenticated)tokenStore.clear();const message=typeof envelope.message==='string'?envelope.message:'服务暂不可用，请稍后重试。';throw new StudentApiError(code===401&&authenticated?'登录已失效，请重新登录。':message,code);}if(method!=='GET')pendingKeys.delete(signature);return envelope.data;}finally{clearTimeout(timeout);}
}
export async function allPages(path){const items=[];let offset=0;for(;;){const join=path.includes('?')?'&':'?';const page=await api(`${path}${join}limit=100&offset=${offset}`);items.push(...page.items);offset+=page.items.length;if(offset>=page.total||!page.items.length)break;}return items;}
export {tokenStore};
