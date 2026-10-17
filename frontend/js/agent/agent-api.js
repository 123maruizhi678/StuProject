/* 独立客服页的请求层。部署时可在本页之前设置 window.CUSTOMER_AGENT_API_BASE。 */
(function (global) {
  "use strict";
  var base = String(global.CUSTOMER_AGENT_API_BASE || "/api/v1").replace(/\/$/, "");
  var timeoutMs = 15000;

  async function request(path, options) {
    options = options || {};
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, timeoutMs);
    var headers = {};
    var init = { method: options.method || "GET", headers: headers, signal: controller.signal };
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(options.body);
    }
    try {
      var response = await fetch(base + path, init);
      var payload;
      try { payload = await response.json(); }
      catch (_) { throw new Error("服务返回了无法解析的数据（HTTP " + response.status + "）"); }
      if (!response.ok) {
        throw new Error((payload && payload.message) || ("请求失败（HTTP " + response.status + "）"));
      }
      if (!payload || typeof payload.code !== "number") throw new Error("服务响应格式不符合接口约定");
      if (payload.code !== 0) {
        var error = new Error(payload.message || "请求未成功");
        error.code = payload.code;
        throw error;
      }
      return payload.data;
    } catch (error) {
      if (error.name === "AbortError") throw new Error("请求超时，请检查服务状态后重试");
      if (error instanceof TypeError) throw new Error("无法连接客服服务，请确认 API 地址和服务已启动");
      throw error;
    } finally { clearTimeout(timer); }
  }

  global.CustomerAgentAPI = Object.freeze({
    request: request,
    chat: function (body) { return request("/agent/chat", { method: "POST", body: body }); },
    events: function (status) { return request("/agent/events" + (status ? "?status=" + encodeURIComponent(status) : "")); },
    event: function (id) { return request("/agent/events/" + encodeURIComponent(id)); },
    signup: function (body) { return request("/agent/events/signup", { method: "POST", body: body }); },
    courses: function (category) { return request("/agent/courses" + (category ? "?category=" + encodeURIComponent(category) : "")); },
    faq: function (question) { return request("/agent/faq" + (question ? "?question=" + encodeURIComponent(question) : "")); }
  });
})(window);
