import { ApiError, request, tokenStore, createRequestId } from "../common/api.js";
import { assertModuleReady } from "../common/module-api.js";

export { ApiError as StudentApiError, tokenStore };
const pendingKeys = new Map();
export const requestId = () => createRequestId();

export async function api(path, { method = "GET", body, authenticated = true, key } = {}) {
  const target = "/" + path.replace(/^\//, "");
  if (authenticated && !tokenStore.get()) throw new ApiError("请先登录，再查看或办理本人业务。", 401);
  if (target.startsWith("/student/")) assertModuleReady(target);
  const signature = JSON.stringify([tokenStore.get(), method, target, body]);
  const headers = {};
  if (method !== "GET") {
    if (!pendingKeys.has(signature)) pendingKeys.set(signature, key || requestId());
    headers["Idempotency-Key"] = pendingKeys.get(signature);
  }
  const token = tokenStore.get();
  try {
    const data = await request(target, { method, body, authenticated, headers, timeoutMs: 90000 });
    if (authenticated && (!token || tokenStore.get() !== token)) throw new ApiError("登录会话已变化，请重新进入学生模块。", 401);
    if (method !== "GET") {
      pendingKeys.delete(signature);
      if (target.includes('/notifications/')) window.dispatchEvent(new Event('student:notifications-changed'));
    }
    return data;
  } catch (error) {
    if (!error.code && method !== "GET") throw new ApiError("请求结果尚未确认，请保持原内容重试，系统会核对原请求。", 0);
    throw error;
  }
}

export async function allPages(path) {
  const items = [];
  let offset = 0;
  for (;;) {
    const page = await api(`${path}${path.includes("?") ? "&" : "?"}limit=100&offset=${offset}`);
    items.push(...page.items);
    offset += page.items.length;
    if (offset >= page.total || !page.items.length) return items;
  }
}

window.addEventListener("auth:changed", () => pendingKeys.clear());
window.addEventListener("auth:expired", () => pendingKeys.clear());
