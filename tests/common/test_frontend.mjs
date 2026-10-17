/** 原生 Node 测试公共前端逻辑；不依赖 npm 包、浏览器或外部服务。 */
import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";
import { readFile } from "node:fs/promises";

const load = async path => import(`data:text/javascript;base64,${Buffer.from(await readFile(new URL(path, import.meta.url), "utf8")).toString("base64")}`);
const api = await load("../../frontend/js/common/api.js");
const modules = await load("../../frontend/js/common/modules.js");

beforeEach(() => {
  const storage = new Map();
  globalThis.sessionStorage = {
    getItem: key => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
    removeItem: key => storage.delete(key),
  };
  globalThis.window = new EventTarget();
  window.location = { origin: "http://fictional.test" };
});

function reply(status, data) {
  return { status, ok: status >= 200 && status < 300, json: async () => data };
}

test("登录仅提交账号密码，不转发先前的令牌", async () => {
  api.saveSession({ access_token: "fake-old-token", token_type: "bearer", expires_in: 60 });
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/v1/auth/login");
    assert.equal(options.headers.Authorization, undefined);
    assert.deepEqual(JSON.parse(options.body), { username: "fake-user", password: "fake-password" });
    return reply(200, { code: 0, data: { access_token: "fake-new-token" } });
  };
  await api.API.login("fake-user", "fake-password");
});

test("受保护请求附带 Bearer，公开请求不附带", async () => {
  api.saveSession({ access_token: "fake-token", token_type: "bearer", expires_in: 60 });
  const seen = [];
  globalThis.fetch = async (_, options) => { seen.push(options.headers.Authorization); return reply(200, { code: 0, data: {} }); };
  await api.API.myAccess();
  await api.API.publicAccess();
  assert.deepEqual(seen, ["Bearer fake-token", undefined]);
});

test("过期与损坏会话被清除", () => {
  sessionStorage.setItem("stuproject.auth.session", "not-json");
  assert.equal(api.readSession(), null);
  sessionStorage.setItem("stuproject.auth.session", JSON.stringify({ accessToken: "fake", expiresAt: 1 }));
  assert.equal(api.readSession(), null);
  assert.equal(sessionStorage.getItem("stuproject.auth.session"), null);
});

test("HTTP401 和信封401都清除会话并通知主入口", async () => {
  let events = 0;
  window.addEventListener("auth:expired", () => events++);
  for (const [status, body] of [[401, { detail: "invalid" }], [200, { code: 401, message: "invalid", data: null }]]) {
    api.saveSession({ access_token: "fake-token", token_type: "bearer", expires_in: 60 });
    globalThis.fetch = async () => reply(status, body);
    await assert.rejects(api.API.myAccess, error => error.code === 401);
    assert.equal(api.readSession(), null);
  }
  assert.equal(events, 2);
});

test("403拒绝访问且保留仍有效的登录会话", async () => {
  api.saveSession({ access_token: "fake-token", token_type: "bearer", expires_in: 60 });
  globalThis.fetch = async () => reply(200, { code: 403, message: "forbidden", data: null });
  await assert.rejects(api.API.myAccess, error => error.code === 403);
  assert.ok(api.readSession());
});

test("网络与非JSON错误返回可读提示", async () => {
  globalThis.fetch = async () => { throw new TypeError("fake-network-error"); };
  await assert.rejects(api.API.publicAccess, /无法连接/);
  globalThis.fetch = async () => ({ json: async () => { throw new SyntaxError("not-json"); } });
  await assert.rejects(api.API.publicAccess, /无法连接/);
});

test("权限导航只使用后端授权页面或模块", () => {
  const report = modules.MODULES.find(module => module.id === "report");
  assert.equal(modules.canAccess(report, { pages: { report: {} }, modules: {} }), true);
  assert.equal(modules.canAccess(report, { pages: {}, modules: { report_center: {} } }), true);
  assert.equal(modules.canAccess(report, { pages: {}, modules: {} }), false);
});

test("返回地址和业务页面必须位于本站允许的位置", () => {
  assert.equal(modules.safeReturnPath("https://outside.test"), "/");
  assert.equal(modules.safeReturnPath("//outside.test"), "/");
  assert.equal(modules.safeReturnPath("/account#access"), "/account#access");
  assert.equal(modules.moduleEntry({ entry: "https://outside.test/a.html" }), null);
  assert.equal(modules.moduleEntry({ entry: "/static/js/common/api.js" }), null);
  assert.equal(modules.moduleEntry({ entry: "/static/report/report.html" }), "/static/report/report.html");
});
