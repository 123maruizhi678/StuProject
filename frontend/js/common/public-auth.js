import { API, readSession, clearSession } from "./api.js";
import { defaultEntry } from "./navigation-model.js";

// 公开页面复用统一会话；仅调整身份入口，不加载业务页面逻辑。
const links = [...document.querySelectorAll("[data-public-auth]")];
const moduleUrl = import.meta.url;
const base = new URL("../../", moduleUrl);
const loginUrl = new URL("common/login.html", base).href;
const entries = Object.fromEntries(["admin", "employee", "student", "customer"].map(role => [role, "common/workspace.html"]));
entries.admin = "admin/accounts.html";
let revision = 0;
let expiryTimer;
let identityToken;

function render(name, href, title) {
  for (const link of links) {
    link.textContent = name;
    link.href = href;
    link.title = title;
    link.setAttribute("aria-label", title);
  }
}

function renderSession(session, access) {
  const identity = session?.identity;
  const entry = access ? defaultEntry(access).slice(1) : entries[identity?.identityType];
  const name = typeof identity?.displayName === "string" ? identity.displayName.trim() : "";
  if (!entry || !name) {
    identityToken = null;
    render("登录", loginUrl, "登录");
    return;
  }
  identityToken = session.accessToken;
  render(name, new URL(entry, base).href, `${name}，进入${identity.identityType === "admin" ? "平台管理" : "通知中心"}`);
}

async function syncIdentity() {
  const current = ++revision;
  clearTimeout(expiryTimer);
  const session = readSession();
  renderSession(session);
  if (!session) return;
  try {
    const access = await API.myAccess();
    if (current !== revision || readSession()?.accessToken !== session.accessToken) return;
    renderSession(readSession(), access);
  } catch (error) {
    if (current !== revision) return;
    if (error.code === 403 && readSession()?.accessToken === session.accessToken) clearSession();
    renderSession(readSession());
  } finally {
    if (current === revision && readSession()) {
      expiryTimer = setTimeout(syncIdentity, Math.max(0, Math.min(session.expiresAt - Date.now(), 2147483647)));
    }
  }
}

for (const link of links) {
  link.addEventListener("click", event => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    if (!identityToken || identityToken !== readSession()?.accessToken) {
      ++revision;
      clearTimeout(expiryTimer);
      identityToken = null;
      render("登录", loginUrl, "登录");
    }
  });
}

window.addEventListener("auth:changed", syncIdentity);
window.addEventListener("auth:expired", syncIdentity);
window.addEventListener("pageshow", event => { if (event.persisted) syncIdentity(); });
window.addEventListener("focus", syncIdentity);
document.addEventListener("visibilitychange", () => { if (!document.hidden) syncIdentity(); });
syncIdentity();
