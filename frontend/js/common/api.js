/* 统一 API 客户端：处理统一响应 {code, message, data} */
const API = (() => {
  const BASE = "/api/v1";

  async function request(method, path, body, isForm = false, key) {
    const opts = { method, headers: {} };
    const token=sessionStorage.getItem('stu.access');
    if(token) opts.headers.Authorization='Bearer '+token;
    if(key) opts.headers['Idempotency-Key']=key;
    if (isForm) {
      opts.body = body; // FormData
    } else if (body !== undefined && body !== null) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    let resp;
    try {
      resp = await fetch(BASE + path, opts);
    } catch (e) {
      throw new Error("网络连接失败，请确认服务已启动");
    }
    let json;
    try {
      json = await resp.json();
    } catch (e) {
      throw new Error(`服务返回异常（HTTP ${resp.status}）`);
    }
    if (!resp.ok || json.code !== 0) {
      const err = new Error(json.message || "请求失败");
      err.code = json.code || resp.status;
      if(err.code===401)sessionStorage.removeItem("stu.access");
      throw err;
    }
    return json.data;
  }

  return {
    request,
    get: (p) => request("GET", p),
    post: (p, b) => request("POST", p, b),
    put: (p, b) => request("PUT", p, b),
    upload: (p, formData) => request("POST", p, formData, true),
  };
})();
