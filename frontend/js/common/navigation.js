import { API, readSession, clearSession } from "./api.js";
import { WORKSPACE_PATH, pagePath, canOpenPage, workspaceModules, navigationLocation } from "./navigation-model.js";
import { isSupportFrame, renderSupportNavigation } from "./support-context.js";

const roleNames = { admin: "平台管理员", employee: "企业员工", student: "学生", customer: "客户" };
const node = (tag, text, className) => {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
};
function link(text, href, className) {
  const element = node("a", text, className);
  element.href = href;
  return element;
}

export function renderIdentity(access) {
  const name = access?.display_name || readSession()?.identity?.displayName || "访客";
  document.querySelectorAll(".user-name").forEach(element => { element.textContent = name; });
  document.querySelectorAll(".user-chip .avatar").forEach(element => { element.textContent = name.slice(0, 1); });
  document.querySelectorAll("[data-current-role]").forEach(element => {
    element.textContent = roleNames[access?.identity_type] || "公开访问";
  });
}

export function renderNavigation(access) {
  if (isSupportFrame()) {
    renderSupportNavigation(access);
    renderIdentity(access);
    return;
  }
  const { current, moduleId, menuPath } = navigationLocation(location.pathname, access);
  for (const nav of document.querySelectorAll(".rail-scroll")) {
    const scrollTop = nav.scrollTop;
    nav.replaceChildren();
    if (readSession()) {
      const active = canOpenPage(current, access) && [WORKSPACE_PATH, "/common/notification-detail.html"].includes(current);
      const home = link("通知中心", WORKSPACE_PATH, "rail-link" + (active ? " active" : ""));
      if (active) home.setAttribute("aria-current", current === WORKSPACE_PATH ? "page" : "location");
      nav.append(home);
    }
    for (const module of workspaceModules(access)) {
      const active = module.id === moduleId;
      const heading = link(module.title, module.entry, "rail-link" + (active ? " active" : ""));
      heading.setAttribute("aria-expanded", String(active));
      if (module.id === "account_center") {
        heading.removeAttribute("aria-expanded");
        if (active) heading.setAttribute("aria-current", "page");
      }
      nav.append(heading);
      if (active && module.id !== "account_center") for (const page of module.pages) {
        const selected = page.route === menuPath;
        const item = link(page.title, page.route, "rail-link sub" + (selected ? " active" : ""));
        if (selected) item.setAttribute("aria-current", page.route === current ? "page" : "location");
        nav.append(item);
      }
      if (active && !menuPath && module.id !== "account_center") {
        const item = link(access.navigation.routes[current].title, current, "rail-link sub active");
        item.setAttribute("aria-current", "page");
        nav.append(item);
      }
    }
    nav.scrollTop = scrollTop;
    const selected = nav.querySelector("[aria-current]");
    if (selected) {
      const bounds = nav.getBoundingClientRect(), item = selected.getBoundingClientRect();
      if (item.top < bounds.top) nav.scrollTop -= bounds.top - item.top;
      else if (item.bottom > bounds.bottom) nav.scrollTop += item.bottom - bounds.bottom;
    }
  }
  document.querySelectorAll(".app-rail .rail-foot").forEach(element => element.remove());
  // 同时过滤模板中的快捷入口、页面导航和面包屑，不改业务表单与正文。
  for (const anchor of document.querySelectorAll("a[href]")) {
    const raw = anchor.getAttribute("href");
    if (!raw || raw.startsWith("#")) continue;
    const path = pagePath(anchor.href);
    if (!path) continue;
    if (path === WORKSPACE_PATH) {
      anchor.href = WORKSPACE_PATH;
      if (/^(我的工作台|工作台|公共入口)$/.test(anchor.textContent.trim())) anchor.textContent = "通知中心";
    }
    if (/^\/(agent|customer|enterprise|student|report|admin)\/.*\.html$/.test(path) ||
        ["/common/account.html", "/common/notifications.html", "/common/notification-detail.html", "/common/announcement-manage.html", WORKSPACE_PATH].includes(path)) {
      anchor.hidden = !canOpenPage(path, access) || (path.startsWith("/agent/") && !workspaceModules(access).some(module => module.id === "agent_center"));
      anchor.dataset.permissionHidden = String(anchor.hidden);
    }
  }
  document.querySelectorAll(".sitemap-grid .section-card").forEach(section => {
    section.hidden = !section.querySelector("a:not([hidden])");
  });
  renderIdentity(access);
  window.dispatchEvent(new CustomEvent("navigation:updated", { detail: access }));
}

function showNotice(title, description) {
  const main = document.querySelector("#main-content") || document.querySelector("main");
  if (!main) return;
  const section = node("section", undefined, "section-card permission-notice");
  section.append(node("h1", title), node("p", description), link("返回通知中心", WORKSPACE_PATH, "button"));
  const retry = node("button", "重新检查权限", "button secondary");
  retry.type = "button";
  retry.onclick = () => location.reload();
  section.append(retry);
  main.replaceChildren(section);
}

export async function mountNavigation() {
  if (location.pathname.replace(/^\/static\//, "/") === "/dashboard/dashboard.html") {
    location.replace(WORKSPACE_PATH);
    return null;
  }
  let revision = 0, lastAccess = null, allowed = false, timer;
  async function refresh() {
    const current = ++revision;
    clearTimeout(timer);
    const session = readSession();
    try {
      const access = await (session ? API.myAccess() : API.publicAccess());
      if (current !== revision || readSession()?.accessToken !== session?.accessToken) return null;
      lastAccess = access;
      renderNavigation(access);
      const nextAllowed = canOpenPage(location.pathname, access);
      if (!nextAllowed) {
        if (!session) {
          location.replace("/common/login.html?next=" + encodeURIComponent(pagePath(location.pathname)));
        } else showNotice("暂无访问权限", "当前账号未获得此页面的访问权限，请从左侧菜单选择其他入口。");
      } else if (document.documentElement.dataset.permissionDenied === "true") {
        location.reload();
      }
      allowed = nextAllowed;
      document.documentElement.dataset.permissionDenied = String(!allowed);
      return allowed ? access : null;
    } catch (error) {
      if (current !== revision) return null;
      if (error.code === 403) { clearSession(); location.replace("/common/login.html"); return null; }
      if (!readSession() && session) { location.replace("/common/login.html"); return null; }
      if (!lastAccess) {
        renderNavigation({});
        showNotice("暂时无法读取访问权限", error.message);
      }
      return null;
    } finally {
      document.documentElement.classList.remove("permission-loading");
      if (current === revision && readSession()) timer = setTimeout(refresh,
        Math.max(0, Math.min(60000, readSession().expiresAt - Date.now())));
    }
  }
  const access = await refresh();
  window.addEventListener("focus", refresh);
  window.addEventListener("pageshow", event => { if (event.persisted) refresh(); });
  window.addEventListener("auth:changed", () => { lastAccess = null; refresh(); });
  window.addEventListener("auth:expired", () => location.replace("/common/login.html"));
  return access;
}
