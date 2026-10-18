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
  const style = node("link"); style.rel = "stylesheet"; style.href = "/css/common/account.css"; document.head.append(style);
  main.classList.add("account-settings");
  if (access.identity_type === "student") mountContact();
  mountPassword();

  function field(form, id, caption, type = "text", autocomplete = "off") {
    const box = node("div", undefined, "form-field");
    const label = node("label", caption); label.htmlFor = id;
    const input = node("input"); input.id = id; input.name = id; input.type = type; input.required = true; input.autocomplete = autocomplete;
    input.maxLength = type === "password" ? 256 : 32; box.append(label, input); form.append(box); return input;
  }
  function section(title) {
    const section = node("section", undefined, "section-card account-setting-card");
    section.append(node("h2", title)); main.append(section); return section;
  }
  async function mountContact() {
    const sectionCard = section("手机号");
    const form = node("form", undefined, "account-setting-form");
    const username = field(form, "contact-username", "登录账号", "text", "section-contact username");
    username.value = readSession()?.accountName || ""; username.readOnly = true; username.required = false; username.maxLength = 64;
    const phone = field(form, "account-phone", "手机号", "tel", "section-contact tel");
    phone.placeholder = "请输入手机号"; phone.inputMode = "tel"; phone.disabled = true;
    const current = field(form, "contact-password", "验证原密码", "password", "section-contact current-password"); current.disabled = true;
    const submit = node("button", "保存手机号", "button"); submit.type = "submit"; submit.disabled = true;
    const message = node("p", "正在读取手机号……"); message.setAttribute("role", "status");
    const retry = node("button", "重新读取", "button secondary"); retry.type = "button"; retry.hidden = true;
    form.append(node("p", "保存手机号前需要验证原密码。", "muted"), submit, retry, message); sectionCard.append(form);
    let version = null;
    async function load() {
      submit.disabled = true; retry.hidden = true; phone.disabled = current.disabled = true;
      phone.value = ""; current.value = ""; version = null; message.textContent = "正在读取手机号……";
      try { const data = await API.myContact(); phone.value = data.phone || ""; version = data.row_version; message.textContent = data.phone ? "" : "尚未填写手机号。"; phone.disabled = current.disabled = false; submit.disabled = false; }
      catch (error) { phone.value = ""; current.value = ""; message.textContent = error.code === 404 ? "当前连接的后端尚未提供手机号接口，请更新后端后重新读取。" : error.message; retry.hidden = false; }
    }
    retry.onclick = load; await load();
    form.onsubmit = async event => {
      event.preventDefault(); if (submit.disabled || !form.reportValidity()) return;
      const number = phone.value.trim().replace(/[\s()-]/g, "");
      if (!/^\+?\d{7,15}$/.test(number)) { message.textContent = "请输入有效的手机号，不能填写登录账号。"; phone.focus(); return; }
      submit.disabled = true; message.textContent = "正在保存……";
      try { const data = await API.updateContact(phone.value.trim(), version, current.value); phone.value = data.phone || ""; version = data.row_version; message.textContent = "手机号已保存。"; }
      catch (error) {
        message.textContent = error.code === 404 ? "当前连接的后端尚未提供手机号接口，请更新后端后重新读取。" : error.message; retry.hidden = false;
        if (error.code === 404 || error.code === 409) { version = null; phone.disabled = current.disabled = true; }
      }
      finally { current.value = ""; submit.disabled = version === null; }
    };
  }
  function mountPassword() {
    const sectionCard = section("修改密码");
    const form = node("form", undefined, "account-setting-form");
    const current = field(form, "current-password", "原密码", "password", "current-password");
    const next = field(form, "new-password", "新密码", "password", "new-password"); next.minLength = 8;
    const confirm = field(form, "confirm-password", "确认新密码", "password", "new-password"); confirm.minLength = 8;
    const submit = node("button", "修改密码", "button"); submit.type = "submit";
    const message = node("p"); message.setAttribute("role", "status");
    form.append(node("p", "新密码为 8–256 位，修改成功后需要重新登录。", "muted"), submit, message); sectionCard.append(form);
    let completed = false;
    form.onsubmit = async event => {
      event.preventDefault(); if (submit.disabled || !form.reportValidity()) return;
      if (next.value !== confirm.value) { message.textContent = "两次输入的新密码不一致。"; confirm.focus(); return; }
      if (current.value === next.value) { message.textContent = "新密码不能与原密码相同。"; next.focus(); return; }
      submit.disabled = true; message.textContent = "正在修改……";
      try { await API.changePassword(current.value, next.value); completed = true; form.reset(); clearSession(); message.textContent = "密码已修改，正在前往登录页……"; setTimeout(() => location.replace("/common/login.html"), 1000); }
      catch (error) { message.textContent = error.code === 404 ? "当前连接的后端尚未提供修改密码接口，请更新后端后再试。" : error.message; }
      finally { current.value = ""; if (!completed) submit.disabled = false; }
    };
  }
  const logout = node("button", "退出登录", "button secondary small");
  logout.type = "button";
  logout.onclick = () => { clearSession(); location.replace("/common/login.html"); };
  document.querySelector(".top-actions")?.append(logout);
  document.documentElement.dataset.liveReady = "true";
}
