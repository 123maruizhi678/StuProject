import { request, createRequestId } from "../common/api.js";
import { toBeijingIso } from "./report-api.js";

/* 智能报告模块工作区：概览 / 列表 / 生成 / 阅读 / 配置。
 * live.js 登录后按页面前缀委托本模块渲染（与企业、学生模块同一模式）。
 * 复用 /api/v1/report 五接口与统一 {code,message,data} 信封；
 * 生成请求携带 Idempotency-Key（8—128 位可见 ASCII，同参数重试复用同一键）。
 * 041/044 约定：仅 success 报告发布正文与指标；pending/running 不发布半成品；
 * failed 展示脱敏失败原因，不返回半成品正文。
 */

const REPORT_LABELS = {
  customer_overview: "客户经营分析",
  daily_report: "员工日报（日）",
  weekly_report: "员工日报（周）",
  mental_weekly: "心理健康周报",
  complaint_weekly: "投诉处理周报",
};
const REPORT_DESCRIPTIONS = {
  customer_overview: "客户状态、新增、跟进与研判概览",
  daily_report: "每日正式提交的工作数量与情况",
  weekly_report: "以周为单位呈现工作与协作趋势",
  mental_weekly: "聚合心理评估记录与服务跟进信息",
  complaint_weekly: "工单分类、处理状态与服务时效",
};
const STATUS_LABELS = { pending: "待生成", running: "生成中", success: "已生成", failed: "失败" };
const STATUS_BADGE = { pending: "amber", running: "blue", success: "green", failed: "red" };
const ALL_CODES = Object.keys(REPORT_LABELS);
const ALL_STATUSES = ["pending", "running", "success", "failed"];

const node = (tag, text, cls) => {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (cls) el.className = cls;
  return el;
};
const button = (text, run, cls = "button secondary small") => {
  const el = node("button", text, cls);
  el.type = "button";
  el.onclick = run;
  return el;
};
const link = (text, href, cls = "") => {
  const el = node("a", text, cls);
  el.href = href;
  return el;
};
/** 接口返回 UTC ISO；业务时区为北京时间（UTC+8），界面统一换算为北京时间展示。 */
const formatBeijing = (value) => {
  if (!value) return "—";
  const ms = Date.parse(String(value).replace(" ", "T"));
  if (Number.isNaN(ms)) return String(value);
  const shifted = new Date(ms + 8 * 3600 * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return (
    `${shifted.getUTCFullYear()}-${pad(shifted.getUTCMonth() + 1)}-${pad(shifted.getUTCDate())} ` +
    `${pad(shifted.getUTCHours())}:${pad(shifted.getUTCMinutes())}:${pad(shifted.getUTCSeconds())}`
  );
};
const statusBadge = (status) => {
  const span = node("span", STATUS_LABELS[status] || status, "badge " + (STATUS_BADGE[status] || "outline"));
  return span;
};
const escapeHtml = (value) =>
  String(value == null ? "" : value).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/** 极简 Markdown 渲染：标题、列表、加粗、行内代码、表格、段落（先转义再渲染）。 */
function renderMarkdown(text) {
  const lines = String(text).split(/\r?\n/);
  let html = "";
  let listTag = null;
  let table = [];
  const inline = (value) =>
    escapeHtml(value)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  const flushList = () => { if (listTag) { html += "</" + listTag + ">"; listTag = null; } };
  const flushTable = () => {
    if (!table.length) return;
    const rows = table
      .map((line) => line.replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim()))
      .filter((cells) => !cells.every((cell) => /^:?-+:?$/.test(cell)));
    if (rows.length) {
      html += "<table><thead><tr>" + rows[0].map((c) => "<th>" + inline(c) + "</th>").join("") + "</tr></thead><tbody>";
      rows.slice(1).forEach((cells) => {
        html += "<tr>" + cells.map((c) => "<td>" + inline(c) + "</td>").join("") + "</tr>";
      });
      html += "</tbody></table>";
    }
    table = [];
  };
  lines.forEach((line) => {
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      flushList(); flushTable();
      const level = heading[1].length;
      html += "<h" + level + ">" + inline(heading[2]) + "</h" + level + ">";
      return;
    }
    if (/^\s*\|.*\|\s*$/.test(line)) { flushList(); table.push(line); return; }
    flushTable();
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    const ordered = /^\s*\d+[.、]\s+(.*)$/.exec(line);
    if (bullet || ordered) {
      const tag = bullet ? "ul" : "ol";
      if (listTag !== tag) { flushList(); html += "<" + tag + ">"; listTag = tag; }
      html += "<li>" + inline((bullet || ordered)[1]) + "</li>";
      return;
    }
    flushList();
    if (line.trim()) html += "<p>" + inline(line) + "</p>";
  });
  flushList(); flushTable();
  return html;
}

