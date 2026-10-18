import { API, readSession, saveSession, clearSession } from "./api.js";
import { safeReturnPath } from "./modules.js";

const form = document.querySelector("#login-form");
const button = document.querySelector("#login-submit");
const errorBox = document.querySelector("#login-error");
const notice = document.querySelector("#login-notice");
const password = document.querySelector("#password");
const destination = safeReturnPath(new URLSearchParams(location.search).get("next"));

document.querySelector("#toggle-password").addEventListener("click", event => {
  const visible = password.type === "password";
  password.type = visible ? "text" : "password";
  event.currentTarget.textContent = visible ? "隐藏" : "显示";
  event.currentTarget.setAttribute("aria-label", visible ? "隐藏密码" : "显示密码");
  event.currentTarget.setAttribute("aria-pressed", String(visible));
});

document.querySelector("#account-help").addEventListener("click", () => {
  notice.textContent = "账号开通与密码重置由系统管理员处理，请联系组内维护人员。";
  notice.hidden = false;
});

form.addEventListener("submit", async event => {
  event.preventDefault();
  if (button.disabled || !form.reportValidity()) return;
  errorBox.hidden = true;
  notice.hidden = true;
  button.disabled = true;
  button.querySelector("span").textContent = "正在验证身份…";
  try {
    const data = await API.login(document.querySelector("#username").value.trim(), password.value);
    saveSession(data);
    try {
      await API.myAccess();
    } catch (error) {
      clearSession();
      throw error;
    }
    password.value = "";
    location.assign(destination);
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
    password.value = "";
    password.focus();
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "登录工作台";
  }
});

if (readSession()) {
  notice.textContent = "检测到当前登录会话，正在确认访问权限…";
  notice.hidden = false;
  API.myAccess().then(() => location.replace(destination)).catch(error => {
    notice.textContent = error.code === 401 ? "登录已失效，请重新登录。" : error.message;
  });
}
