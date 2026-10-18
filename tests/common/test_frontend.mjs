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

test("登录保存姓名和身份摘要，重新读取会话无需再次请求", async () => {
  globalThis.fetch = async () => reply(200, { code: 0, data: {
    access_token: "identity-token", token_type: "bearer", expires_in: 60,
    user_id: 102, identity_type: "employee", display_name: "测试教师",
  } });
  api.saveSession(await api.API.login("fake-employee", "fictional-password"));
  assert.deepEqual(api.readSession().identity, { displayName: "测试教师", identityType: "employee", userId: 102 });
  assert.equal(api.readSession().accountName, "fake-employee");
});

test("旧接口通过已验证的登录账号补充姓名，并在权限读取后保存身份", async () => {
  globalThis.fetch = async url => reply(200, { code: 0, data: url.endsWith('/login')
    ? { access_token: "legacy-token", token_type: "bearer", expires_in: 60 }
    : { user_id: 103, identity_type: "student", permissions: ["fictional-permission"] } });
  api.saveSession(await api.API.login("fake-student", "fictional-password"));
  const access = await api.API.myAccess();
  assert.equal(access.display_name, "fake-student");
  assert.deepEqual(api.readSession().identity, { displayName: "fake-student", identityType: "student", userId: 103 });
  assert.equal(api.readSession().permissions, undefined);
});

test("身份接口临时不可用时保留已有会话和姓名", async () => {
  api.saveSession({ access_token: "kept-token", token_type: "bearer", expires_in: 60,
    identity_type: "employee", user_id: 102, display_name: "已有姓名" });
  globalThis.fetch = async () => { throw new TypeError("fictional-network-error"); };
  await assert.rejects(api.API.myAccess());
  assert.equal(api.readSession().identity.displayName, "已有姓名");
});

test("旧请求返回401不能清除随后登录的新账号", async () => {
  api.saveSession({ access_token: "old-token", token_type: "bearer", expires_in: 60 });
  let complete;
  globalThis.fetch = () => new Promise(resolve => { complete = resolve; });
  const pending = api.API.myAccess();
  api.saveSession({ access_token: "new-token", token_type: "bearer", expires_in: 60,
    identity_type: "student", display_name: "新账号" });
  complete(reply(401, { detail: "old request expired" }));
  await assert.rejects(pending, error => error.code === 401);
  assert.equal(api.readSession().accessToken, "new-token");
  assert.equal(api.readSession().identity.displayName, "新账号");
});

