import { CustomerAgentAPI } from "./agent-api.js";
/* Customer Agent UI; isolated to this iframe document. */
(function () {
  "use strict";
  if (document.documentElement.dataset.caReady === "true") return;
  document.documentElement.dataset.caReady = "true";

  var $ = function (id) { return document.getElementById(id); };
  var api = CustomerAgentAPI;
  var sessionId = sessionStorage.getItem("customer-agent-session") || null;
  var busy = false;
  var lastFailedMessage = "";
  var toastTimer;

  function setConnection(online) {
    var status = document.querySelector(".ca-status");
    status.classList.toggle("is-online", online);
    status.classList.toggle("is-offline", !online);
    $("connection-label").textContent = online ? "服务已连接" : "服务暂不可用";
  }
  function toast(message, isError) {
    var el = $("toast");
    el.textContent = message;
    el.classList.toggle("is-error", Boolean(isError));
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.hidden = true; }, 3200);
  }
  function appendMessage(role, text, options) {
    options = options || {};
    var row = document.createElement("article");
    row.className = "ca-message ca-message-" + role + (options.pending ? " ca-pending" : "");
    var avatar = document.createElement("div");
    avatar.className = "ca-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = role === "user" ? "你" : role === "system" ? "!" : "AI";
    var bubble = document.createElement("div");
    bubble.className = "ca-bubble";
    var p = document.createElement("p");
    p.textContent = text;
    bubble.appendChild(p);
    if (options.pending) {
      var dots = document.createElement("span");
      dots.className = "ca-dots";
      dots.setAttribute("aria-label", "正在等待回复");
      for (var i = 0; i < 3; i++) dots.appendChild(document.createElement("i"));
      bubble.appendChild(dots);
    }
    if (options.retry) {
      var retry = document.createElement("button");
      retry.className = "ca-retry";
      retry.type = "button";
      retry.textContent = "重试发送";
      retry.addEventListener("click", function () { sendChat(options.retry); });
      bubble.appendChild(retry);
    }
    if (role !== "system") {
      var time = document.createElement("time");
      time.dateTime = new Date().toISOString();
      time.textContent = new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit" }).format(new Date());
      bubble.appendChild(time);
    }
    row.appendChild(avatar);
    row.appendChild(bubble);
    $("messages").appendChild(row);
    $("messages").scrollTop = $("messages").scrollHeight;
    return row;
  }
  function setPanelState(name, text, error) {
    var state = $(name + "-state");
    state.textContent = text || "";
    state.classList.toggle("is-error", Boolean(error));
    state.hidden = !text;
  }
  function updateSession(id) {
    sessionId = id;
    sessionStorage.setItem("customer-agent-session", id);
    $("session-badge").textContent = "会话 " + id.slice(0, 8);
  }

  async function sendChat(value) {
    var input = $("chat-text");
    var message = String(value == null ? input.value : value).trim();
    if (!message || busy) return;
    if (message.length > 2000) { toast("消息不能超过 2000 个字符", true); return; }
    busy = true;
    $("send-button").disabled = true;
    if (value == null) input.value = "";
    lastFailedMessage = "";
    appendMessage("user", message);
    var pending = appendMessage("assistant", "正在整理回复", { pending: true });
    try {
      var result = await api.chat({ session_id: sessionId, message: message });
      if (!result || typeof result.reply !== "string") throw new Error("客服回复格式异常");
      updateSession(result.session_id);
      setConnection(true);
      pending.remove();
      appendMessage("assistant", result.reply || "客服暂时没有返回文字回复。");
      if (result.need_action && result.action) handleAction(result.action);
    } catch (error) {
      pending.remove();
      setConnection(false);
      lastFailedMessage = message;
      appendMessage("system", "发送失败：" + error.message, { retry: message });
    } finally {
      busy = false;
      $("send-button").disabled = false;
      input.focus();
    }
  }
  function handleAction(action) {
    if (!action || typeof action.type !== "string") return;
    if (action.type === "show_events") { switchTab("events"); loadEvents(); }
    if (action.type === "show_courses") { switchTab("courses"); loadCourses(); }
  }

  function clearList(id) { while ($(id).firstChild) $(id).removeChild($(id).firstChild); }
  function addText(parent, tag, className, text) {
    var el = document.createElement(tag);
    if (className) el.className = className;
    el.textContent = text == null || text === "" ? "—" : String(text);
    parent.appendChild(el);
    return el;
  }
  function makeCard(title, lines, tag) {
    var li = document.createElement("li");
    li.className = "ca-card";
    addText(li, "h4", "", title);
    lines.forEach(function (line) { addText(li, "p", "", line); });
    var meta = document.createElement("div");
    meta.className = "ca-card-meta";
    addText(meta, "span", "ca-tag", tag);
    li.appendChild(meta);
    return { card: li, meta: meta };
  }
  async function loadEvents() {
    setPanelState("event", "正在获取活动…");
    clearList("event-list");
    try {
      var list = await api.events($("event-status").value);
      if (!Array.isArray(list)) throw new Error("活动列表格式异常");
      setConnection(true);
      setPanelState("event", list.length ? "" : "当前没有符合条件的活动");
      list.forEach(function (event) {
        var card = makeCard(event.event_name, [
          (event.event_type || "活动") + " · " + (event.start_time || "时间待定"),
          "地点：" + (event.location || "待确认"),
          event.quota === 0 ? "名额不限" : "名额：" + event.signed_count + " / " + event.quota
        ], event.status || "状态待确认");
        var canSignup = event.status === "报名中" && (!event.quota || event.signed_count < event.quota);
        var signup = document.createElement("button");
        signup.type = "button";
        signup.className = "ca-card-action";
        signup.textContent = canSignup ? "立即报名" : "查看详情";
        card.meta.appendChild(signup);
        signup.addEventListener("click", function () {
          if (canSignup) openSignup(event);
          else showEventDetails(event.event_id, card.card, signup);
        });
        $("event-list").appendChild(card.card);
      });
    } catch (error) {
      setConnection(false);
      setPanelState("event", error.message, true);
      var retry = document.createElement("button");
      retry.type = "button"; retry.className = "ca-card-action"; retry.textContent = "重试";
      retry.addEventListener("click", loadEvents);
      $("event-state").appendChild(document.createTextNode(" "));
      $("event-state").appendChild(retry);
    }
  }
  async function showEventDetails(eventId, card, button) {
    button.disabled = true;
    try {
      var event = await api.event(eventId);
      var detail = document.createElement("p");
      detail.textContent = "报名方式：" + (event.signup_method || "请联系工作人员");
      card.appendChild(detail);
      setConnection(true);
    } catch (error) { toast(error.message, true); setConnection(false); }
    finally { button.disabled = false; }
  }
  function openSignup(event) {
    $("signup-event-id").value = event.event_id;
    $("signup-event-title").textContent = event.event_name;
    $("signup-name").value = "";
    $("signup-phone").value = "";
    $("signup-note").value = "";
    $("signup-error").hidden = true;
    $("signup-submit").disabled = false;
    $("signup-dialog").showModal();
    $("signup-name").focus();
  }
  async function submitSignup(event) {
    event.preventDefault();
    var name = $("signup-name").value.trim();
    var phone = $("signup-phone").value.trim();
    var phonePattern = /^[+()\-\s\d]{6,32}$/;
    if (!name || name.length > 64) { showSignupError("请输入有效姓名（最多 64 个字符）"); return; }
    if (!phonePattern.test(phone)) { showSignupError("请检查手机号格式"); return; }
    var body = { event_id: Number($("signup-event-id").value), customer_name: name, customer_phone: phone };
    var note = $("signup-note").value.trim();
    if (note) body.customer_info = { note: note };
    $("signup-submit").disabled = true;
    showSignupError("");
    try {
      var result = await api.signup(body);
      $("signup-dialog").close();
      setConnection(true);
      toast("报名已提交 · 编号 " + result.signup_id, false);
      loadEvents();
    } catch (error) {
      setConnection(false);
      showSignupError(error.message);
    } finally { $("signup-submit").disabled = false; }
  }
  function showSignupError(message) {
    var el = $("signup-error");
    el.textContent = message;
    el.hidden = !message;
  }
  async function loadCourses() {
    setPanelState("course", "正在获取课程…");
    clearList("course-list");
    try {
      var list = await api.courses($("course-category").value);
      if (!Array.isArray(list)) throw new Error("课程列表格式异常");
      setConnection(true);
      setPanelState("course", list.length ? "" : "当前没有符合条件的课程");
      list.forEach(function (course) {
        var card = makeCard(course.course_name, [
          (course.category || "课程") + " · 适合：" + (course.target_audience || "请咨询客服"),
          course.description || "暂无课程简介",
          "地点：" + (course.location || "请咨询") + " · 报名：" + (course.signup_method || "请咨询")
        ], course.category || "课程");
        card.meta.removeChild(card.meta.firstChild);
        $("course-list").appendChild(card.card);
      });
    } catch (error) {
      setConnection(false);
      setPanelState("course", error.message, true);
      var retry = document.createElement("button");
      retry.type = "button"; retry.className = "ca-card-action"; retry.textContent = "重试";
      retry.addEventListener("click", loadCourses);
      $("course-state").appendChild(document.createTextNode(" "));
      $("course-state").appendChild(retry);
    }
  }
  async function searchFaq(event) {
    event.preventDefault();
    var question = $("faq-keyword").value.trim();
    if (question.length > 200) { toast("关键词不能超过 200 个字符", true); return; }
    $("faq-result").hidden = true;
    setPanelState("faq", "正在搜索…");
    try {
      var result = await api.faq(question);
      if (!result || typeof result.answer !== "string") throw new Error("FAQ 响应格式异常");
      $("faq-result").replaceChildren();
      addText($("faq-result"), "h4", "", result.question);
      addText($("faq-result"), "p", "", result.answer);
      $("faq-result").hidden = false;
      setPanelState("faq", "");
      setConnection(true);
    } catch (error) { setPanelState("faq", error.message, true); setConnection(false); }
  }
  function switchTab(name) {
    document.querySelectorAll(".ca-tab").forEach(function (tab) {
      var active = tab.dataset.tab === name;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    ["events", "courses", "faq"].forEach(function (key) {
      var panel = $("panel-" + key);
      panel.hidden = key !== name;
      panel.classList.toggle("is-active", key === name);
    });
    if (name === "courses" && !$("course-list").childElementCount) loadCourses();
  }

  $("chat-form").addEventListener("submit", function (event) { event.preventDefault(); sendChat(); });
  $("chat-text").addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendChat(); }
  });
  $("chat-text").addEventListener("input", function () { this.style.height = "auto"; this.style.height = Math.min(this.scrollHeight, 112) + "px"; });
  document.querySelectorAll(".ca-chip").forEach(function (chip) {
    chip.addEventListener("click", function () { $("chat-text").value = chip.dataset.prompt; sendChat(); });
  });
  document.querySelectorAll(".ca-tab").forEach(function (tab) { tab.addEventListener("click", function () { switchTab(tab.dataset.tab); }); });
  $("refresh-events").addEventListener("click", loadEvents);
  $("event-status").addEventListener("change", loadEvents);
  $("refresh-courses").addEventListener("click", loadCourses);
  $("course-category").addEventListener("change", loadCourses);
  $("faq-form").addEventListener("submit", searchFaq);
  $("signup-form").addEventListener("submit", submitSignup);
  $("signup-close").addEventListener("click", function () { $("signup-dialog").close(); });
  $("signup-dialog").addEventListener("click", function (event) { if (event.target === this) this.close(); });

  if (sessionId) $("session-badge").textContent = "会话 " + sessionId.slice(0, 8);
  loadEvents();
})();
