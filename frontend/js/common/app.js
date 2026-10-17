import { API, readSession, clearSession, publishAuthEvent } from "./api.js";
import { MODULES, canAccess, moduleEntry } from "./modules.js";

const $ = selector => document.querySelector(selector);
const identities = { admin: "平台管理员", employee: "企业员工", customer: "客户", student: "学生" };
const state = { publicAccess: { pages: {}, modules: {} }, access: { pages: {}, modules: {} }, user: null, loading: true, connected: false };
let revision = 0;
let expiryTimer;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function notify(message) {
  $("#workspace-alert").textContent = message;
  $("#workspace-alert").hidden = !message;
}

function moduleStatus(module) {
  if (state.loading) return ["同步中", "loading"];
  if (!canAccess(module, state.access)) return [state.user ? "未授权" : "需登录", "locked"];
  if (!module.delivered) return ["待接入", "pending"];
  return module.apiReady ? ["可访问", "available"] : ["待联调", "pending"];
}

function renderModules() {
  const grid = $("#module-grid");
  const navigation = $("#module-navigation");
  grid.replaceChildren();
  navigation.replaceChildren();
  for (const module of MODULES) {
    const [status, statusClass] = moduleStatus(module);
    const card = element("article", `module-card accent-${module.accent}`);
    card.dataset.module = module.id;
    const top = element("div", "module-card-top");
    top.append(element("span", "module-icon", module.symbol), element("span", `module-status ${statusClass}`, status));
    const foot = element("div", "module-card-foot");
    foot.append(element("span", "module-number", `${module.number} / WORKSPACE`));
    const action = element("button", "module-action", "↗");
    action.setAttribute("aria-label", `${module.name}：${status}`);
    action.disabled = state.loading || (statusClass === "locked" && Boolean(state.user));
    action.addEventListener("click", () => openModule(module));
    foot.append(action);
    card.append(top, element("p", "module-english", module.english), element("h3", "", module.name), element("p", "module-description", module.description), foot);
    grid.append(card);

    const nav = element("button", "nav-item module-nav-item");
    nav.append(element("span", "", module.symbol), element("span", "", module.name), element("span", `nav-dot ${statusClass}`));
    nav.setAttribute("aria-label", `${module.name}：${status}`);
    nav.disabled = action.disabled;
    nav.addEventListener("click", () => openModule(module));
    navigation.append(nav);
  }
}

function renderAccess() {
  const role = state.user ? identities[state.user.identity_type] || state.user.identity_type : "访客";
  $("#overview-identity").textContent = role;
  $("#overview-account").textContent = state.user ? `账号 ID · ${state.user.user_id}` : "公开访问模式";
  $("#overview-modules").replaceChildren(document.createTextNode(state.loading ? "—" : String(MODULES.filter(module => canAccess(module, state.access)).length).padStart(2, "0")), element("em", "", ` / ${String(MODULES.length).padStart(2, "0")}`));
  $("#nav-module-count").textContent = String(MODULES.length).padStart(2, "0");
  $("#module-count").textContent = String(MODULES.length).padStart(2, "0");
  $("#overview-pages").textContent = state.loading ? "—" : String(Object.keys(state.access.pages || {}).length).padStart(2, "0");
  $("#welcome-copy").textContent = state.user ? `${role}，欢迎回来。你的页面与模块权限已同步至工作台。` : "欢迎来到智教工作台。登录后，发现属于你的业务空间。";
  $("#login-link").hidden = Boolean(state.user);
  $("#identity-button").hidden = !state.user;
  $("#identity-label").textContent = role;
  $("#avatar").textContent = role.slice(0, 1);
  $("#account-identity").textContent = role;
  $("#account-id").textContent = state.user ? String(state.user.user_id) : "未登录";
  const session = readSession();
  $("#account-expiry").textContent = state.user && session ? new Date(session.expiresAt).toLocaleString("zh-CN", { hour12: false }) : "—";
  $("#logout-button").hidden = !state.user;
  $("#access-callout-copy").textContent = state.user ? "查看当前身份、操作权限和页面访问清单。权限变更后，可重新同步。" : "登录统一账号后，系统将为你展示可访问的页面和模块。";
  $("#access-callout-action").textContent = state.user ? "查看权限 ↗" : "前往登录 ↗";
  $("#access-callout-action").href = state.user ? "#access" : "/login";

  const tags = $("#permission-tags");
  tags.replaceChildren();
  const permissions = state.user?.permissions || [];
  $("#permission-total").textContent = `${permissions.length} 项`;
  if (!permissions.length) tags.append(element("p", "empty-message", state.user ? "当前身份未配置操作权限。" : "登录后可查看本人的操作权限。"));
  for (const permission of permissions) tags.append(element("code", "permission-tag", permission));

  const pages = $("#page-list");
  pages.replaceChildren();
  for (const [id, page] of Object.entries(state.access.pages || {})) {
    const row = element("div", "page-row");
    const title = element("div", "");
    title.append(element("strong", "", page.title || id), element("small", "", id));
    row.append(title, element("code", "", page.route || "—"), element("span", "page-visibility", page.public ? "公开页面" : "已授权"));
    pages.append(row);
  }
  if (!pages.children.length) pages.append(element("p", "empty-message", "暂无访问清单，请重新同步。"));
}

