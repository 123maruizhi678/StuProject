// 公共后端请求：同时检查实际HTTP状态与业务信封，不向浏览器提供服务密钥。
const TOKEN_KEY = "stuproject.common.access_token";
export const tokenStore = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (token) => sessionStorage.setItem(TOKEN_KEY, token),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  constructor(message, code) { super(message); this.code = code; }
}

export async function request(path, {method = "GET", body, authenticated = false, idempotencyKey} = {}) {
  const headers = {"Accept": "application/json"};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (authenticated) {
    const token = tokenStore.get();
    if (!token) throw new ApiError("请先登录。", 401);
    headers.Authorization = "Bearer " + token;
  }
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
  let response;
  try {
    response = await fetch("/api/v1" + path, {
      method, headers, credentials: "omit", cache: "no-store",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("暂时无法连接服务，请稍后重试。", 0);
  }
  let envelope;
  try { envelope = await response.json(); }
  catch { throw new ApiError("服务返回异常，请稍后重试。", response.status); }
  if (!response.ok || envelope.code !== 0) {
    const code = envelope.code || response.status;
    if (code === 401 && authenticated) tokenStore.clear();
    const messages = {
      400: "请检查用户名和密码的填写格式。",
      401: authenticated ? "登录已失效，请重新登录。" : "用户名或密码不正确。",
      403: "当前账号或关联资料暂不可用，请联系管理员。",
      503: "登录服务暂不可用，请稍后重试。",
    };
    throw new ApiError(messages[code] || "请求失败，请稍后重试。", code);
  }
  return envelope.data;
}
