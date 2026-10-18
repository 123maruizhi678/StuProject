import { API, readSession, clearSession, readNavigationPreview, saveNavigationState } from "./api.js";
import { WORKSPACE_PATH, pagePath, canOpenPage, workspaceModules, navigationLocation, hasNotificationCenter, defaultEntry } from "./navigation-model.js";
import { isSupportFrame, renderSupportNavigation } from "./support-context.js";
import { setPageAccess, finishPageLoading } from "./page-loading.js";

const roleNames = { admin: "平台管理员", employee: "企业员工", student: "学生", customer: "客户" };
const renderedNavigations = new WeakMap(), boundNavigations = new WeakSet();
let restoredNavigationState = false, lastPublishedAccess = null;
let navigationAccess = null, navigationPreview = false;
let expandedModuleId = null;      // 用户手动点开的模块；null 表示全部收起
let hasManualExpansion = false;   // 是否已手动点过，用于区分"默认展开当前模块"
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

export function renderNavigation(access = navigationAccess || {}, { preview = false } = {}) {
  navigationAccess = access; navigationPreview = preview;
  if (isSupportFrame()) {
    renderSupportNavigation(access);
    renderIdentity(access);
    document.documentElement.dataset.navigationReady = 'true';
    return;
  }
  const { current, moduleId, menuPath } = navigationLocation(location.pathname, access);
  const savedState = readSession()?.navigationState;
  if (!restoredNavigationState) {
    if (savedState?.moduleId === moduleId) {
      hasManualExpansion = Boolean(savedState.manual);
      expandedModuleId = savedState.expandedModuleId;
    }
    restoredNavigationState = true;
  }
  const modules = workspaceModules(access);
  const signature = JSON.stringify({ current, moduleId, menuPath, modules, loggedIn: Boolean(readSession()),
    notifications: hasNotificationCenter(access), hasManualExpansion, expandedModuleId, metadata: access.navigation?.routes?.[current] });
  const rememberState = nav => saveNavigationState({ moduleId, manual: hasManualExpansion, expandedModuleId, scrollTop: nav.scrollTop });
  for (const nav of document.querySelectorAll(".rail-scroll")) {
    if (!boundNavigations.has(nav)) {
      nav.addEventListener('scroll', () => rememberState(nav), { passive: true });
      boundNavigations.add(nav);
    }
    if (renderedNavigations.get(nav) === signature) continue;
    const scrollTop = !renderedNavigations.has(nav) && savedState?.moduleId === moduleId ? savedState.scrollTop || 0 : nav.scrollTop;
    renderedNavigations.set(nav, signature);
    nav.replaceChildren();
    if (readSession() && hasNotificationCenter(access)) {
      const active = canOpenPage(current, access) && [WORKSPACE_PATH, "/common/notification-detail.html"].includes(current);
      const home = link("通知中心", WORKSPACE_PATH, "rail-link" + (active ? " active" : ""));
      if (active) home.setAttribute("aria-current", current === WORKSPACE_PATH ? "page" : "location");
      nav.append(home);
    }
    for (const module of modules) {
      const active = module.id === moduleId;
      const expandable = module.id !== "account_center";
      const expanded = expandable && (hasManualExpansion ? expandedModuleId === module.id : active);
      let heading;
      if (expandable) {
        heading = node("button", module.title, "rail-link" + (active ? " active" : ""));
        heading.type = "button";
        heading.setAttribute("aria-expanded", String(expanded));
        heading.addEventListener("click", () => {
          const wasExpanded = heading.getAttribute('aria-expanded') === 'true';
          hasManualExpansion = true;
          expandedModuleId = wasExpanded ? null : module.id;
          renderNavigation(navigationAccess, { preview: navigationPreview });
        });
      } else {
        heading = link(module.title, module.entry, "rail-link" + (active ? " active" : ""));
        if (active) heading.setAttribute("aria-current", "page");
      }
      nav.append(heading);
      if (expanded) for (const page of module.pages) {
        const selected = page.route === menuPath;
        const item = link(page.title, page.route, "rail-link sub" + (selected ? " active" : ""));
        if (selected) item.setAttribute("aria-current", page.route === current ? "page" : "location");
        nav.append(item);
      }
      if (active && expanded && !menuPath) {
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
    rememberState(nav);
  }
  document.querySelectorAll(".app-rail .rail-foot").forEach(element => element.remove());
  // 同时过滤模板中的快捷入口、页面导航和面包屑，不改业务表单与正文。
  for (const anchor of document.querySelectorAll("a[href]")) {
    const raw = anchor.getAttribute("href");
    if (!raw || raw.startsWith("#")) continue;
    let path = pagePath(anchor.href);
    if (!path) continue;
    if (path === WORKSPACE_PATH) {
      const genericEntry = /^(我的工作台|工作台|公共入口)$/.test(anchor.textContent.trim());
      anchor.href = genericEntry ? defaultEntry(access) : WORKSPACE_PATH;
      if (genericEntry) anchor.textContent = hasNotificationCenter(access) ? "通知中心" : "账号管理";
      path = pagePath(anchor.href);
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
  document.documentElement.dataset.navigationReady = 'true';
  if (!preview) {
    const published = JSON.stringify(access);
    if (published !== lastPublishedAccess) {
      lastPublishedAccess = published;
      window.dispatchEvent(new CustomEvent("navigation:updated", { detail: access }));
    }
  }
}

function showNotice(title, description, access) {
  const main = document.querySelector("#main-content") || document.querySelector("main");
  if (!main) return;
  const section = node("section", undefined, "section-card permission-notice");
  const entry = defaultEntry(access);
  const backLabel = entry === WORKSPACE_PATH ? "返回通知中心" : entry === "/admin/accounts.html" ? "返回账号管理" : "返回首页";
  section.append(node("h1", title), node("p", description), link(backLabel, entry, "button"));
  const retry = node("button", "重新检查权限", "button secondary");
  retry.type = "button";
  retry.onclick = () => location.reload();
  section.append(retry);
  main.replaceChildren(section);
  void finishPageLoading();
}

export async function mountNavigation() {
  if (location.pathname.replace(/^\/static\//, "/") === "/dashboard/dashboard.html") {
    location.replace(WORKSPACE_PATH);
    return null;
  }
  const preview = readNavigationPreview();
  if (preview) renderNavigation(preview, { preview: true });
  let revision = 0, lastAccess = null, allowed = false, timer;
  async function refresh() {
    const current = ++revision;
    clearTimeout(timer);
    const session = readSession();
    try {
      const access = await (session ? API.myAccess() : API.publicAccess());
      if (current !== revision || readSession()?.accessToken !== session?.accessToken) return null;
      lastAccess = access;
      setPageAccess(access, session?.accessToken);
      if (!hasNotificationCenter(access) && [WORKSPACE_PATH, "/common/notification-detail.html"].includes(pagePath(location.pathname))) {
        location.replace(defaultEntry(access));
        return null;
      }
      renderNavigation(access);
      const nextAllowed = canOpenPage(location.pathname, access);
      if (!nextAllowed) {
        if (!session) {
          location.replace("/common/login.html?next=" + encodeURIComponent(pagePath(location.pathname)));
        } else showNotice("暂无访问权限", "当前账号未获得此页面的访问权限，请从左侧菜单选择其他入口。", access);
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
        showNotice("暂时无法读取访问权限", error.message, { identity_type: session?.identity?.identityType });
      }
      return null;
    } finally {
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
