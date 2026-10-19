// 个人中心只维护当前登录账号的公共资料。
import { API, readSession } from "./api.js";
import { workspaceModules } from "./navigation-model.js";
import { renderIdentity } from "./navigation.js";

export function renderAccount(access) {
  const main = document.querySelector("#main-content");
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
  for (const [label, value] of [["账号身份", roles[access.identity_type]],
    ["可用模块", workspaceModules(access).map(module => module.title).join("、")],
    ["登录有效期", new Date(readSession().expiresAt).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false })]]) {
    const row = node("div"); row.append(node("dt", label), node("dd", value || "—")); details.append(row);
  }
  const form = node("form", undefined, "account-profile-form");
  const label = node("label", "姓名"); label.htmlFor = "account-name";
  const input = node("input"); input.id = "account-name"; input.name = "full_name";
  input.value = access.display_name || ""; input.required = true; input.maxLength = 100; input.autocomplete = "name";
  const hint = node("p", "修改的是本人档案中的正式姓名，保存后同步显示在首页和个人身份信息中。", "muted");
  const save = node("button", "保存", "button"); save.type = "submit";
  const message = node("p"); message.setAttribute("role", "status");
  let savedName = input.value;
  form.append(label, input, hint, save, message);
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (save.disabled || !form.reportValidity()) return;
    const name = input.value.trim();
    if (!name) { message.textContent = "请输入姓名。"; input.focus(); return; }
    save.disabled = true; message.textContent = "正在保存……";
    try {
      const data = await API.updateProfile(name, savedName);
      savedName = data.display_name; input.value = savedName;
      access.display_name = savedName; renderIdentity(access);
      message.textContent = "姓名已保存。";
    } catch (error) { message.textContent = error.message; }
    finally { save.disabled = false; }
  });
  card.append(form, details);
  main.replaceChildren(card);
  document.documentElement.dataset.liveReady = "true";
}
