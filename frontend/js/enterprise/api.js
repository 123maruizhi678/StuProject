// 企业页面共用客户端：同源会话、业务信封、写入幂等和身份校验。
const keys = new Map();
export const $ = id => document.getElementById(id);
export function text(tag, value, className) {
  const element = document.createElement(tag);
  element.textContent = value ?? '—';
  if (className) element.className = className;
  return element;
}
export function setToken(token) {
  if (token) sessionStorage.setItem('enterprise.token', token);
  else sessionStorage.removeItem('enterprise.token');
}
export function hasToken() { return Boolean(sessionStorage.getItem('enterprise.token')); }
export function logout() {
  setToken(null);
  keys.clear();
  if (window.parent !== window) window.parent.postMessage({type:'enterprise:logout'}, location.origin);
  else location.reload();
}
export async function request(path, {method='GET', body, key, form=false, signal}={}) {
  const headers = {}, token = sessionStorage.getItem('enterprise.token');
  if (token) headers.Authorization = 'Bearer ' + token;
  if (body !== undefined && !form) headers['Content-Type'] = 'application/json';
  const fingerprint = method + '|' + path + '|' + JSON.stringify(form ? null : body);
  if (method !== 'GET' && !path.startsWith('/api/v1/auth/')) {
    if (!keys.has(fingerprint)) keys.set(fingerprint, crypto.randomUUID());
    headers['Idempotency-Key'] = key || keys.get(fingerprint);
  }
  let response;
  try {
    response = await fetch(path.startsWith('/api/') ? path : '/api/v1/enterprise'+path,
      {method, headers, body:body === undefined ? undefined : form ? body : JSON.stringify(body), signal});
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw Error('网络连接失败，请检查服务后重试。');
  }
  let payload;
  try { payload = await response.json(); }
  catch { throw Error('服务返回异常，请稍后重试。'); }
  if (!response.ok || payload.code !== 0) {
    if (response.status === 401 || payload.code === 401) logout();
    const error = Error(payload.message || payload.detail || '请求未完成');
    error.code = payload.code || response.status;
    throw error;
  }
  keys.delete(fingerprint);
  return payload.data;
}
export const can = (me, permission) => me.permissions?.includes('enterprise.'+permission);
export async function requireEmployee(permission) {
  if (!hasToken()) throw Error('请先从企业管理入口登录。');
  const access = await request('/api/v1/auth/me/access');
  if (!['employee','admin'].includes(access.identity_type)) throw Error('当前身份不能访问企业工作台。');
  const me = await request('/me/permissions');
  if (permission && !can(me, permission)) throw Error('当前账户没有此功能的访问权限。');
  return me;
}
export function deny(error) {
  document.body.replaceChildren();
  const panel = text('section', '', 'panel access-denied');
  panel.append(text('span','ACCESS CONTROL','eyebrow'), text('h1','暂时无法访问'), text('p',error.message,'muted'));
  const link = text('a','返回企业管理入口','button secondary');
  link.href = '/enterprise'; link.target = '_top';
  panel.append(link); document.body.append(panel);
}
export function navigate(key) {
  if (window.parent !== window) window.parent.postMessage({type:'enterprise:navigate',key},location.origin);
  else location.href = '/enterprise#/'+key;
}