test("旧请求返回姓名不能覆盖随后登录的新账号", async () => {
  api.saveSession({ access_token: "old-token", token_type: "bearer", expires_in: 60 });
  let complete;
  globalThis.fetch = () => new Promise(resolve => { complete = resolve; });
  const pending = api.API.myAccess();
  api.saveSession({ access_token: "new-token", token_type: "bearer", expires_in: 60,
    identity_type: "student", display_name: "新账号" });
  complete(reply(200, { code: 0, data: { identity_type: "employee", display_name: "旧账号" } }));
  await pending;
  assert.equal(api.readSession().identity.displayName, "新账号");
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

test("公共工作台只采用服务端页面清单，返回地址必须已获授权", async () => {
  const navigation = await load("../../frontend/js/common/navigation-model.js");
  const access = { navigation: {
    routes: { "/common/workspace.html": {}, "/student/student-assistant.html": {} },
    modules: [
      { id: "student", title: "学生", entry: "/static/student/student-assistant.html", pages: [] },
      { id: "admin", title: "管理", entry: "/admin/accounts.html", pages: [] },
      { id: "outside", title: "外部", entry: "https://outside.test/student/student-assistant.html", pages: [] },
    ],
  } };
  assert.deepEqual(navigation.visibleModules(access).map(item => item.id), ["student"]);
  assert.equal(navigation.canOpenPage("/static/student/student-assistant.html", access), true);
  assert.equal(navigation.canOpenPage("/admin/accounts.html", access), false);
  assert.equal(navigation.canOpenPage("/student/student-assistant.html", {}), false);
  assert.equal(navigation.loginDestination("https://outside.test/", access), "/common/workspace.html");
  assert.equal(navigation.loginDestination("/admin/accounts.html", access), "/common/workspace.html");
  assert.equal(navigation.loginDestination("/static/student/student-assistant.html?tab=all", access), "/student/student-assistant.html?tab=all");
});

test("详情页定位所属模块和列表目录，权限撤销后不能沿用目录", async () => {
  const navigation = await load("../../frontend/js/common/navigation-model.js");
  const entry = "/student/student-assistant.html", list = "/student/leave.html", detail = "/student/leave-detail.html";
  const access = { navigation: { routes: {
    [entry]: { module: "student" }, [list]: { module: "student" }, [detail]: { module: "student", menu: false },
  }, modules: [{ id: "student", title: "学生", entry, pages: [{ route: entry }, { route: list }] }] } };
  assert.deepEqual(navigation.navigationLocation("/static" + detail + "?id=77", access), {
    current: detail, moduleId: "student", menuPath: list,
  });
  assert.equal(navigation.navigationLocation(list, access).menuPath, list);
  delete access.navigation.routes[list];
  assert.deepEqual(navigation.navigationLocation(detail, access), { current: detail, moduleId: "student", menuPath: null });
  delete access.navigation.routes[detail];
  assert.deepEqual(navigation.navigationLocation(detail, access), { current: detail, moduleId: null, menuPath: null });
});

test("平台管理员移除通知中心并进入已授权账号管理，其他身份保留通知中心", async () => {
  const navigation = await load("../../frontend/js/common/navigation-model.js");
  const access = { identity_type: "admin", navigation: { routes: {
    "/common/workspace.html": {}, "/common/notification-detail.html": {},
    "/admin/accounts.html": {}, "/common/account.html": {},
  } } };
  assert.equal(navigation.canOpenPage("/common/workspace.html", access), false);
  assert.equal(navigation.canOpenPage("/common/notification-detail.html", access), false);
  assert.equal(navigation.canOpenPage("/common/notifications.html", access), false);
  assert.equal(navigation.loginDestination(null, access), "/admin/accounts.html");
  assert.equal(navigation.loginDestination("/dashboard/dashboard.html", access), "/admin/accounts.html");
  assert.equal(navigation.loginDestination("/common/workspace.html", access), "/admin/accounts.html");
  assert.equal(navigation.loginDestination("/common/account.html", access), "/common/account.html");
  delete access.navigation.routes["/admin/accounts.html"];
  assert.equal(navigation.defaultEntry(access), "/common/account.html");
  for (const identity_type of ["employee", "student", "customer"]) {
    const other = { ...access, identity_type, roles: ["admin"] };
    assert.equal(navigation.canOpenPage("/common/workspace.html", other), true);
    assert.equal(navigation.loginDestination(null, other), "/common/workspace.html");
  }
});

test("后台客服菜单仅对管理员保留，公开客服页面授权不变", async () => {
  const navigation = await load("../../frontend/js/common/navigation-model.js");
  const access = { identity_type: "student", roles: [], navigation: {
    routes: { "/agent/agent.html": { module: "agent_center" } },
    modules: [{ id: "agent_center", title: "客服咨询", entry: "/agent/agent.html", pages: [] }],
  } };
  assert.equal(navigation.workspaceModules(access).length, 0);
  assert.equal(navigation.canOpenPage("/agent/agent.html", access), true);
  access.identity_type = "admin";
  assert.equal(navigation.workspaceModules(access).length, 1);
  access.identity_type = "employee"; access.roles = ["admin"];
  assert.equal(navigation.workspaceModules(access).length, 1);
});

test("修改姓名只提交本人资料并更新当前会话身份", async () => {
  api.saveSession({ access_token: "name-token", token_type: "bearer", expires_in: 60, identity_type: "student", display_name: "旧姓名" });
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/v1/auth/me/profile");
    assert.equal(options.method, "PATCH");
    assert.deepEqual(JSON.parse(options.body), { full_name: "新姓名", expected_full_name: "旧姓名" });
    return reply(200, { code: 0, data: { user_id: 103, identity_type: "student", display_name: "新姓名" } });
  };
  await api.API.updateProfile("新姓名", "旧姓名");
  assert.equal(api.readSession().identity.displayName, "新姓名");
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

test("主管研判和报告仅渲染已授权查询，管理员保留写入表单", async () => {
  const pages = await load("../../frontend/js/workspace/pages.js");
  const operations = [
    { method: "GET", path: "/api/v1/customer/source" },
    { method: "GET", path: "/api/v1/customer/source/{id}/file" },
    { method: "POST", path: "/api/v1/customer/source" },
    { method: "POST", path: "/api/v1/customer/source/{id}/parse" },
    { method: "GET", path: "/api/v1/customer/result" },
    { method: "POST", path: "/api/v1/customer/judge" },
    { method: "GET", path: "/api/v1/customer/rule" },
    { method: "PUT", path: "/api/v1/customer/rule" },
    { method: "GET", path: "/api/v1/report/list" },
    { method: "POST", path: "/api/v1/report/generate" },
    { method: "GET", path: "/api/v1/report/configs" },
  ];
  const permissions = ["customer.source.read", "customer.result.read", "customer.rule.read", "report.read"];
  assert.deepEqual(pages.operationsForAccess(operations, { permissions }).map(item => item.path), [
    "/api/v1/customer/source", "/api/v1/customer/result", "/api/v1/customer/rule", "/api/v1/report/list",
  ]);
  assert.equal(pages.operationsForAccess(operations, { identity_type: "admin", permissions: [] }).length, 0);
  assert.equal(pages.operationsForAccess(operations, { permissions: [...permissions, "customer.source.file", "customer.source.create",
    "customer.source.parse", "customer.judge.create", "customer.rule.manage", "report.generate", "report.config.read"] }).length, operations.length);
});
