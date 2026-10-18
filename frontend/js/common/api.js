/** 公共请求工具：兼容 HTTP 错误与 code/message/data 业务信封。 */
const SESSION_KEY = "stuproject.auth.session";

export class ApiError extends Error {
  constructor(message, code = 0) {
    super(message);
    this.name = "ApiError";
    this.code = code;
  }
}

export function clearSession() {
  sessionStorage.removeItem(SESSION_KEY);
  for (const key of ['stuproject.live.selection','stuproject.command.preview','stuproject.student.preview']) sessionStorage.removeItem(key);
}

/** 同一标签页中的工作台与业务 iframe 同步身份事件。 */
export function publishAuthEvent(name = "auth:changed") {
  let root = window;
  try {
    while (root.parent && root.parent !== root && root.parent.location.origin === window.location.origin) root = root.parent;
  } catch { /* 跨域父页面不参与会话同步。 */ }
  function dispatch(target) {
    try {
      if (target.location.origin !== window.location.origin) return;
      target.dispatchEvent(new Event(name));
      for (let index = 0; index < (target.frames?.length || 0); index++) dispatch(target.frames[index]);
    } catch { /* 跳过跨域或已卸载的 iframe。 */ }
  }
  dispatch(root);
}

export function readSession() {
  try {
    const value = JSON.parse(sessionStorage.getItem(SESSION_KEY));
    if (value && typeof value.accessToken === "string" && value.accessToken &&
        Number.isFinite(value.expiresAt) && value.expiresAt > Date.now()) return value;
  } catch { /* 不使用损坏或过期的会话。 */ }
  clearSession();
  return null;
}

export function saveSession(data) {
  if (!data || typeof data.access_token !== "string" || !data.access_token ||
      data.token_type?.toLowerCase() !== "bearer" || !Number.isFinite(data.expires_in) || data.expires_in <= 0) {
    throw new ApiError("登录响应不完整，请联系管理员。");
  }
  clearSession();
  sessionStorage.setItem(SESSION_KEY, JSON.stringify({
    accessToken: data.access_token,
    expiresAt: Date.now() + data.expires_in * 1000,
  }));
}

/** 兼容学生模块的会话读取；令牌仍由统一登录按有效期保存。 */
export const tokenStore = Object.freeze({
  get: () => readSession()?.accessToken || null,
  clear: () => { clearSession(); publishAuthEvent(); },
});

export async function request(path, { method = "GET", body, authenticated = true, headers: extraHeaders = {}, timeoutMs = 15000 } = {}) {
  if (!path.startsWith("/") || path.startsWith("//") || path.includes("\\")) throw new ApiError("无效的接口路径。");
  const headers = { ...extraHeaders, Accept: "application/json" };
  const session = authenticated ? readSession() : null;
  if (session) headers.Authorization = `Bearer ${session.accessToken}`;
  const form = typeof FormData !== "undefined" && body instanceof FormData;
  if (body !== undefined && !form) headers["Content-Type"] = "application/json";
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  let response, result;
  try {
    response = await fetch(`/api/v1${path}`, {
      method, headers, body: body === undefined ? undefined : form ? body : JSON.stringify(body),
      signal: controller.signal, credentials: "same-origin", cache: "no-store",
    });
    result = await response.json();
  } catch (error) {
    throw new ApiError(error.name === "AbortError" ? "请求超时，请稍后重试。" : "无法连接服务或读取响应，请检查服务状态。");
  } finally {
    clearTimeout(timeout);
  }
  const code = response.ok && Number.isInteger(result?.code) ? result.code : response.status;
  if (code === 401 && authenticated) {
    clearSession();
    publishAuthEvent("auth:expired");
  }
  if (!response.ok || code !== 0) {
    let message = result?.message || (typeof result?.detail === "string" ? result.detail : "请求失败，请稍后重试。");
    if (code === 401) message = authenticated ? "登录已失效，请重新登录。" : "账号或密码不正确。";
    if (code === 403) message = "当前账号没有访问权限。";
    if (code === 422) message = path === "/auth/login" ? "请检查账号和密码的填写格式。" : "请检查提交内容的填写格式。";
    throw new ApiError(message, code);
  }
  if (!Object.hasOwn(result, "data")) throw new ApiError("服务响应格式不正确。");
  return result.data;
}

export const API = {
  publicAccess: () => request("/auth/public-access", { authenticated: false }),
  myAccess: () => request("/auth/me/access"),
  login: (username, password) => request("/auth/login", {
    method: "POST", body: { username, password }, authenticated: false,
  }),
};