/* ---------- 生成（幂等） ---------- */

const pendingKeys = new Map();
function generateReport(body) {
  const signature = JSON.stringify(body);
  if (!pendingKeys.has(signature)) pendingKeys.set(signature, `report-${createRequestId()}`);
  return request("/report/generate", {
    method: "POST",
    body,
    headers: { "Idempotency-Key": pendingKeys.get(signature) },
  }).finally(() => pendingKeys.delete(signature));
}

/* ---------- 列表 ---------- */

function listQuery(state) {
  const params = new URLSearchParams();
  if (state.report_code) params.set("report_code", state.report_code);
  if (state.status) params.set("status", state.status);
  params.set("page", String(state.page));
  params.set("page_size", String(state.page_size));
  return params.toString();
}

function renderReportTable(tbody, items, withWindow) {
  tbody.replaceChildren();
  if (!items.length) {
    const tr = node("tr");
    const td = node("td", "暂无授权可见的报告。", "empty-search");
    td.colSpan = withWindow ? 6 : 5;
    tr.append(td);
    tbody.append(tr);
    return;
  }
  for (const item of items) {
    const tr = node("tr");
    const name = node("td");
    name.append(node("strong", item.report_name));
    name.append(node("br"));
    name.append(node("small", "#" + item.report_record_id + " · " + REPORT_LABELS[item.report_code] || item.report_code));
    tr.append(name);
    tr.append(node("td", REPORT_LABELS[item.report_code] || item.report_code));
    if (withWindow) {
      const window = node("td", formatBeijing(item.start_time) + " ~ " + formatBeijing(item.end_time));
      window.style.fontFamily = "var(--mono, monospace)";
      window.style.fontSize = "11.5px";
      tr.append(window);
    }
    const status = node("td");
    status.append(statusBadge(item.status));
    tr.append(status);
    tr.append(node("td", item.generated_at ? formatBeijing(item.generated_at) : "—"));
    tr.append(node("td", String(item.source_record_count ?? "—")));
    const action = node("td");
    action.append(link("查看报告", `detail.html?report_record_id=${item.report_record_id}`));
    tr.append(action);
    tbody.append(tr);
  }
}

