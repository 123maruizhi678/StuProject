/** 浏览器集成回归：本地静态服务器 + 虚构 API，无真实数据库或 Dify 调用。
 * 运行前设置 PLAYWRIGHT_MODULE 指向已安装的 playwright 模块；可用 BROWSER_EXECUTABLE 指定 Edge/Chrome。
 */
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { resolve, extname, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const frontend = fileURLToPath(new URL("../../frontend/", import.meta.url));
const playwright = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : "playwright");
const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url, "http://localhost");
    const path = url.pathname.startsWith("/static/") ? url.pathname.slice(8) :
      url.pathname === "/login" ? "common/login.html" :
      url.pathname === "/student-assistant" ? "student/student-assistant.html" : "index.html";
    const file = resolve(frontend, decodeURIComponent(path));
    if (!file.startsWith(frontend.endsWith(sep) ? frontend : frontend + sep)) throw new Error("invalid path");
    response.setHeader("Content-Type", ({ ".html": "text/html", ".js": "text/javascript", ".css": "text/css" })[extname(file)] || "application/octet-stream");
    response.end(await readFile(file));
  } catch { response.writeHead(404).end(); }
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
let browser;
try {
  browser = await playwright.chromium.launch({ headless: true, executablePath: process.env.BROWSER_EXECUTABLE || undefined });
  const context = await browser.newContext();
  const errors = [], requests = [], generationKeys = [];
  let allowCustomerPreview = false;
  const reportItem = { report_record_id: 17, report_code: "daily_report", report_name: "虚构日报",
    start_time: "2026-10-16T00:00:00Z", end_time: "2026-10-17T00:00:00Z", status: "success", generated_at: "2026-10-17T01:00:00Z" };
  let reportConfig = { report_code: "daily_report", report_name: "虚构日报", report_period: "daily", cron_expr: null, enabled: true, row_version: 1 };
  const publicAccess = { pages: { home: {}, login: {}, agent: {} }, modules: { agent_center: {} } };
  const accessFor = role => ({ ...publicAccess, user_id: 7, identity_type: role,
    permissions: role === "admin" ? ["admin.dashboard", "report.read", "report.generate", "report.config.read", "report.config.write"] : [],
    pages: { ...publicAccess.pages, ...(allowCustomerPreview ? { customer_research: {} } : {}), ...(role === "admin" ? { report: {}, admin_dashboard: {} } : role === "employee" ? { employee_dashboard: {} } : { student_dashboard: {} }) },
    modules: { ...publicAccess.modules, ...(role === "admin" ? { report_center: {}, admin_workspace: {} } : role === "employee" ? { employee_workspace: {} } : { student_workspace: {} }) },
  });
  context.on("page", page => {
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  });
  await context.route("**/api/v1/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    requests.push({ path, authorization: request.headers().authorization });
    let status = 200, code = 0, data = null;
    if (path === "/auth/public-access") data = publicAccess;
    else if (path === "/auth/login") {
      const body = request.postDataJSON();
      if (body.password !== "fictional-password") { status = 401; code = 401; }
      else data = { access_token: `fake-${body.username}`, token_type: "bearer", expires_in: 3600 };
    } else if (path === "/auth/me/access") data = accessFor((request.headers().authorization || "").split("fake-")[1] || "student");
    else if (path === "/agent/events") data = [];
    else if (path === "/agent/chat") data = { session_id: "fictional-session", reply: "虚构客服回复", need_action: false };
    else if (path === "/report/list") data = { items: [reportItem], total: 1, page: 1, page_size: 20 };
    else if (path === "/report/17") data = { ...reportItem, report_version: "v1", source_record_count: 3,
      metric_json: { daily_count: { value: 3, unit: "份" } }, report_content: "# 虚构分析\n**测试正文**\n<script>window.fakeInjected = true</script>" };
    else if (path === "/report/configs") data = [reportConfig];
    else if (path === "/report/configs/daily_report" && request.method() === "PUT") {
      const body = request.postDataJSON();
      assert.equal(body.row_version, reportConfig.row_version);
      reportConfig = { ...reportConfig, ...body, row_version: body.row_version + 1 };
      data = reportConfig;
    }
    else if (path === "/report/generate") {
      generationKeys.push(request.headers()["idempotency-key"]);
      if (generationKeys.length === 1) code = 503;
      else data = { report_record_id: 17, status: "pending" };
    } else throw new Error(`Unexpected API request: ${path}`);
    await route.fulfill({ status, contentType: "application/json", body: JSON.stringify({ code, message: code ? "虚构依赖暂不可用" : "ok", data }) });
  });
  const page = await context.newPage();
  await page.goto(origin);
  await page.locator("#connection-status.connected").waitFor();
  assert.equal(await page.locator(".module-card").count(), 6);
  assert.equal(await page.locator("#module-count").textContent(), "06");
  await page.locator('[data-module="agent"] .module-action').click();
  const agent = page.frameLocator("#module-frame");
  await agent.locator("#chat-text").fill("虚构咨询");
  await agent.locator("#send-button").click();
  await agent.getByText("虚构客服回复", { exact: true }).waitFor();
  assert.ok(requests.filter(item => item.path.startsWith("/agent/")).every(item => !item.authorization));

  async function login(role, next = "/") {
    await page.evaluate(() => sessionStorage.clear());
    await page.goto(`${origin}/login?next=${encodeURIComponent(next)}`);
    await page.locator("#username").fill(role);
    await page.locator("#password").fill("fictional-password");
    await page.locator("#login-submit").click();
    await page.waitForURL(url => url.pathname !== "/login");
  }
  await login("admin", "/#module/report");
  const report = page.frameLocator("#module-frame");
  await report.locator("#workspace").waitFor();
  await report.getByRole("button", { name: "详情", exact: true }).click();
  await report.locator("#detailCard:not([hidden])").waitFor();
  assert.equal(await report.locator("#detailCode").textContent(), "daily_report");
  assert.match(await report.locator("#detailMetrics").textContent(), /daily_count.*3/s);
  assert.equal(await report.locator("#detailContent strong").textContent(), "测试正文");
  assert.equal(await report.locator("#detailContent script").count(), 0);
  await report.locator("#detailClose").click();
  await report.locator("#configList input").first().fill("虚构更新日报");
  await report.getByRole("button", { name: "保存", exact: true }).click();
  await report.locator(".config-item .title").filter({ hasText: "虚构更新日报" }).waitFor();
  assert.equal(reportConfig.row_version, 2);
  await report.locator("#generateBtn").click();
  await report.locator("#genStart").fill("2026-10-17T09:30");
  await report.locator("#genEnd").fill("2026-10-17T08:30");
  await report.locator("#genSubmit").click();
  await report.locator("#genError").filter({ hasText: "截止时间必须晚于开始时间" }).waitFor();
  assert.equal(generationKeys.length, 0);
  await report.locator("#genStart").fill("");
  await report.locator("#genEnd").fill("");
  await report.locator("#genSubmit").click();
  await report.locator("#genError:not([hidden])").waitFor();
  await report.locator("#genSubmit:not([disabled])").click();
  await report.locator("#generateCard[hidden]").waitFor({ state: "attached" });
  assert.equal(generationKeys.length, 2);
  assert.equal(generationKeys[0], generationKeys[1]);
  await page.setViewportSize({ width: 390, height: 844 });
  const reportFrame = page.frames().find(frame => frame.url().includes("/static/report/report.html"));
  assert.equal(await reportFrame.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
  await report.locator("#themeBtn").click();
  assert.equal(await report.locator("html").getAttribute("data-theme"), "light");
  assert.equal(await reportFrame.evaluate(() => getComputedStyle(document.querySelector(".card")).backgroundColor), "rgba(255, 255, 255, 0.92)");
  await report.locator("#themeBtn").click();
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`${origin}/#module/dashboard`);
  const dashboard = page.frameLocator("#module-frame");
  await dashboard.locator("#module-notice").filter({ hasText: "业务服务正在联调" }).waitFor();
  await dashboard.locator("#app .empty").waitFor();

  await login("employee", "/#module/enterprise");
  const enterprise = page.frameLocator("#module-frame");
  await enterprise.locator("#eTabs").waitFor();
  await enterprise.getByRole("button", { name: "学生成绩", exact: true }).click();
  assert.equal(await enterprise.locator("#sSubmit").isDisabled(), true);
  await enterprise.getByRole("button", { name: "NL2SQL", exact: true }).click();
  for (const label of ["意向客户", "日报", "指令处理", "组织架构", "新人指引", "投诉"]) {
    await enterprise.getByRole("button", { name: label, exact: true }).click();
  }

  await login("student", "/static/student/leave.html");
  await page.locator(".inline-notice").filter({ hasText: "学生业务服务正在联调" }).waitFor();
  assert.equal(await page.locator(".sidebar a[href='/static/student/student-assistant.html']").count(), 1);
  await page.goto(`${origin}/static/student/student-assistant.html`);
  await page.getByRole("heading", { name: "我的服务", exact: true }).waitFor();
  for (const name of ["chat", "academics", "tickets", "reminders", "progress", "care", "notifications"]) {
    await page.goto(`${origin}/static/student/${name}.html`);
    await page.locator(".footer").waitFor();
  }
  await page.goto(`${origin}/static/student/preview.html`);
  await page.locator("#sTabs").waitFor();
  await page.getByRole("button", { name: "心理关怀", exact: true }).click();
  assert.equal(await page.locator("#mSubmit").isDisabled(), true);
  await page.goto(`${origin}/static/customer/customer.html`);
  await page.locator("#module-notice").filter({ hasText: "未获得该模块访问权限" }).waitFor();
  allowCustomerPreview = true;
  await page.reload();
  await page.locator("#jSubmit").waitFor();
  assert.equal(await page.locator("#jSubmit").isDisabled(), true);
  allowCustomerPreview = false;

  await context.clearCookies();
  await page.evaluate(() => sessionStorage.clear());
  await page.goto(`${origin}/static/report/index.html`);
  await page.waitForURL("**/static/report/report.html");
  await page.getByRole("link", { name: "前往统一登录" }).waitFor();
  await page.goto(`${origin}/static/student/login.html?next=%2Fstatic%2Fstudent%2Fleave.html`);
  await page.waitForURL("**/login?next=*");
  assert.equal(new URL(page.url()).searchParams.get("next"), "/static/student/leave.html");

  await page.goto(origin);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator("#connection-status.connected").waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
  await page.locator("#menu-toggle").click();
  assert.equal(await page.locator("#menu-toggle").getAttribute("aria-expanded"), "true");
  assert.equal(requests.some(item => /^\/(student|enterprise|customer|dashboard)\//.test(item.path)), false);
  assert.deepEqual(errors, []);
  console.log("Browser integration: public agent, report auth/retry/detail/config/time validation/themes/mobile, dashboard, enterprise/student tabs, permission denial and redirects passed.");
} finally {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
}
