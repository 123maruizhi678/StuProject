import {request, tokenStore} from "./api.js";

const form = document.querySelector("#login-form");
const loginPanel = document.querySelector("#login-panel");
const accountPanel = document.querySelector("#account-panel");
const loginStatus = document.querySelector("#login-status");
const accountStatus = document.querySelector("#account-status");
const identityNames = {admin: "平台管理员", employee: "员工", customer: "客户", student: "学生"};
const roleNames = {employee: "普通员工", consultant: "客户顾问", manager: "部门主管",
  teacher: "班主任 / 服务老师", academic: "教务", admin: "企业配置管理员",
  analyst: "研判人员", reviewer: "复核人员"};

function loggedOut(message = "") {
  tokenStore.clear();
  accountPanel.hidden = true;
  loginPanel.hidden = false;
  loginStatus.textContent = message;
  document.querySelector("#permissions").replaceChildren();
  document.querySelector("#modules").replaceChildren();
}

function showAccess(access) {
  document.querySelector("#identity-label").textContent = identityNames[access.identity_type] || access.identity_type;
  document.querySelector("#account-label").textContent = "账号编号 " + access.user_id;
  document.querySelector("#role-label").textContent = access.role_codes.length
    ? "当前角色：" + access.role_codes.map(r => roleNames[r] || r).join("、") : "";
  const permissions = document.querySelector("#permissions");
  permissions.replaceChildren();
  for (const permission of access.permissions) {
    const chip = document.createElement("span");
    chip.className = "permission-chip";
    chip.textContent = permission;
    permissions.append(chip);
  }
  if (!access.permissions.length) permissions.textContent = "当前未配置业务权限。";
  const modules = document.querySelector("#modules");
  modules.replaceChildren();
  for (const module of Object.values(access.modules)) {
    const item = document.createElement("li");
    item.textContent = module.title;
    modules.append(item);
  }
  loginPanel.hidden = true;
  accountPanel.hidden = false;
  accountStatus.textContent = "";
}

async function refreshAccess() {
  const access = await request("/auth/me/access", {authenticated: true});
  showAccess(access);
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  const button = document.querySelector("#login-button");
  button.disabled = true;
  loginStatus.textContent = "正在登录…";
  const password = document.querySelector("#password");
  try {
    const result = await request("/auth/login", {
      method: "POST", body: {username: form.username.value, password: password.value},
    });
    tokenStore.set(result.access_token);
    await refreshAccess();
    history.replaceState(null, "", "/account");
  } catch (error) {
    loggedOut(error.message);
  } finally {
    password.value = "";
    button.disabled = false;
  }
});

document.querySelector("#toggle-password").addEventListener("click", event => {
  const password = document.querySelector("#password");
  const show = password.type === "password";
  password.type = show ? "text" : "password";
  event.currentTarget.textContent = show ? "隐藏" : "显示";
  event.currentTarget.setAttribute("aria-pressed", String(show));
});
document.querySelector("#logout-button").addEventListener("click", () => {
  loggedOut();
  history.replaceState(null, "", "/login");
});
document.querySelector("#refresh-button").addEventListener("click", async event => {
  event.currentTarget.disabled = true;
  try {
    await refreshAccess();
    accountStatus.classList.add("success");
    accountStatus.textContent = "权限已更新。";
  } catch (error) {
    accountStatus.classList.remove("success");
    if ([401, 403].includes(error.code)) loggedOut(error.message);
    else accountStatus.textContent = error.message;
  } finally { event.currentTarget.disabled = false; }
});
if (tokenStore.get()) {
  refreshAccess().catch(error => loggedOut(error.message));
}