async function renderList(main, notify, access) {
  const state = { report_code: "", status: "", page: 1, page_size: 20 };
  const card = node("section", undefined, "section-card");
  const title = node("div", undefined, "section-title");
  const heading = node("div");
  heading.append(node("h2", "报告记录"));
  title.append(heading);
  if ((access.permissions || []).includes("report.generate")) {
    const actions = node("div", undefined, "actions");
    actions.append(link("生成新报告", "generate.html", "button"));
    title.append(actions);
  }
  card.append(title);

  const body = node("div", undefined, "section-body");
  body.style.paddingBottom = "0";
  const toolbar = node("div", undefined, "toolbar");
  const codeSelect = node("select");
  codeSelect.append(new Option("全部类型", ""));
  for (const code of ALL_CODES) codeSelect.append(new Option(REPORT_LABELS[code], code));
  const statusSelect = node("select");
  statusSelect.append(new Option("全部状态", ""));
  for (const status of ALL_STATUSES) statusSelect.append(new Option(STATUS_LABELS[status], status));
  const refresh = button("刷新", load);
  toolbar.append(codeSelect, statusSelect, refresh);
  body.append(toolbar);

  const wrap = node("div", undefined, "table-wrap");
  const table = node("table", undefined, "data-table");
  const head = node("tr");
  for (const label of ["报告名称", "类别", "统计窗口（北京时间）", "状态", "生成日期", "来源记录数", "操作"]) {
    head.append(node("th", label));
  }
  const thead = node("thead");
  thead.append(head);
  table.append(thead);
  const tbody = node("tbody");
  table.append(tbody);
  wrap.append(table);
  body.append(wrap);

  const pager = node("div", undefined, "pager");
  const info = node("span");
  const prev = button("‹ 上一页", () => { if (state.page > 1) { state.page -= 1; load(); } });
  const next = button("下一页 ›", () => { if (state.page * state.page_size < total) { state.page += 1; load(); } });
  pager.append(info, prev, next);
  body.append(pager);
  card.append(body);
  main.append(card);

  let total = 0;
  async function load() {
    prev.disabled = next.disabled = true;
    try {
      const data = await request("/report/list?" + listQuery(state));
      total = data.total;
      renderReportTable(tbody, data.items, true);
      const pages = Math.max(1, Math.ceil(data.total / data.page_size));
      info.textContent = `第 ${data.page} / ${pages} 页 · 共 ${data.total} 条`;
      prev.disabled = data.page <= 1;
      next.disabled = data.page >= pages;
      notify("");
    } catch (error) {
      notify(error.message || "报告列表加载失败。", true);
    }
  }
  codeSelect.onchange = () => { state.report_code = codeSelect.value; state.page = 1; load(); };
  statusSelect.onchange = () => { state.status = statusSelect.value; state.page = 1; load(); };
  await load();
}

/* ---------- 生成 ---------- */

