/** 业务页面通用 DOM 工具；业务页面通过独立文档隔离样式和选择器。 */
export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
export const esc = value => String(value ?? "").replace(/[&<>"']/g, character =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);

export function toast(message, type = "") {
  const item = document.createElement("div");
  item.className = `toast ${type}`;
  item.textContent = message;
  $("#toasts").append(item);
  setTimeout(() => item.remove(), 3600);
}

export function riskBadge(risk) {
  const colors = { high: "critical", medium: "serious", low: "good" };
  const names = { high: "高危", medium: "中危", low: "低危" };
  return `<span class="badge ${colors[risk] || "neutral"}">${esc(names[risk] || risk || "—")}</span>`;
}

export function statusBadge(status) {
  const color = ["已签约", "已解决", "已同意", "已完成"].includes(status) ? "good" :
    ["已流失", "已拒绝"].includes(status) ? "critical" :
    ["待处理", "待审批", "处理中", "待跟进", "意向中", "审核中"].includes(status) ? "warning" : "neutral";
  return `<span class="badge ${color}">${esc(status || "—")}</span>`;
}

// 等待后端提供本人身份或授权学生名单，禁止使用源页面硬编码的虚构学生。
export function studentSelect(id) {
  return `<select class="input" id="${esc(id)}" disabled><option value="">待对接授权学生名单</option></select>`;
}
