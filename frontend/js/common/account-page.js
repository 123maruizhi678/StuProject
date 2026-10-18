// 个人中心只读展示当前登录账号的公共资料。
import { readSession, clearSession } from "./api.js";
import { workspaceModules } from "./navigation-model.js";

export function renderAccount(access) {
  const main = document.querySelector("#main-content");
  document.querySelectorAll(".preview-tag").forEach(element => { element.textContent = "只读资料"; });
  const roles = { admin: "平台管理员", employee: "企业员工", student: "学生", customer: "客户" };
  const node = (tag, text, cls) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (cls) element.className = cls;
    return element;
  };
  const card = node("section", undefined, "section-card permission-notice");
  card.append(node("div", "MY ACCOUNT", "eyebrow"), node("h1", "个人中心"));
  const details = node("dl", undefined, "detail-pairs");
  for (const [label, value] of [["姓名", access.display_name], ["账号身份", roles[access.identity_type]],
    ["可用模块", workspaceModules(access).map(module => module.title).join("、")],
    ["登录有效期", new Date(readSession().expiresAt).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false })]]) {
    const row = node("div"), content = node("dd", value || "—");
    if (label === "姓名") content.id = "account-name";
    row.append(node("dt", label), content); details.append(row);
  }
  card.append(details);
  main.replaceChildren(card);
  const logout = node("button", "退出登录", "button secondary small");
  logout.type = "button";
  logout.onclick = () => { clearSession(); location.replace("/common/login.html"); };
  document.querySelector(".top-actions")?.append(logout);
  document.documentElement.dataset.liveReady = "true";
}
