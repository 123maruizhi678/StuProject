import { ApiError, request } from "./api.js";
import { MODULES } from "./modules.js";

/** 未完成接口联调的模块只保留页面，禁止向历史接口发送业务请求。 */
export function assertModuleReady(path) {
  const module = MODULES.find(item => item.apiPrefix &&
    (path === item.apiPrefix || path.startsWith(`${item.apiPrefix}/`) || path.startsWith(`${item.apiPrefix}?`)));
  if (!module?.apiReady) throw new ApiError("该模块正在接入服务，暂不能查询或提交业务数据。", 503);
}

async function businessRequest(path, options) {
  assertModuleReady(path);
  return request(path, options);
}

export const API = {
  get: path => businessRequest(path),
  post: (path, body) => businessRequest(path, { method: "POST", body }),
  put: (path, body) => businessRequest(path, { method: "PUT", body }),
  upload: (path, body) => businessRequest(path, { method: "POST", body }),
};