async function renderGenerate(main, notify, access) {
  if (!(access.permissions || []).includes("report.generate")) {
    main.append(node("p", "当前账号没有报告生成权限（report.generate），仅平台管理员可手动生成。", "live-error"));
    return;
  }
  const card = node("section", undefined, "section-card");
  const title = node("div", undefined, "section-title");
  const headingBox = node("div");
  headingBox.append(node("h2", "报告生成设置"));
  title.append(headingBox);
  const back = node("div", undefined, "actions");
  back.append(link("返回报告列表", "list.html", "button secondary"));
  title.append(back);
  card.append(title);

  const body = node("div", undefined, "section-body");
  const grid = node("div", undefined, "form-grid");

  const codeField = node("div", undefined, "form-field");
  codeField.append(node("label", "报告类型 *"));
  const codeSelect = node("select");
  for (const code of ALL_CODES) codeSelect.append(new Option(REPORT_LABELS[code], code));
  codeField.append(codeSelect);

  const startField = node("div", undefined, "form-field");
  startField.append(node("label", "开始日期（可选）"));
  const startInput = node("input");
  startInput.type = "date";
  startInput.title = "不填则按报告周期使用默认窗口；起止时刻固定为北京时间 00:00";
  startField.append(startInput);

  const endField = node("div", undefined, "form-field");
  endField.append(node("label", "截止日期（可选）"));
  const endInput = node("input");
  endInput.type = "date";
  endInput.title = "不填则按报告周期使用默认窗口；起止时刻固定为北京时间 00:00";
  endField.append(endInput);

  const tzField = node("div", undefined, "form-field");
  tzField.append(node("label", "业务时区"));
  const tz = node("div", undefined, "tz-fixed");
  tz.append(node("code", "Asia/Shanghai"));
  tz.append(node("span", "北京时间（固定，不可选）"));
  tzField.append(tz);

  grid.append(codeField, startField, endField, tzField);
  body.append(grid);

  const preview = node("p", undefined, "window-preview");
  body.append(preview);
  const syncPreview = () => {
    const start = startInput.value;
    const end = endInput.value;
    preview.textContent = !start && !end
      ? "未选择日期：按报告周期使用默认窗口（日报=昨天，周报=上一周）。"
      : !start || !end
        ? "开始与截止日期必须成对提供。"
        : `将提交窗口（北京时间）：${start} 00:00 ~ ${end} 00:00`;
  };
  startInput.oninput = endInput.oninput = syncPreview;
  codeSelect.onchange = syncPreview;
  syncPreview();

  const strip = node("div", undefined, "info-strip");
  strip.append(node("p", "报告由授权业务数据与固定指标生成，后台异步执行：受理后立即返回报告编号与待生成状态，请在报告列表中查看进度。日期起止时刻固定为北京时间 00:00。"));
  body.append(strip);

  const actions = node("div", undefined, "form-actions");
  const submit = button("提交生成", () => submitGenerate(), "button");
  actions.append(submit);
  body.append(actions);
  card.append(body);
  main.append(card);

  async function submitGenerate() {
    notify("");
    const bodyPayload = { report_code: codeSelect.value };
    const start = startInput.value;
    const end = endInput.value;
    if (start || end) {
      if (!start || !end) {
        notify("开始与截止时间必须成对提供。", true);
        return;
      }
      try {
        // 仅选日期：起止时刻固定为北京时间 00:00（对日报类即满足 00:00 对齐要求）。
        bodyPayload.start_time = toBeijingIso(start + "T00:00");
        bodyPayload.end_time = toBeijingIso(end + "T00:00");
        if (Date.parse(bodyPayload.start_time) >= Date.parse(bodyPayload.end_time)) {
          throw new Error("截止日期必须晚于开始日期。");
        }
      } catch (validation) {
        notify(validation.message, true);
        return;
      }
    }
    submit.disabled = true;
    try {
      const data = await generateReport(bodyPayload);
      const hint = node("p", undefined, "live-status");
      hint.append(node("span", `已受理：报告 #${data.report_record_id}（${STATUS_LABELS[data.status] || data.status}）`));
      hint.append(node("br"));
      hint.append(link("前往报告列表查看进度", "list.html"));
      notify.replaceChildren(hint);
    } catch (error) {
      notify(error.message || "提交失败，请稍后重试。", true);
    } finally {
      submit.disabled = false;
    }
  }
}

/* ---------- 阅读（详情） ---------- */

