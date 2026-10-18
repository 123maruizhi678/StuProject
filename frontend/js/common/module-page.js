import { API, readSession } from "./api.js";
import { MODULES, canAccess } from "./modules.js";

const module = MODULES.find(item => item.id === document.documentElement.dataset.module);
const root = document.querySelector("#app");
const notice = document.querySelector("#module-notice");
const loaders = {
  dashboard: () => import("../dashboard/dashboard.js"),
  customer: () => import("../customer/customer.js"),
  enterprise: () => import("../enterprise/enterprise.js"),
  student: () => import("../student/student.js"),
};
let revision = 0;

async function render() {
  const current = ++revision;
  observer?.disconnect();
  root.replaceChildren();
  try {
    const access = await (readSession() ? API.myAccess() : API.publicAccess());
    if (current !== revision) return;
    if (!module || !canAccess(module, access)) {
      notice.textContent = "当前身份未获得该模块访问权限，请返回工作台登录或查看权限。";
      return;
    }
    notice.textContent = module.apiReady ? "" : "页面已接入，业务服务正在联调，暂不能查询或提交数据。";
    const page = await loaders[module.id]();
    if (current !== revision) return;
    await page.render(root);
    if (!module.apiReady) {
      // 保留标签切换以便查看各子功能；所有业务表单只展示布局。
      const disableForms = () => {
        root.querySelectorAll("input, textarea, select, button:not(.tab)").forEach(node => { node.disabled = true; });
      };
      disableForms();
      observer?.disconnect();
      observer = new MutationObserver(disableForms);
      observer.observe(root, { childList: true, subtree: true });
    }
  } catch (error) {
    if (current === revision) notice.textContent = error.message;
  }
}

let observer;
const theme = localStorage.getItem("stuproject.theme") === "light" ? "light" : "dark";
document.documentElement.dataset.theme = theme;
document.querySelector("#themeBtn").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("stuproject.theme", next);
});
window.addEventListener("auth:expired", () => {
  ++revision;
  observer?.disconnect();
  root.replaceChildren();
  notice.textContent = "登录已失效，请返回工作台重新登录。";
});
window.addEventListener("auth:changed", render);
window.addEventListener("pageshow", event => { if (event.persisted) render(); });
await render();
await import("./effects.js");
