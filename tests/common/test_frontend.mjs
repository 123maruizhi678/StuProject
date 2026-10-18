/** 原生 Node 测试公共前端逻辑；不依赖 npm 包、浏览器或外部服务。 */
import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";
import { readFile, readdir, access } from "node:fs/promises";
import { resolve, dirname, relative } from "node:path";
import { fileURLToPath } from "node:url";

const load = async path => import(`data:text/javascript;base64,${Buffer.from(await readFile(new URL(path, import.meta.url), "utf8")).toString("base64")}`);
const api = await load("../../frontend/js/common/api.js");
const modules = await load("../../frontend/js/common/modules.js");

async function loadTree(path) {
  const file = new URL(path, import.meta.url);
  let source = await readFile(file, "utf8");
  for (const match of [...source.matchAll(/from\s+["'](\.[^"']+)["']/g)]) {
    const dependency = await moduleUrl(new URL(match[1], file));
    source = source.replace(match[0], `from "${dependency}"`);
  }
  return import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
}

async function moduleUrl(file) {
  let source = await readFile(file, "utf8");
  for (const match of [...source.matchAll(/from\s+["'](\.[^"']+)["']/g)]) {
    source = source.replace(match[0], `from "${await moduleUrl(new URL(match[1], file))}"`);
  }
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

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
  assert.equal(modules.safeReturnPath("/static/student/leave.html?tab=pending"), "/static/student/leave.html?tab=pending");
  assert.equal(modules.safeReturnPath("/static/student/login.html"), "/");
  assert.equal(modules.safeReturnPath("/static/missing.html"), "/");
});

test("模块登记、学生导航、所有页面和脚本的本地依赖均存在", async () => {
  const frontend = fileURLToPath(new URL("../../frontend/", import.meta.url));
  async function walk(directory) {
    const entries = await readdir(directory, { withFileTypes: true });
    const files = await Promise.all(entries.map(item => item.isDirectory() ? walk(resolve(directory, item.name)) : resolve(directory, item.name)));
    return files.flat();
  }
  assert.equal(new Set(modules.MODULES.map(item => item.id)).size, modules.MODULES.length);
  for (const item of modules.MODULES) {
    assert.equal(item.delivered, true);
    await access(resolve(frontend, item.entry.slice("/static/".length)));
  }
  for (const item of modules.STUDENT_PAGES) await access(resolve(frontend, item[3].slice("/static/".length)));
  for (const file of await walk(frontend)) {
    if (!/\.(html|js)$/.test(file)) continue;
    const source = await readFile(file, "utf8");
    assert.doesNotMatch(source, /^(?:<{7}|={7}|>{7})(?: |$)/m, relative(frontend, file));
    const references = file.endsWith(".html")
      ? [...source.matchAll(/(?:src|href)=["']([^"'#?]+)[^"']*["']/g)].map(match => match[1])
      : [...source.matchAll(/(?:from\s*|import\s*\()["'](\.[^"']+)["']/g)].map(match => match[1]);
    for (const reference of references) {
      if (/^(?:https?:|data:|blob:|mailto:|tel:)/.test(reference)) continue;
      if (reference.startsWith("/") && !reference.startsWith("/static/")) continue;
      const target = reference.startsWith("/static/") ? resolve(frontend, reference.slice(8)) : resolve(dirname(file), reference);
      await assert.doesNotReject(access(target), `${relative(frontend, file)} -> ${reference}`);
    }
  }
});

test("统一请求保留上传表单、幂等请求头和当前登录身份", async () => {
  api.saveSession({ access_token: "fake-token", token_type: "bearer", expires_in: 60 });
  const body = new FormData();
  body.append("file", new Blob(["fictional upload"]), "fake.txt");
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/v1/customer/judge");
    assert.equal(options.body, body);
    assert.equal(options.headers["Content-Type"], undefined);
    assert.equal(options.headers["Idempotency-Key"], "fake-upload-key");
    assert.equal(options.headers.Authorization, "Bearer fake-token");
    return reply(200, { code: 0, data: {} });
  };
  await api.request("/customer/judge", { method: "POST", body, headers: { "Idempotency-Key": "fake-upload-key" } });
});

test("401 同步到同源工作台及 iframe", async () => {
  const parent = window;
  parent.frames = [];
  const child = new EventTarget();
  child.parent = parent;
  child.location = parent.location;
  child.frames = [];
  parent.frames.push(child);
  let rootEvents = 0, childEvents = 0;
  parent.addEventListener("auth:expired", () => rootEvents++);
  child.addEventListener("auth:expired", () => childEvents++);
  globalThis.window = child;
  globalThis.fetch = async () => reply(200, { code: 401, message: "invalid", data: null });
  await assert.rejects(api.API.myAccess, error => error.code === 401);
  assert.deepEqual([rootEvents, childEvents], [1, 1]);
});

test("已接入模块调用真实接口，未实现看板保持阻止", async () => {
  const adapter = await loadTree("../../frontend/js/common/module-api.js");
  globalThis.fetch = async () => { assert.fail("未就绪模块不应发起网络请求"); };
  await assert.rejects(adapter.API.get("/dashboard/overview"), error => error.code === 503);
  globalThis.fetch = async url => {
    assert.equal(url, "/api/v1/enterprise/customer");
    return reply(200, {code: 0, data: {items: []}});
  };
  assert.deepEqual(await adapter.API.get("/enterprise/customer"), {items: []});
});

test("报告失败重试复用幂等键，受理成功后下次操作换键", async () => {
  const report = await loadTree("../../frontend/js/report/report-api.js");
  const keys = [];
  const generator = report.createReportGenerator(async (method, path, body, headers) => {
    assert.equal(method, "POST");
    assert.equal(path, "/report/generate");
    keys.push(headers["Idempotency-Key"]);
    if (keys.length === 1) throw new Error("fictional network failure");
    return { report_record_id: 7, status: "pending" };
  });
  const body = { report_code: "daily_report" };
  await assert.rejects(generator.generate(body));
  await generator.generate(body);
  await generator.generate(body);
  assert.equal(keys[0], keys[1]);
  assert.notEqual(keys[1], keys[2]);
});

test("北京时间转换不受运行机器时区影响", async () => {
  const report = await loadTree("../../frontend/js/report/report-api.js");
  assert.equal(report.toBeijingIso("2026-10-17T09:30"), "2026-10-17T09:30:00+08:00");
  assert.equal(report.toBeijingIso("2026-10-17T09:30:15"), "2026-10-17T09:30:15+08:00");
  assert.throws(() => report.toBeijingIso("invalid"));
});

test("普通 HTTP 缺少 randomUUID 时仍生成安全且互不重复的 UUID v4", () => {
  const provider = { getRandomValues: bytes => globalThis.crypto.getRandomValues(bytes) };
  const ids = Array.from({ length: 100 }, () => api.createRequestId(provider));
  assert.equal(new Set(ids).size, ids.length);
  for (const id of ids) assert.match(id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  const fixed = api.createRequestId({ getRandomValues: bytes => bytes.fill(255) });
  assert.equal(fixed, "ffffffff-ffff-4fff-bfff-ffffffffffff");
});