async function renderDetail(main, notify, access) {
  const id = new URLSearchParams(location.search).get("report_record_id");
  if (!id || !/^\d+$/.test(id) || Number(id) <= 0) {
    main.append(node("p", "缺少有效的报告编号。", "live-error"));
    main.append(link("返回报告列表", "list.html", "button secondary"));
    return;
  }
  let data;
  try {
    data = await request("/report/" + id);
  } catch (error) {
    main.append(node("p", error.message || "报告不存在或不在可见范围。", "live-error"));
    main.append(link("返回报告列表", "list.html", "button secondary"));
    return;
  }

  const card = node("section", undefined, "section-card");
  const title = node("div", undefined, "section-title");
  const heading = node("div");
  heading.append(node("h2", data.report_name));
  heading.append(node("p", "#" + data.report_record_id + " · " + (REPORT_LABELS[data.report_code] || data.report_code) + " · " + (STATUS_LABELS[data.status] || data.status)));
  title.append(heading);
  const back = node("div", undefined, "actions");
  back.append(link("返回列表", "list.html", "button secondary"));
  title.append(back);
  card.append(title);

  const body = node("div", undefined, "section-body");

  if (data.status === "failed" && data.fail_reason) {
    const strip = node("div", undefined, "info-strip");
    strip.style.borderColor = "var(--crimson)";
    strip.append(node("p", "失败原因（脱敏）：" + data.fail_reason));
    body.append(strip);
  }

  const tabs = node("div", undefined, "tab-list");
  tabs.setAttribute("role", "tablist");
  const panels = [];
  const tabNames = ["报告正文", "指标快照", "生成信息"];
  tabNames.forEach((name, index) => {
    const tab = node("button", name, "tab-button" + (index === 0 ? " active" : ""));
    tab.type = "button";
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", index === 0 ? "true" : "false");
    const panel = node("div");
    panel.dataset.tabPanel = String(index);
    panel.setAttribute("role", "tabpanel");
    if (index > 0) panel.hidden = true;
    tab.onclick = () => {
      tabs.querySelectorAll(".tab-button").forEach((el, i) => {
        el.classList.toggle("active", i === index);
        el.setAttribute("aria-selected", i === index ? "true" : "false");
      });
      panels.forEach((el, i) => { el.hidden = i !== index; });
    };
    tabs.append(tab);
    panels.push(panel);
  });
  body.append(tabs);

  // 报告正文：仅 success 发布；其余状态明确说明（041/044 不发布半成品）。
  const contentPanel = panels[0];
  if (data.status === "success" && data.report_content) {
    const paper = node("article", undefined, "report-md");
    paper.innerHTML = renderMarkdown(data.report_content);
    contentPanel.append(paper);
  } else {
    contentPanel.append(node("p",
      data.status === "success" ? "该报告没有正文内容。" :
      data.status === "failed" ? "生成失败，不发布半成品正文；请查看上方失败原因。" :
      "报告正在生成中，暂不发布半成品正文，完成后自动可见。", "live-status"));
  }

  // 指标快照：仅 success 返回已发布指标；其余状态说明未发布。
  const metricPanel = panels[1];
  if (data.status === "success" && data.metric_json) {
    const entries = Object.entries(data.metric_json).filter(([code]) => !code.startsWith("_"));
    if (!entries.length) {
      metricPanel.append(node("p", "该报告没有指标数据。", "live-status"));
    } else {
      const grid = node("div", undefined, "metric-grid");
      for (const [code, entry] of entries) {
        const card = node("div", "metric-card" + (entry.value == null ? " unavailable" : ""));
        card.append(node("div", code, "metric-code"));
        const value = node("div", undefined, "metric-value");
        value.append(node("span", entry.value == null ? "—" : String(entry.value)));
        if (entry.unit && entry.value != null) value.append(node("span", entry.unit, "metric-unit"));
        card.append(value);
        if (entry.reason) card.append(node("div", entry.reason, "metric-reason"));
        grid.append(card);
      }
      metricPanel.append(grid);
      const note = node("p", undefined, "section-caption");
      note.textContent = "指标为生成时冻结的快照（白名单投影），与正文引用一致。";
      metricPanel.append(note);
    }
  } else {
    metricPanel.append(node("p",
      data.status === "success" ? "该报告没有指标快照。" :
      data.status === "failed" ? "生成失败，未发布指标快照。" :
      "报告正在生成中，暂不发布指标快照。", "live-status"));
  }

  // 生成信息
  const infoPanel = panels[2];
  const infoTable = node("table", undefined, "data-table");
  const infoRows = [
    ["报告编号", String(data.report_record_id)],
    ["报告类型", REPORT_LABELS[data.report_code] || data.report_code + "（" + data.report_code + "）"],
    ["状态", STATUS_LABELS[data.status] || data.status],
    ["报告版本", data.report_version],
    ["业务时区", data.timezone],
    ["统计窗口（北京时间）", formatBeijing(data.start_time) + " ~ " + formatBeijing(data.end_time)],
    ["指标快照时间", formatBeijing(data.data_snapshot_at)],
    ["来源记录数", String(data.source_record_count)],
    ["完成时间", formatBeijing(data.generated_at)],
    ["幂等键", data.idempotency_key || "—"],
  ];
  for (const [key, value] of infoRows) {
    const tr = node("tr");
    tr.append(node("td", key));
    const td = node("td", value);
    if (["报告编号", "统计窗口", "指标快照时间", "来源记录数", "完成时间", "幂等键"].includes(key)) {
      td.style.fontFamily = "var(--mono, monospace)";
      td.style.fontSize = "11.5px";
    }
    tr.append(td);
    infoTable.append(tr);
  }
  infoPanel.append(infoTable);

  panels.forEach((panel) => body.append(panel));
  card.append(body);
  main.append(card);
}

