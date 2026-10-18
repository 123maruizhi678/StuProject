import { canOpenPage, pagePath, visibleModules } from "./navigation-model.js";

export function isSupportFrame() {
  try { return window.parent !== window && window.frameElement?.hasAttribute("data-support-frame"); }
  catch { return false; }
}

export function supportMessage(type) {
  if (isSupportFrame()) window.parent.postMessage({ type }, window.location.origin);
}

export function prepareSupportFrame() {
  if (!isSupportFrame()) return true;
  document.documentElement.classList.add("support-embedded");
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet";
  stylesheet.href = "/css/common/support-embed.css";
  document.head.append(stylesheet);
  if (!pagePath(location.pathname)?.startsWith("/agent/")) {
    if (pagePath(location.pathname) === "/common/login.html") supportMessage("support:login");
    location.replace("/agent/agent.html");
    return false;
  }
  document.addEventListener("click", event => {
    const anchor = event.target.closest("a[href]");
    if (!anchor) return;
    const raw = anchor.getAttribute("href");
    if (raw.startsWith("#")) return;
    const path = pagePath(anchor.href);
    if (path?.startsWith("/agent/")) { anchor.target = "_self"; return; }
    event.preventDefault();
    event.stopImmediatePropagation();
    if (path === "/common/login.html") supportMessage("support:login");
  }, true);
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") { event.preventDefault(); supportMessage("support:close"); }
  });
  return true;
}

export function renderSupportNavigation(access) {
  let tabs = document.querySelector(".support-tabs");
  if (!tabs) {
    tabs = document.createElement("nav");
    tabs.className = "support-tabs";
    tabs.setAttribute("aria-label", "客服功能");
    document.querySelector(".workspace")?.prepend(tabs);
  }
  tabs.replaceChildren();
  const current = pagePath(location.pathname);
  for (const page of visibleModules(access).find(module => module.id === "agent_center")?.pages || []) {
    const item = document.createElement("a");
    item.textContent = page.title;
    item.href = page.route;
    if (page.route === current || (page.route === "/agent/events.html" && current === "/agent/event-detail.html")) {
      item.setAttribute("aria-current", page.route === current ? "page" : "location");
    }
    tabs.append(item);
  }
  for (const anchor of document.querySelectorAll("a[href]")) {
    const raw = anchor.getAttribute("href"), path = pagePath(anchor.href);
    anchor.hidden = !raw.startsWith("#") && !(path?.startsWith("/agent/") && canOpenPage(path, access));
  }
  supportMessage("support:ready");
}
