const open = document.querySelector("#support-open"), dialog = document.querySelector("#support-dialog");
const frame = document.querySelector("#support-frame"), status = document.querySelector("#support-status");
const retry = document.querySelector("#support-retry");
let timeout;
function load() {
  clearTimeout(timeout);
  status.hidden = false;
  status.textContent = "正在连接客服……";
  retry.hidden = true;
  frame.hidden = true;
  frame.src = "/agent/agent.html";
  timeout = setTimeout(() => {
    status.textContent = "客服暂时无法加载，请稍后重试。";
    retry.hidden = false;
  }, 20000);
}
function close() { dialog.close(); }
open.addEventListener("click", () => {
  dialog.showModal();
  open.setAttribute("aria-expanded", "true");
  if (!frame.hasAttribute("src")) load();
});
document.querySelector("#support-close").addEventListener("click", close);
retry.addEventListener("click", load);
dialog.addEventListener("close", () => { open.setAttribute("aria-expanded", "false"); open.focus(); });
dialog.addEventListener("click", event => { if (event.target === dialog) {
  const bounds = dialog.getBoundingClientRect();
  if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) close();
} });
window.addEventListener("message", event => {
  if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
  if (event.data?.type === "support:ready") {
    clearTimeout(timeout);
    status.hidden = true;
    retry.hidden = true;
    frame.hidden = false;
  }
  if (event.data?.type === "support:close") close();
  if (event.data?.type === "support:login") location.assign("/common/login.html");
});