/* ---------- 概览 ---------- */

async function renderOverview(main, notify, access) {
  const data = await request("/report/list?page=1&page_size=100");
  const items = data.items || [];
  const now = new Date();
  const monthPrefix = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const doneThisMonth = items.filter((item) => item.status === "success" && String(item.generated_at || "").startsWith(monthPrefix)).length;
  const inFlight = items.filter((item) => item.status === "pending" || item.status === "running").length;
  const latest = items.filter((item) => item.generated_at).sort((a, b) => (a.generated_at < b.generated_at ? 1 : -1))[0];

  const stats = node("div", undefined, "stats-grid");
  const statCards = [
    ["报告总数", String(data.total), "当前账号可见范围"],
    ["本月已完成", String(doneThisMonth), monthPrefix + " 统计周期"],
    ["生成任务", String(inFlight), "等待或正在生成"],
    ["最近生成", latest ? formatBeijing(latest.generated_at) : "—", latest ? latest.report_name : "暂无已完成报告"],
  ];
  for (const [label, value, note] of statCards) {
    const card = node("div", undefined, "stat-card");
    card.append(node("div", label, "stat-label"));
    const valueEl = node("div", undefined, "stat-value");
    valueEl.append(node("span", value));
    card.append(valueEl);
    card.append(node("div", note, "stat-note"));
    stats.append(card);
  }
  main.append(stats);

  const grid = node("div", undefined, "grid-3");
  for (const code of ALL_CODES) {
    const latestOfCode = items.filter((item) => item.report_code === code).sort((a, b) => b.report_record_id - a.report_record_id)[0];
    const card = node("article", undefined, "section-card category-card");
    const body = node("div", undefined, "section-body");
    body.append(node("h2", REPORT_LABELS[code]));
    body.append(node("p", REPORT_DESCRIPTIONS[code]));
    body.append(latestOfCode && latestOfCode.status === "success"
      ? link("查看最新报告 →", `detail.html?report_record_id=${latestOfCode.report_record_id}`, "tiny")
      : link("去生成 →", "generate.html", "tiny"));
    card.append(body);
    grid.append(card);
  }
  main.append(grid);

  const card = node("section", undefined, "section-card");
  const title = node("div", undefined, "section-title");
  const heading = node("div");
  heading.append(node("h2", "最近的报告"));
  title.append(heading);
  const actions = node("div", undefined, "actions");
  actions.append(link("查看全部 →", "list.html", "tiny"));
  title.append(actions);
  card.append(title);
  const body = node("div", undefined, "section-body");
  body.style.paddingBottom = "0";
  const wrap = node("div", undefined, "table-wrap");
  const table = node("table", undefined, "data-table");
  const head = node("tr");
  for (const label of ["报告名称", "类别", "统计窗口（北京时间）", "状态", "生成日期", "操作"]) {
    head.append(node("th", label));
  }
  const thead = node("thead");
  thead.append(head);
  table.append(thead);
  const tbody = node("tbody");
  renderReportTable(tbody, items.slice(0, 5), true);
  table.append(tbody);
  wrap.append(table);
  body.append(wrap);
  card.append(body);
  main.append(card);
  notify("");
}

/* ---------- 配置 ---------- */