function render() {
  renderModules();
  renderAccess();
  $("#connection-status").replaceChildren(element("i"), document.createTextNode(state.loading ? "正在同步" : state.connected ? "权限已同步" : "连接待恢复"));
  $("#connection-status").classList.toggle("connected", state.connected);
  $("#refresh-access").disabled = state.loading;
  showView();
}

function loginForCurrentPage() {
  location.assign(`/login?next=${encodeURIComponent(location.pathname + location.hash)}`);
}

async function openModule(module) {
  if (!canAccess(module, state.access)) {
    if (!state.user) loginForCurrentPage();
    else notify("当前账号没有该模块的访问权限。");
    return;
  }
  if (!module.delivered) {
    notify(`${module.name}页面尚未接入。接入完成后，可从此处进入。`);
    return;
  }
  const url = moduleEntry(module);
  if (!url) {
    notify("模块入口配置无效，请联系维护人员。");
    return;
  }
  try {
    const result = await fetch(url, { method: "HEAD", cache: "no-store" });
    if (!result.ok) throw new Error();
    if (!canAccess(module, state.access)) return;
    location.hash = `module/${module.id}`;
  } catch {
    notify("模块页面暂时无法打开，请联系维护人员。");
  }
}

function showView() {
  const hash = location.hash.slice(1) || (location.pathname === "/account" ? "access" : "workspace");
  let view = hash === "access" ? "access" : "workspace";
  const activeModule = hash.startsWith("module/") ? MODULES.find(item => item.id === hash.slice(7)) : null;
  if (activeModule && !state.loading) {
    if (canAccess(activeModule, state.access) && activeModule.delivered && moduleEntry(activeModule)) {
      view = "module";
      $("#module-title").textContent = activeModule.name;
      $("#module-new-window").href = activeModule.entry;
      $("#module-frame").title = activeModule.name;
      if ($("#module-frame").getAttribute("src") !== activeModule.entry) $("#module-frame").src = activeModule.entry;
    } else {
      notify(activeModule.delivered ? "该模块需要当前账号的访问授权。" : "该模块页面尚未接入。");
    }
  }
  if (view !== "module") $("#module-frame").removeAttribute("src");
  for (const name of ["workspace", "access", "module"]) $(`#${name}-view`).hidden = name !== view;
  document.querySelectorAll("[data-view]").forEach(node => node.classList.toggle("active", node.dataset.view === view));
  $("#breadcrumb-current").textContent = view === "access" ? "我的访问权限" : view === "module" ? activeModule.name : "概览";
  $("#sidebar").classList.remove("is-open");
  $("#menu-toggle").setAttribute("aria-expanded", "false");
}

async function syncAccess() {
  const current = ++revision;
  state.loading = true;
  state.connected = false;
  notify("");
  render();
  const session = readSession();
  const [publicResult, ownResult] = await Promise.allSettled([
    API.publicAccess(), session ? API.myAccess() : Promise.resolve(null),
  ]);
  if (current !== revision) return;
  if (publicResult.status === "fulfilled") state.publicAccess = publicResult.value;
  state.user = ownResult.status === "fulfilled" && readSession() ? ownResult.value : null;
  state.access = state.user || state.publicAccess;
  state.loading = false;
  state.connected = publicResult.status === "fulfilled" && ownResult.status === "fulfilled";
  $("#sync-time").textContent = state.connected ? new Date().toLocaleTimeString("zh-CN", { hour12: false }) : "同步未完成";
  if (publicResult.status === "rejected") notify(publicResult.reason.message);
  else if (ownResult.status === "rejected") notify(ownResult.reason.message);
  render();
  clearTimeout(expiryTimer);
  const active = readSession();
  if (active) expiryTimer = setTimeout(() => {
    clearSession();
    publishAuthEvent("auth:expired");
  }, Math.min(active.expiresAt - Date.now(), 2147483647));
}

$("#identity-button").addEventListener("click", () => { location.hash = "access"; });
$("#back-workspace").addEventListener("click", () => { location.hash = "workspace"; });
$("#refresh-access").addEventListener("click", syncAccess);
$("#logout-button").addEventListener("click", () => {
  ++revision;
  clearTimeout(expiryTimer);
  clearSession();
  publishAuthEvent();
  state.user = null;
  state.access = state.publicAccess;
  state.loading = false;
  location.hash = "workspace";
  render();
  notify("已退出当前登录会话。");
});
$("#menu-toggle").addEventListener("click", event => {
  event.currentTarget.setAttribute("aria-expanded", String($("#sidebar").classList.toggle("is-open")));
});
window.addEventListener("hashchange", showView);
window.addEventListener("auth:expired", () => {
  state.user = null;
  state.access = state.publicAccess;
  render();
  notify("登录已失效，请重新登录。");
});
window.addEventListener("auth:changed", syncAccess);
window.addEventListener("pageshow", event => { if (event.persisted) syncAccess(); });
syncAccess();
