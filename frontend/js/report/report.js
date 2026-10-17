/* 智能报告页面脚本：登录、列表、详情、生成与配置管理。
 * 复用 /api/v1/report 五接口；统一 {code,message,data} 信封；
 * 生成请求必须携带 Idempotency-Key（8—128 位可见 ASCII，重试复用）。
 */
(function () {
  "use strict";

  var BASE = "/api/v1";
  var TOKEN_KEY = "report-token";
  var ME_KEY = "report-me";
  var page = 1;
  var pageSize = 20;
  var total = 0;

  var $ = function (sel) { return document.querySelector(sel); };

  /* ---------- 基础设施 ---------- */

  function toast(message, type) {
    var wrap = $("#toasts");
    var item = document.createElement("div");
    item.className = "toast " + (type || "");
    item.textContent = message;
    wrap.appendChild(item);
    setTimeout(function () { item.remove(); }, 3600);
  }

  function token() { return localStorage.getItem(TOKEN_KEY) || ""; }

  function request(method, path, body, headers) {
    var opts = { method: method, headers: {} };
    if (token()) opts.headers["Authorization"] = "Bearer " + token();
    if (body !== undefined && body !== null) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    Object.keys(headers || {}).forEach(function (key) { opts.headers[key] = headers[key]; });
    return fetch(BASE + path, opts).then(function (resp) {
      return resp.json().catch(function () {
        throw new Error("服务返回异常（HTTP " + resp.status + "）");
      }).then(function (json) {
        if (json.code !== 0) {
          var error = new Error(json.message || "请求失败");
          error.code = json.code;
          throw error;
        }
        return json.data;
      });
    });
  }

  function newIdempotencyKey() {
    var bytes = new Uint8Array(12);
    (window.crypto || {}).getRandomValues
      ? window.crypto.getRandomValues(bytes)
      : bytes.forEach(function (_, i) { bytes[i] = Math.floor(Math.random() * 256); });
    var text = Array.from(bytes, function (b) {
      return ("0" + b.toString(16)).slice(-2);
    }).join("");
    return "report-" + text; // 8—128 位可见 ASCII
  }

  function formatTime(value) {
    if (!value) return "—";
    return String(value).replace("T", " ").replace(/\.\d+Z?$/, "Z").slice(0, 19) + "Z";
  }

  function statusLabel(status) {
    return { pending: "待生成", running: "生成中", success: "已生成", failed: "失败" }[status] || status;
  }

  /* ---------- 登录 / 身份 ---------- */

  function login(username, password) {
    return request("POST", "/auth/login", { username: username, password: password })
      .then(function (data) {
        localStorage.setItem(TOKEN_KEY, data.access_token);
        return request("GET", "/auth/me/access");
      })
      .then(function (access) {
        localStorage.setItem(ME_KEY, JSON.stringify(access));
        return access;
      });
  }

  function currentAccess() {
    try { return JSON.parse(localStorage.getItem(ME_KEY) || "null"); }
    catch (e) { return null; }
  }

  function hasPermission(permission) {
    var access = currentAccess();
    return !!(access && (access.permissions || []).indexOf(permission) >= 0);
  }

  function refreshIdentity() {
    var access = currentAccess();
    var badge = $("#identityBadge");
    var logout = $("#logoutBtn");
    if (!access) {
      badge.hidden = true;
      logout.hidden = true;
      $("#loginCard").hidden = false;
      $("#workspace").hidden = true;
      return;
    }
    badge.hidden = false;
    badge.textContent = (access.identity_type === "admin" ? "平台管理员" : "员工") + " · " +
      (access.permissions || []).filter(function (p) { return p.indexOf("report.") === 0; })
        .map(function (p) { return p.replace("report.", ""); }).join(" / ");
    logout.hidden = false;
    $("#loginCard").hidden = true;
    $("#workspace").hidden = false;
    $("#generateBtn").hidden = !hasPermission("report.generate");
    $("#configCard").hidden = !hasPermission("report.config.read");
    if (hasPermission("report.config.read")) loadConfigs();
  }

  /* ---------- 列表 ---------- */

  function loadList() {
    var params = new URLSearchParams();
    var code = $("#filterCode").value;
    var status = $("#filterStatus").value;
    if (code) params.set("report_code", code);
    if (status) params.set("status", status);
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    return request("GET", "/report/list?" + params.toString())
      .then(function (data) {
        total = data.total;
        renderList(data);
      })
      .catch(function (error) { toast(error.message, "error"); });
  }

  function renderList(data) {
    var tbody = $("#reportRows");
    tbody.innerHTML = "";
    if (!data.items.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="hint">暂无授权可见的报告。</td></tr>';
    }
    data.items.forEach(function (item) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + item.report_record_id + "</td>" +
        "<td>" + escapeHtml(item.report_name) + "</td>" +
        "<td>" + escapeHtml(item.report_code) + "</td>" +
        "<td>" + formatTime(item.start_time) + " ~ " + formatTime(item.end_time) + "</td>" +
        '<td><span class="status ' + item.status + '">' + statusLabel(item.status) + "</span></td>" +
        "<td>" + formatTime(item.generated_at) + "</td>" +
        '<td><button class="btn sm" data-id="' + item.report_record_id + '">详情</button></td>';
      tr.querySelector("button").addEventListener("click", function () {
        openDetail(item.report_record_id);
      });
      tbody.appendChild(tr);
    });
    var pages = Math.max(1, Math.ceil(data.total / data.page_size));
    $("#pageInfo").textContent = "第 " + data.page + " / " + pages + " 页 · 共 " + data.total + " 条";
    $("#prevPage").disabled = data.page <= 1;
    $("#nextPage").disabled = data.page >= pages;
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* ---------- 详情 ---------- */

  function openDetail(id) {
    request("GET", "/report/" + id)
      .then(function (data) { renderDetail(data); })
      .catch(function (error) { toast(error.message, "error"); });
  }

  function renderDetail(data) {
    $("#detailTitle").textContent = data.report_name + "（#" + data.report_record_id + "）";
    var meta = [
      ["类型", data.report_code],
      ["状态", statusLabel(data.status)],
      ["版本", data.report_version],
      ["时区", data.timezone],
      ["窗口", formatTime(data.start_time) + " ~ " + formatTime(data.end_time)],
      ["快照时间", formatTime(data.data_snapshot_at)],
      ["来源记录数", data.source_record_count],
      ["完成时间", formatTime(data.generated_at)],
    ];
    $("#detailMeta").innerHTML = meta.map(function (pair) {
      return "<div><dt>" + escapeHtml(pair[0]) + "</dt><dd>" + escapeHtml(pair[1]) + "</dd></div>";
    }).join("");

    var metrics = $("#detailMetrics");
    metrics.innerHTML = "";
    var entries = data.metric_json || {};
    Object.keys(entries).forEach(function (code) {
      var entry = entries[code];
      var box = document.createElement("div");
      box.className = "metric";
      var value = entry.value == null ? "—" : entry.value;
      box.innerHTML =
        '<div class="code">' + escapeHtml(code) + "</div>" +
        '<div class="value">' + escapeHtml(value) +
        (entry.unit && entry.value != null ? '<span class="unit">' + escapeHtml(entry.unit) + "</span>" : "") + "</div>" +
        (entry.reason ? '<div class="reason">' + escapeHtml(entry.reason) + "</div>" : "");
      metrics.appendChild(box);
    });

    $("#detailContent").innerHTML = data.report_content ? renderMarkdown(data.report_content) : "";
    var fail = $("#detailFail");
    if (data.status === "failed" && data.fail_reason) {
      fail.hidden = false;
      fail.textContent = "失败原因（脱敏）：" + data.fail_reason;
    } else {
      fail.hidden = true;
    }
    $("#detailCard").hidden = false;
    $("#detailCard").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  /* 极简 Markdown 渲染：标题、列表、加粗、行内代码、表格、段落（先转义）。 */
  function renderMarkdown(text) {
    var lines = String(text).split(/\r?\n/);
    var html = "";
    var inList = null;
    var tableBuffer = [];

    function inline(value) {
      return escapeHtml(value)
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    }
    function flushList() {
      if (inList) { html += "</" + inList + ">"; inList = null; }
    }
    function flushTable() {
      if (!tableBuffer.length) return;
      var rows = tableBuffer.map(function (line) {
        return line.replace(/^\||\|$/g, "").split("|").map(function (cell) { return cell.trim(); });
      }).filter(function (cells) {
        return !cells.every(function (cell) { return /^:?-+:?$/.test(cell); });
      });
      if (rows.length) {
        html += "<table><thead><tr>" + rows[0].map(function (cell) {
          return "<th>" + inline(cell) + "</th>";
        }).join("") + "</tr></thead><tbody>";
        rows.slice(1).forEach(function (cells) {
          html += "<tr>" + cells.map(function (cell) { return "<td>" + inline(cell) + "</td>"; }).join("") + "</tr>";
        });
        html += "</tbody></table>";
      }
      tableBuffer = [];
    }

    lines.forEach(function (line) {
      var heading = /^(#{1,4})\s+(.*)$/.exec(line);
      if (heading) {
        flushList(); flushTable();
        var level = heading[1].length;
        html += "<h" + level + ">" + inline(heading[2]) + "</h" + level + ">";
        return;
      }
      if (/^\s*\|.*\|\s*$/.test(line)) { flushList(); tableBuffer.push(line); return; }
      flushTable();
      var bullet = /^\s*[-*]\s+(.*)$/.exec(line);
      var ordered = /^\s*\d+[.、]\s+(.*)$/.exec(line);
      if (bullet || ordered) {
        var tag = bullet ? "ul" : "ol";
        if (inList !== tag) { flushList(); html += "<" + tag + ">"; inList = tag; }
        html += "<li>" + inline((bullet || ordered)[1]) + "</li>";
        return;
      }
      flushList();
      if (line.trim()) html += "<p>" + inline(line) + "</p>";
    });
    flushList(); flushTable();
    return html;
  }

  /* ---------- 生成 ---------- */

  function submitGenerate() {
    var error = $("#genError");
    error.hidden = true;
    var body = { report_code: $("#genCode").value };
    var start = $("#genStart").value;
    var end = $("#genEnd").value;
    if (start || end) {
      if (!start || !end) {
        error.hidden = false;
        error.textContent = "开始与截止时间必须成对提供。";
        return;
      }
      body.start_time = toBeijingIso(start);
      body.end_time = toBeijingIso(end);
    }
    var button = $("#genSubmit");
    button.disabled = true;
    request("POST", "/report/generate", body, { "Idempotency-Key": newIdempotencyKey() })
      .then(function (data) {
        toast("已受理：报告 #" + data.report_record_id + "（" + statusLabel(data.status) + "）", "success");
        $("#generateCard").hidden = true;
        page = 1;
        return loadList();
      })
      .catch(function (err) {
        error.hidden = false;
        error.textContent = err.message;
      })
      .then(function () { button.disabled = false; });
  }

  function toBeijingIso(localValue) {
    // datetime-local 输入按浏览器本地时区解释，转为带 +08:00 偏移的 ISO 文本。
    var date = new Date(localValue + ":00");
    var shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return shifted.toISOString().slice(0, 19) + "+08:00";
  }

  /* ---------- 配置 ---------- */

  function loadConfigs() {
    return request("GET", "/report/configs")
      .then(function (configs) { renderConfigs(configs); })
      .catch(function (error) { toast(error.message, "error"); });
  }

  function renderConfigs(configs) {
    var wrap = $("#configList");
    wrap.innerHTML = "";
    var writable = hasPermission("report.config.write");
    configs.forEach(function (config) {
      var box = document.createElement("div");
      box.className = "config-item";
      box.innerHTML =
        '<div class="title">' + escapeHtml(config.report_name) + "</div>" +
        '<div class="desc">' + escapeHtml(config.report_code) + " · 周期 " +
        escapeHtml(config.report_period) + " · cron " + escapeHtml(config.cron_expr || "未设置") +
        " · row_version " + config.row_version + "</div>";
      if (writable) {
        var row = document.createElement("div");
        row.className = "row";
        var name = document.createElement("input");
        name.type = "text"; name.value = config.report_name; name.maxLength = 128;
        var cron = document.createElement("input");
        cron.type = "text"; cron.value = config.cron_expr || ""; cron.placeholder = "cron（可留空关闭调度）";
        var enabled = document.createElement("select");
        enabled.innerHTML = '<option value="true">启用</option><option value="false">停用</option>';
        enabled.value = String(config.enabled);
        var save = document.createElement("button");
        save.className = "btn sm primary";
        save.textContent = "保存";
        save.addEventListener("click", function () {
          save.disabled = true;
          request("PUT", "/report/configs/" + config.report_code, {
            row_version: config.row_version,
            report_name: name.value.trim(),
            cron_expr: cron.value.trim() || null,
            enabled: enabled.value === "true",
          })
            .then(function (updated) {
              toast("配置已更新（row_version " + updated.row_version + "）", "success");
              return loadConfigs();
            })
            .catch(function (err) { toast(err.message, "error"); })
            .then(function () { save.disabled = false; });
        });
        row.appendChild(name); row.appendChild(cron); row.appendChild(enabled); row.appendChild(save);
        box.appendChild(row);
      }
      wrap.appendChild(box);
    });
  }

  /* ---------- 主题与事件 ---------- */

  function initTheme() {
    var saved = localStorage.getItem("report-theme") || "dark";
    document.documentElement.dataset.theme = saved;
    $("#themeBtn").textContent = saved === "dark" ? "🌙" : "☀️";
    $("#themeBtn").addEventListener("click", function () {
      var next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      localStorage.setItem("report-theme", next);
      $("#themeBtn").textContent = next === "dark" ? "🌙" : "☀️";
    });
  }

  function initEvents() {
    $("#loginBtn").addEventListener("click", function () {
      var error = $("#loginError");
      error.hidden = true;
      login($("#username").value.trim(), $("#password").value)
        .then(function () {
          toast("登录成功", "success");
          refreshIdentity();
          page = 1;
          return loadList();
        })
        .catch(function (err) {
          error.hidden = false;
          error.textContent = err.message;
        });
    });

    $("#logoutBtn").addEventListener("click", function () {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(ME_KEY);
      refreshIdentity();
    });

    $("#refreshBtn").addEventListener("click", loadList);
    $("#prevPage").addEventListener("click", function () { if (page > 1) { page -= 1; loadList(); } });
    $("#nextPage").addEventListener("click", function () {
      if (page * pageSize < total) { page += 1; loadList(); }
    });
    $("#filterCode").addEventListener("change", function () { page = 1; loadList(); });
    $("#filterStatus").addEventListener("change", function () { page = 1; loadList(); });

    $("#generateBtn").addEventListener("click", function () {
      $("#generateCard").hidden = false;
      $("#generateCard").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    $("#genCancel").addEventListener("click", function () { $("#generateCard").hidden = true; });
    $("#genSubmit").addEventListener("click", submitGenerate);

    $("#detailClose").addEventListener("click", function () { $("#detailCard").hidden = true; });

    $("#password").addEventListener("keydown", function (event) {
      if (event.key === "Enter") $("#loginBtn").click();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTheme();
    initEvents();
    refreshIdentity();
    if (token() && currentAccess()) {
      loadList();
    }
  });
})();
