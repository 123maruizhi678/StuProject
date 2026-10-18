import { API, readSession, saveSession } from "./api.js";
import { loginDestination } from "./navigation-model.js";

const form = document.querySelector("[data-login-preview]");
const name = form.querySelector("input[type=text]");
const password = form.querySelector("input[type=password]");
const button = form.querySelector("button[type=submit]");
const message = document.createElement("p");
message.setAttribute("role", "status");
form.append(message);
name.name = "username";
name.autocomplete = "username";
password.name = "password";
password.autocomplete = "current-password";
button.textContent = "登录";
document.querySelector(".login-disclaimer").textContent = "登录后，根据当前账号权限显示可用模块。";
const publicLink = document.querySelector(".preview-link");
publicLink.textContent = "返回公开首页";
publicLink.href = "/index.html";
const next = new URLSearchParams(location.search).get("next");

form.addEventListener("submit", async event => {
  event.preventDefault();
  if (button.disabled || !form.reportValidity()) return;
  button.disabled = true;
  message.textContent = "正在验证账号与访问权限……";
  try {
    saveSession(await API.login(name.value.trim(), password.value));
    password.value = "";
    const access = await API.myAccess();
    location.assign(loginDestination(next, access));
  } catch (error) {
    message.textContent = error.message;
  } finally { button.disabled = false; }
});

// 已登录时无需再次输入密码；只进入服务端仍授权的页面。
if (readSession()) {
  message.textContent = "正在确认当前账号的访问权限……";
  API.myAccess().then(access => location.replace(loginDestination(next, access)))
    .catch(error => { message.textContent = error.message; });
}
