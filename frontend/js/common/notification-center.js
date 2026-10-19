import { request, readSession } from "./api.js";
import { mountNavigation } from "./navigation.js";
import { canOpenPage, WORKSPACE_PATH } from "./navigation-model.js";

const $ = selector => document.querySelector(selector);
const labels = { announcement: "公共通知", status: "办理状态", reply: "服务回复", important: "重要事项" };
const states = { draft: "草稿", published: "已发布", withdrawn: "已撤回" };
const view = document.body.dataset.noticeView;
let access, offset = 0, personalRevision = 0;
const size = 20;
const node = (tag, text, cls) => {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (cls) element.className = cls;
  return element;
};
function time(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(date);
}
function messageLink(item, publicNotice = false) {
  const link = node("a", undefined, "notice-row" + (item.read_at ? "" : " unread"));
  link.href = "/common/notification-detail.html?key=" + encodeURIComponent(item.key);
  link.dataset.messageKey = item.key;
  const dot = node("span", item.read_at ? "已读" : "未读", "notice-read-state");
  const body = node("div", undefined, "notice-row-body");
  const title = node("div", undefined, "notice-row-title");
  title.append(node("span", publicNotice ? item.pinned ? "置顶" : "公告" : labels[item.kind] || "重要事项", "notice-kind"), node("strong", item.title));
  body.append(title, node("p", item.content.slice(0, 160), "notice-excerpt"));
  const date = node("time", time(item.published_at || item.sent_at || item.created_at));
  link.append(dot, body, date, node("span", "›", "notice-row-arrow"));
  return link;
}
function showError(container, error) {
  if (container) container.replaceChildren(node("p", error.message + "，可点击刷新重试。", "notice-empty notice-error"));
}
async function loadPublic() {
  const container = $("#public-notices");
  const token = readSession()?.accessToken;
  try {
    const data = await request("/common/announcements");
    if (!container?.isConnected || readSession()?.accessToken !== token) return;
    container.replaceChildren(...data.items.map(item => messageLink(item, true)));
    if (!data.items.length) container.append(node("p", "暂无公共通知", "notice-empty"));
  } catch (error) { showError(container, error); }
}
async function loadPersonal() {
  const current = ++personalRevision;
  const token = readSession()?.accessToken;
  const params = new URLSearchParams({ limit: String(size), offset: String(offset) });
  if ($("#notice-read").value === "unread") params.set("unread", "true");
  if ($("#notice-kind").value) params.set("kind", $("#notice-kind").value);
  if ($("#notice-query").value.trim()) params.set("q", $("#notice-query").value.trim());
  try {
    const data = await request("/common/notifications?" + params);
    if (current !== personalRevision || !$("#personal-notices") || readSession()?.accessToken !== token) return;
    if (offset && !data.items.length && data.total <= offset) { offset = 0; return loadPersonal(); }
    $("#personal-notices").replaceChildren(...data.items.map(item => messageLink(item)));
    if (!data.items.length) $("#personal-notices").append(node("p", "暂无符合条件的个人消息", "notice-empty"));
    $("#personal-unread").textContent = `${data.unread_count} 条未读`;
    $("#notice-prev").disabled = offset === 0;
    $("#notice-next").disabled = offset + size >= data.total;
    $("#notice-page").textContent = `第 ${Math.floor(offset / size) + 1} 页 · 共 ${data.total} 条`;
  } catch (error) { if (current === personalRevision) showError($("#personal-notices"), error); }
}
async function loadOverview() {
  await Promise.allSettled([loadPublic(), loadPersonal()]);
  document.documentElement.dataset.notificationReady = "true";
}
async function loadDetail() {
  const status = $("#detail-status");
  try {
    const key = new URLSearchParams(location.search).get("key") || "";
    const data = await request("/common/notifications/" + encodeURIComponent(key));
    if (!$("#notice-detail")) return;
    $("#detail-title").textContent = data.title;
    $("#detail-body").textContent = data.content;
    $("#detail-meta").textContent = `${labels[data.kind] || "通知"} · ${time(data.created_at)}`;
    $("#notice-detail").hidden = false;
    const related = data.related;
    if (related && canOpenPage(related.route, access)) {
      const link = $("#notice-related");
      link.hidden = false;
      link.href = related.route;
      link.addEventListener("click", () => {
        // 复用现有业务布局的记录定位，不更改其页面或表单处理逻辑。
        sessionStorage.setItem("stuproject.live.selection", JSON.stringify(related.selection));
      });
    }
    status.textContent = data.read_at ? "已读" : "正在标记为已读……";
    try {
      await request("/common/notifications/" + encodeURIComponent(key) + "/read", { method: "POST" });
      status.textContent = "已读";
    } catch (error) { status.textContent = "通知已加载，标记已读失败：" + error.message; }
  } catch (error) { status.textContent = error.message; }
  document.documentElement.dataset.notificationReady = "true";
}
const toInputTime = value => value ? new Date(new Date(value).getTime() + 8 * 3600000).toISOString().slice(0, 16) : "";
const fromInputTime = value => value ? new Date(value + "+08:00").toISOString() : null;
function resetForm() {
  $("#announcement-form").reset();
  $("#announcement-id").value = "";
  $("#announcement-version").value = "";
  $("#announcement-form-title").textContent = "新增公共通知";
  $("#announcement-form-status").textContent = "";
}
async function loadManagement() {
  try {
    const data = await request("/common/announcements/manage");
    const list = $("#announcement-list");
    if (!list) return;
    list.replaceChildren();
    for (const item of data.items) {
      const row = node("div", undefined, "notice-manage-row");
      const body = node("div");
      body.append(node("strong", item.title), node("p", `${states[item.status]}${item.pinned ? " · 置顶" : ""} · ${time(item.published_at || item.created_at)}`));
      const edit = node("button", "编辑", "button secondary small");
      edit.type = "button";
      edit.onclick = () => {
        $("#announcement-id").value = item.announcement_id;
        $("#announcement-version").value = item.row_version;
        $("#announcement-title").value = item.title;
        $("#announcement-content").value = item.content;
        $("#announcement-state").value = item.status;
        $("#announcement-pinned").checked = item.pinned;
        $("#announcement-published").value = toInputTime(item.published_at);
        $("#announcement-expires").value = toInputTime(item.expires_at);
        $("#announcement-form-title").textContent = "编辑公共通知";
        $("#announcement-form-status").textContent = "";
        $("#announcement-title").focus();
      };
      row.append(body, edit); list.append(row);
    }
    if (!data.items.length) list.append(node("p", "暂无公告，填写上方表单创建第一条。", "notice-empty"));
  } catch (error) { showError($("#announcement-list"), error); }
  document.documentElement.dataset.notificationReady = "true";
}
function setupManagement() {
  $("#announcement-reset").onclick = resetForm;
  $("#announcement-form").onsubmit = async event => {
    event.preventDefault();
    const button = $("#announcement-save"), status = $("#announcement-form-status");
    if (button.disabled || !event.currentTarget.reportValidity()) return;
    button.disabled = true;
    status.textContent = "正在保存……";
    try {
      const id = $("#announcement-id").value;
      const data = { title: $("#announcement-title").value.trim(), content: $("#announcement-content").value.trim(),
        status: $("#announcement-state").value, pinned: $("#announcement-pinned").checked,
        published_at: fromInputTime($("#announcement-published").value), expires_at: fromInputTime($("#announcement-expires").value) };
      if (id) data.expected_version = Number($("#announcement-version").value);
      const saved = await request("/common/announcements" + (id ? "/" + id : ""), { method: id ? "PATCH" : "POST", body: data });
      $("#announcement-id").value = saved.announcement_id;
      $("#announcement-version").value = saved.row_version;
      $("#announcement-published").value = toInputTime(saved.published_at);
      $("#announcement-form-title").textContent = "编辑公共通知";
      status.textContent = "保存成功。";
      await loadManagement();
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  };
}

document.documentElement.classList.add("permission-loading");
document.addEventListener("click", event => {
  if (event.target.closest("[data-menu]")) {
    const open = document.body.classList.toggle("rail-open");
    $("[data-menu]").setAttribute("aria-expanded", String(open));
  }
  if (event.target.closest(".mobile-scrim")) document.body.classList.remove("rail-open");
});
document.addEventListener("keydown", event => { if (event.key === "Escape") document.body.classList.remove("rail-open"); });
access = await mountNavigation();
if (access) {
  document.documentElement.dataset.workspaceReady = "true";
  if (view === "overview") {
    $("#announcement-manage-link").hidden = !canOpenPage("/common/announcement-manage.html", access);
    $("#notification-refresh").onclick = loadOverview;
    $("#notification-filters").onsubmit = event => { event.preventDefault(); offset = 0; loadPersonal(); };
    for (const selector of ["#notice-read", "#notice-kind"]) $(selector).onchange = () => { offset = 0; loadPersonal(); };
    $("#notice-prev").onclick = () => { offset = Math.max(0, offset - size); loadPersonal(); };
    $("#notice-next").onclick = () => { offset += size; loadPersonal(); };
    window.addEventListener("pageshow", event => { if (event.persisted && readSession()) loadOverview(); });
    await loadOverview();
    window.addEventListener("navigation:updated", event => {
      access = event.detail;
      if (!$("#public-notices") || !readSession()) return;
      $("#announcement-manage-link").hidden = !canOpenPage("/common/announcement-manage.html", access);
      loadOverview();
    });
  } else if (view === "detail") await loadDetail();
  else if (view === "manage") { setupManagement(); await loadManagement(); }
}