async function renderConfigs(main, notify, access) {
  const writable = (access.permissions || []).includes("report.config.write");
  const card = node("section", undefined, "section-card");
  const title = node("div", undefined, "section-title");
  const heading = node("div");
  heading.append(node("h2", "报告配置"));
  heading.append(node("p", writable ? "修改后按当前版本保存（乐观锁）；并发冲突请刷新后重试。" : "当前账号可查看配置，修改需要平台管理员权限。"));
  title.append(heading);
  card.append(title);
  const body = node("div", undefined, "section-body");
  body.style.paddingBottom = "0";
  const wrap = node("div", undefined, "table-wrap");
  const table = node("table", undefined, "data-table");
  const head = node("tr");
  for (const label of ["报告名称", "周期", "计划时间（cron）", "时区", "状态", "操作"]) {
    head.append(node("th", label));
  }
  const thead = node("thead");
  thead.append(head);
  table.append(thead);
  const tbody = node("tbody");
  table.append(tbody);
  wrap.append(table);
  body.append(wrap);
  card.append(body);
  main.append(card);

  async function load() {
    tbody.replaceChildren();
    let configs;
    try {
      configs = await request("/report/configs");
    } catch (error) {
      notify(error.message || "配置加载失败。", true);
      return;
    }
    for (const config of configs) {
      const tr = node("tr");
      tr.append(node("td", config.report_name));
      tr.append(node("td", config.report_period === "day" ? "每日" : "每周"));
      tr.append(node("td", config.cron_expr || "未设置"));
      tr.append(node("td", "北京时间"));
      const status = node("td");
      status.append(node("span", config.enabled ? "已启用" : "已停用", "badge " + (config.enabled ? "green" : "outline")));
      tr.append(status);
      const action = node("td");
      if (writable) {
        action.append(button("编辑配置", () => openEditor(tr, config)));
      } else {
        action.append(node("span", "—"));
      }
      tr.append(action);
      tbody.append(tr);
    }
    notify("");
  }

  function openEditor(tr, config) {
    if (tr.nextElementSibling && tr.nextElementSibling.classList.contains("config-edit-row")) {
      tr.nextElementSibling.remove();
      return;
    }
    tbody.querySelectorAll(".config-edit-row").forEach((row) => row.remove());
    const editRow = node("tr", undefined, "config-edit-row");
    const cell = node("td");
    cell.colSpan = 6;
    const form = node("div", undefined, "config-edit");
    const name = node("input");
    name.type = "text";
    name.value = config.report_name;
    name.maxLength = 128;
    name.placeholder = "报告名称";
    const cron = node("input");
    cron.type = "text";
    cron.value = config.cron_expr || "";
    cron.placeholder = "cron 六字段（留空关闭调度）";
    const enabled = node("select");
    enabled.append(new Option("启用", "true"), new Option("停用", "false"));
    enabled.value = String(config.enabled);
    const error = node("div", undefined, "config-error");
    const save = button("保存", async () => {
      error.textContent = "";
      save.disabled = true;
      try {
        await request(`/report/configs/${config.report_code}`, {
          method: "PUT",
          body: {
            row_version: config.row_version,
            report_name: name.value.trim(),
            cron_expr: cron.value.trim() || null,
            enabled: enabled.value === "true",
          },
        });
        notify(`配置已更新（${config.report_code}）。`);
        await load();
      } catch (err) {
        error.textContent = err.message || "保存失败。";
      } finally {
        save.disabled = false;
      }
    }, "button");
    const cancel = button("取消", () => editRow.remove());
    form.append(name, cron, enabled, save, cancel, error);
    cell.append(form);
    editRow.append(cell);
    tr.after(editRow);
  }

  await load();
}

/* ---------- 入口 ---------- */

export async function mountReportWorkspace({ main, page, access }) {
  const style = document.createElement("link");
  style.rel = "stylesheet";
  style.href = "/css/report/workspace.css";
  document.head.append(style);

  const notice = node("div");
  notice.setAttribute("aria-live", "polite");
  main.append(notice);
  const notify = (text, error = false) =>
    notice.replaceChildren(text ? node("p", text, error ? "live-error" : "live-status") : node("p"));

  try {
    if (page.startsWith("report/list")) await renderList(main, notify, access);
    else if (page.startsWith("report/generate")) await renderGenerate(main, notify, access);
    else if (page.startsWith("report/detail")) await renderDetail(main, notify, access);
    else if (page.startsWith("report/configs")) await renderConfigs(main, notify, access);
    else await renderOverview(main, notify, access);
  } catch (error) {
    notify(error.message || "报告数据加载失败。", true);
  }
}
