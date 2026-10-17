/** 客服 Agent 前端：对话 / 活动 / 课程 / FAQ / 报名。
 * 对应后端六个匿名接口（前缀 /api/v1）：
 *   POST /agent/chat、GET /agent/events、GET /agent/events/{id}、
 *   POST /agent/events/signup、GET /agent/courses、GET /agent/faq
 * 统一响应信封 {code, message, data}；code=0 成功。
 */
(function () {
  "use strict";

  var API = "/api/v1";
  var sessionId = null;

  var $ = function (id) { return document.getElementById(id); };

  // ---------- 通用 ----------
  function toast(text, isError) {
    var el = $("toast");
    el.textContent = text;
    el.className = "toast" + (isError ? " error" : "");
    el.hidden = false;
    clearTimeout(el._timer);
    el._timer = setTimeout(function () { el.hidden = true; }, 2600);
  }

  function api(path, options) {
    return fetch(API + path, {
      method: (options && options.method) || "GET",
      headers: { "Content-Type": "application/json" },
      body: options && options.body ? JSON.stringify(options.body) : undefined,
    })
      .then(function (res) { return res.json(); })
      .then(function (envelope) {
        if (!envelope || envelope.code !== 0) {
          throw new Error((envelope && envelope.message) || "请求失败");
        }
        return envelope.data;
      });
  }

  function addMessage(role, text) {
    var box = $("messages");
    var div = document.createElement("div");
    div.className = "msg " + role;
    div.textContent = text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  }

  // ---------- 对话 ----------
  function sendChat(message) {
    addMessage("user", message);
    var thinking = document.createElement("div");
    thinking.className = "msg assistant";
    thinking.textContent = "正在输入…";
    $("messages").appendChild(thinking);

    return api("/agent/chat", {
      method: "POST",
      body: { session_id: sessionId, message: message },
    })
      .then(function (data) {
        sessionId = data.session_id;
        $("session-badge").textContent = "会话 " + data.session_id.slice(0, 8);
        thinking.remove();
        addMessage("assistant", data.reply || "");
        if (data.need_action && data.action) {
          handleAction(data.action);
        }
      })
      .catch(function (err) {
        thinking.remove();
        addMessage("system", "发送失败：" + err.message);
      });
  }

  function handleAction(action) {
    if (action.type === "show_events") {
      switchTab("events");
      loadEvents();
    } else if (action.type === "show_courses") {
      switchTab("courses");
      loadCourses();
    }
  }

  $("chat-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var input = $("chat-text");
    var text = input.value.trim();
    if (!text) return;
    input.value = "";
    sendChat(text);
  });

  // ---------- 活动 ----------
  function loadEvents() {
    var status = $("event-status").value;
    api("/agent/events" + (status ? "?status=" + encodeURIComponent(status) : ""))
      .then(renderEvents)
      .catch(function (err) { toast(err.message, true); });
  }

  function renderEvents(list) {
    var box = $("event-list");
    box.innerHTML = "";
    if (!list || !list.length) {
      box.innerHTML = '<li class="card"><p>暂无活动</p></li>';
      return;
    }
    list.forEach(function (e) {
      var li = document.createElement("li");
      li.className = "card";
      var open = e.status === "报名中" && (e.quota === 0 || e.signed_count < e.quota);
      li.innerHTML =
        "<h3></h3>" +
        "<p>类型：" + esc(e.event_type) + " · 时间：" + esc(e.start_time) + "</p>" +
        "<p>地点：" + esc(e.location) + "</p>" +
        '<div class="meta"><span class="quota">' +
        (e.quota === 0 ? "名额不限" : "名额 " + e.signed_count + "/" + e.quota) +
        " · " + esc(e.status) + "</span></div>";
      li.querySelector("h3").textContent = e.event_name;
      var btn = document.createElement("button");
      btn.textContent = "报名";
      btn.disabled = !open;
      btn.addEventListener("click", function () { openSignup(e); });
      li.querySelector(".meta").appendChild(btn);
      box.appendChild(li);
    });
  }

  function openSignup(event) {
    $("signup-title").textContent = "报名：" + event.event_name;
    $("signup-event-id").value = event.event_id;
    $("signup-name").value = "";
    $("signup-phone").value = "";
    $("signup-info").value = "";
    $("signup-dialog").showModal();
  }

  $("signup-cancel").addEventListener("click", function () { $("signup-dialog").close(); });

  $("signup-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var payload = {
      event_id: Number($("signup-event-id").value),
      customer_name: $("signup-name").value.trim(),
      customer_phone: $("signup-phone").value.trim(),
    };
    var info = $("signup-info").value.trim();
    if (info) payload.customer_info = { note: info };

    api("/agent/events/signup", { method: "POST", body: payload })
      .then(function (data) {
        $("signup-dialog").close();
        toast("报名成功（单号 " + data.signup_id + "）");
        loadEvents();
      })
      .catch(function (err) { toast(err.message, true); });
  });

  // ---------- 课程 ----------
  function loadCourses() {
    var category = $("course-category").value;
    api("/agent/courses" + (category ? "?category=" + encodeURIComponent(category) : ""))
      .then(renderCourses)
      .catch(function (err) { toast(err.message, true); });
  }

  function renderCourses(list) {
    var box = $("course-list");
    box.innerHTML = "";
    if (!list || !list.length) {
      box.innerHTML = '<li class="card"><p>暂无课程</p></li>';
      return;
    }
    list.forEach(function (c) {
      var li = document.createElement("li");
      li.className = "card";
      li.innerHTML =
        "<h3></h3>" +
        "<p>类别：" + esc(c.category) + " · 适合：" + esc(c.target_audience) + "</p>" +
        "<p>地点：" + esc(c.location) + " · 报名方式：" + esc(c.signup_method) + "</p>";
      li.querySelector("h3").textContent = c.course_name;
      box.appendChild(li);
    });
  }

  // ---------- FAQ ----------
  function searchFaq() {
    var kw = $("faq-keyword").value.trim();
    api("/agent/faq" + (kw ? "?question=" + encodeURIComponent(kw) : ""))
      .then(function (data) {
        $("faq-result").innerHTML =
          "<h3></h3><div class='answer'></div>";
        $("faq-result").querySelector("h3").textContent = data.question;
        $("faq-result").querySelector(".answer").textContent = data.answer;
      })
      .catch(function (err) {
        $("faq-result").innerHTML = '<p class="empty"></p>';
        $("faq-result").querySelector(".empty").textContent = err.message;
      });
  }

  // ---------- Tab 切换 ----------
  function switchTab(name) {
    document.querySelectorAll(".tab").forEach(function (t) {
      t.classList.toggle("active", t.dataset.tab === name);
    });
    document.querySelectorAll(".tab-panel").forEach(function (p) {
      p.classList.toggle("active", p.id === "tab-" + name);
    });
  }

  document.querySelectorAll(".tab").forEach(function (t) {
    t.addEventListener("click", function () { switchTab(t.dataset.tab); });
  });

  $("refresh-events").addEventListener("click", loadEvents);
  $("refresh-courses").addEventListener("click", loadCourses);
  $("search-faq").addEventListener("click", searchFaq);
  $("faq-keyword").addEventListener("keydown", function (e) {
    if (e.key === "Enter") searchFaq();
  });

  function esc(text) {
    return String(text == null ? "" : text).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  // 初始加载
  loadEvents();
})();
