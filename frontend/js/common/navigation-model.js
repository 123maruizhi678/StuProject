export const WORKSPACE_PATH = "/common/workspace.html";

export function pagePath(value) {
  try {
    if (typeof value !== "string" || value.includes("\\")) return null;
    const url = new URL(value, window.location.origin);
    if (url.origin !== window.location.origin) return null;
    const path = url.pathname.replace(/^\/static\//, "/");
    return ({ "/account": "/common/account.html", "/login": "/common/login.html",
      "/login.html": "/common/login.html", "/enterprise": "/enterprise/enterprise.html",
      "/student-assistant": "/student/student-assistant.html", "/admin": "/admin/accounts.html",
      "/admin/accounts": "/admin/accounts.html", "/dashboard/dashboard.html": WORKSPACE_PATH,
      "/common/notifications.html": WORKSPACE_PATH,
    })[path] || path;
  } catch { return null; }
}

export function canOpenPage(value, access) {
  const path = pagePath(value);
  return Boolean(path && Object.hasOwn(access?.navigation?.routes || {}, path));
}

export function visibleModules(access) {
  const modules = access?.navigation?.modules;
  if (!Array.isArray(modules)) return [];
  return modules.filter(module => typeof module.title === "string" && canOpenPage(module.entry, access))
    .map(module => ({ ...module, entry: pagePath(module.entry),
      pages: (Array.isArray(module.pages) ? module.pages : [])
        .filter(page => canOpenPage(page.route, access)).map(page => ({ ...page, route: pagePath(page.route) })),
    }));
}

export function workspaceModules(access) {
  const admin = access?.identity_type === "admin" || access?.roles?.includes("admin");
  return visibleModules(access).filter(module => module.id !== "agent_center" || admin);
}

export function loginDestination(value, access) {
  if (!value || !canOpenPage(value, access)) return WORKSPACE_PATH;
  const url = new URL(value, window.location.origin);
  return pagePath(value) + url.search + url.hash;
}

// 详情和办理确认页沿用所属列表目录，仅参与导航定位，不授予页面权限。
const parentPages = {
  "/agent/event-detail.html": "/agent/events.html",
  "/customer/source-detail.html": "/customer/sources.html",
  "/customer/result-detail.html": "/customer/results.html",
  "/customer/rule-detail.html": "/customer/rules.html",
  "/enterprise/command-preview.html": "/enterprise/assistant.html",
  "/enterprise/customer-detail.html": "/enterprise/customers.html",
  "/enterprise/student-detail.html": "/enterprise/students.html",
  "/enterprise/daily-report-new.html": "/enterprise/daily-reports.html",
  "/enterprise/daily-report-detail.html": "/enterprise/daily-reports.html",
  "/enterprise/leave-detail.html": "/enterprise/leave-review.html",
  "/enterprise/ticket-detail.html": "/enterprise/tickets.html",
  "/enterprise/knowledge-detail.html": "/enterprise/knowledge.html",
  "/enterprise/warning-detail.html": "/enterprise/warnings.html",
  "/student/leave-detail.html": "/student/leave.html",
  "/student/ticket-detail.html": "/student/tickets.html",
  "/student/action-preview.html": "/student/chat.html",
  "/report/detail.html": "/report/list.html",
};

export function navigationLocation(value, access) {
  const current = pagePath(value);
  if (!canOpenPage(current, access)) return { current, moduleId: null, menuPath: null };
  const metadata = access.navigation.routes[current];
  const module = visibleModules(access).find(item => item.id === metadata.module ||
    item.pages.some(page => page.route === current));
  const menuPath = module?.pages.find(page => page.route === current || page.route === parentPages[current])?.route || null;
  return { current, moduleId: module?.id || null, menuPath };
}
