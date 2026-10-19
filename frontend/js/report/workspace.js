import { $, $$, esc } from "../common/ui.js";
import { Viz } from "../common/charts.js";
import { API } from "../common/module-api.js";

/* 智能报告模块渲染：概览分块 + 列表 + 详情图表与正文。
 * 由 live.js 在 report/report.html、report/list.html、report/detail.html
 * 三个页面分派到这里，替代通用 schema 渲染；只读、仅前端展示。
 * 指标条目对外投影为 {value, unit, availability, reason?, metric_version}，
 * unit 为语义类型 count/rate/duration/score（见 report_metrics.py）。
 */

const style = document.createElement("link");
style.rel = "stylesheet";
style.href = "../css/report/workspace.css";
document.head.append(style);

const PAGE_SIZE = 20;
const SERIES_NAMES = ["--s1", "--s2", "--s3", "--s4"];
/* 延迟取系列色：--s1..--s4 由注入的 workspace.css 定义，模块加载时样式表
   尚未解析，若此刻 getComputedStyle 会拿到空串，SVG fill="" 便默认渲染成
   黑色条块；改为每次渲染时再读取，确保拿到真实颜色。 */
const seriesColor = (i) => Viz.cssVar(SERIES_NAMES[i % SERIES_NAMES.length]);

const STATUS_META = {
  pending: { label: "待生成", cls: "neutral" },
  running: { label: "生成中", cls: "amber" },
  success: { label: "已生成", cls: "green" },
  failed: { label: "失败", cls: "red" },
};

const REPORT_CODE_NAMES = {
  customer_overview: "客户经营分析",
  daily_report: "员工日报汇总",
  weekly_report: "员工周报",
  mental_weekly: "学生心理周报",
  complaint_weekly: "投诉处理周报",
};

const METRIC_LABELS = {
  customer_total: "客户总数",
  customer_archived_count: "已归档客户数",
  customer_new_count: "新增客户数",
  customer_new_change_rate: "新增客户环比",
  followup_count: "跟进次数",
  followup_customer_count: "被跟进客户数",
  customer_lost_event_count: "期间流失客户数",
  research_customer_count: "已研判客户数",
  research_matched_customer_count: "命中客户数",
  research_match_rate: "研判命中率",
  daily_submitted_count: "提交日报数",
  daily_author_count: "提交人数",
  daily_void_count: "作废日报数",
  mental_assessment_count: "心理评估数",
  mental_warning_count: "心理预警数",
  mental_assessment_change_rate: "评估数环比",
  mental_warning_change_rate: "预警数环比",
  complaint_new_count: "新增投诉数",
  complaint_new_change_rate: "新增投诉环比",
  complaint_open_count: "未结投诉存量",
  complaint_first_response_hours: "首次回应平均时长",
  complaint_closed_count: "关闭投诉数",
  complaint_close_hours: "关闭平均时长",
  complaint_satisfaction_avg: "满意度均分",
  complaint_satisfaction_rate: "满意度（4–5分占比）",
  complaint_rating_coverage_rate: "评价覆盖率",
  complaint_first_response_timely_rate: "首次回应及时率",
  complaint_response_overdue_count: "超期未回应数",
  complaint_resolution_overdue_count: "超期未给方案数",
  complaint_cycle_solution_hours: "每轮给方案平均时长",
  complaint_solved_cycle_count: "给方案轮次数",
  complaint_closed_cycle_count: "关闭轮次数",
  complaint_solution_timely_rate: "方案及时率",
};

const ENUM_NAMES = {
  new: "新客户", contacting: "跟进中", qualified: "意向确认", signed: "已签约", lost: "已流失",
  active: "有效", disabled: "停用", pending: "待处理", in_progress: "进行中", completed: "已完成", cancelled: "已取消",
  closed: "已关闭", open: "未结", awaiting_student: "待学生确认", reopened: "已重开", resolved: "已解决",
  high: "高危", medium: "中危", low: "低危",
};

function fmtTime(value) {
  if (!value) return "—";
  return String(value).replace("T", " ").replace(/\.\d+/, "").slice(0, 19);
}

function metricLabel(code) {
  if (METRIC_LABELS[code]) return METRIC_LABELS[code];
  const dynamic = [
    [/^customer_state_(.+)$/, (m) => `客户状态「${ENUM_NAMES[m[1]] || m[1]}」`],
    [/^mental_risk_(.+)_count$/, (m) => `风险等级「${ENUM_NAMES[m[1]] || m[1]}」评估数`],
    [/^mental_warning_(.+)_count$/, (m) => `预警状态「${ENUM_NAMES[m[1]] || m[1]}」数`],
    [/^complaint_new_state_(.+)_count$/, (m) => `新增投诉「${ENUM_NAMES[m[1]] || m[1]}」数`],
    [/^complaint_category_(.+)_count$/, (m) => `投诉分类「${m[1]}」数`],
  ];
  for (const [re, fn] of dynamic) {
    const m = re.exec(code);
    if (m) return fn(m);
  }
  return code.replaceAll("_", " ");
}

function metricValue(entry) {
  const v = entry.value;
  if (v == null) return "—";
  if (entry.unit === "rate") return Viz.fmt(v) + "%";
  if (entry.unit === "duration") return Viz.fmt(v) + " 小时";
  if (entry.unit === "score") return Viz.fmt(v) + " 分";
  return Viz.fmt(v);
}

function statusBadge(status) {
  const meta = STATUS_META[status] || { label: status, cls: "neutral" };
  return `<span class="badge ${meta.cls}">${esc(meta.label)}</span>`;
}

function node(tag, text, cls) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
}

/* 极简 Markdown 渲染：标题、列表、加粗、行内代码、表格、段落（先转义）。 */
export function renderMarkdown(text) {
  const lines = String(text ?? "").split(/\r?\n/);
  let html = "";
  let inList = null;
  let tableBuffer = [];

  const inline = (value) =>
    esc(value)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  const flushList = () => { if (inList) { html += `</${inList}>`; inList = null; } };
  const flushTable = () => {
    if (!tableBuffer.length) return;
    const rows = tableBuffer
      .map((line) => line.replace(/^\||\|$/g, "").split("|").map((c) => c.trim()))
      .filter((cells) => !cells.every((cell) => /^:?-+:?$/.test(cell)));
    if (rows.length) {
      html += "<table><thead><tr>" + rows[0].map((c) => `<th>${inline(c)}</th>`).join("") + "</tr></thead><tbody>";
      rows.slice(1).forEach((cells) => { html += "<tr>" + cells.map((c) => `<td>${inline(c)}</td>`).join("") + "</tr>"; });
      html += "</tbody></table>";
    }
    tableBuffer = [];
  };

  lines.forEach((line) => {
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) { flushList(); flushTable(); const lv = heading[1].length; html += `<h${lv}>${inline(heading[2])}</h${lv}>`; return; }
    if (/^\s*\|.*\|\s*$/.test(line)) { flushList(); tableBuffer.push(line); return; }
    flushTable();
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    const ordered = /^\s*\d+[.、]\s+(.*)$/.exec(line);
    if (bullet || ordered) {
      const tag = bullet ? "ul" : "ol";
      if (inList !== tag) { flushList(); html += `<${tag}>`; inList = tag; }
      html += `<li>${inline((bullet || ordered)[1])}</li>`;
      return;
    }
    flushList();
    if (line.trim()) html += `<p>${inline(line)}</p>`;
  });
  flushList(); flushTable();
  return html;
}

/* ---------- 概览 + 列表 ---------- */

async function renderOverview(main) {
  main.replaceChildren();
  main.append(node("p", "正在加载报告数据……", "live-status"));
  try {
    const [configs, running, pending, failed, list] = await Promise.all([
      API.get("/report/configs"),
      API.get("/report/list?page=1&page_size=1&status=running"),
      API.get("/report/list?page=1&page_size=1&status=pending"),
      API.get("/report/list?page=1&page_size=1&status=failed"),
      API.get("/report/list?page=1&page_size=" + PAGE_SIZE),
    ]);
    main.replaceChildren();
    main.insertAdjacentHTML("beforeend",
      `<div class="page-heading"><div><div class="eyebrow">INTELLIGENT REPORTS</div>` +
      `<h1>智能报告概览</h1><p>将已经计算的业务指标，整理为清晰可读的周期报告。</p></div></div>`);
    paintOverview(main, {
      total: list.total || 0,
      categories: Array.isArray(configs) ? configs.length : 0,
      running: running.total || 0,
      pending: pending.total || 0,
      failed: failed.total || 0,
      latest: (list.items && list.items[0] && list.items[0].generated_at) || null,
    });
    paintList(main, list);
  } catch (error) {
    main.replaceChildren();
    main.append(node("div", error.message, "live-error"));
  }
}

async function loadListInto(main, page) {
  const section = $("[data-report-list]", main);
  if (section) section.remove();
  try {
    const list = await API.get(`/report/list?page=${page}&page_size=${PAGE_SIZE}`);
    paintList(main, list);
  } catch (error) {
    main.append(node("div", error.message, "live-error"));
  }
}

export function paintOverview(main, overview) {
  const success = Math.max(0, overview.total - overview.running - overview.pending - overview.failed);
  const cards = [
    ["报告总数", overview.total, "份", "全部统计周期报告"],
    ["报告类别", overview.categories, "类", "客户 / 日报 / 周报 / 心理 / 投诉"],
    ["已生成", success, "份", "成功完成的报告"],
    ["生成中 / 待生成", overview.running + overview.pending, "项", "等待或正在生成"],
    ["失败", overview.failed, "份", "需关注的生成失败"],
    ["最近生成", fmtTime(overview.latest), "", "最近一份报告完成时间"],
  ];
  main.insertAdjacentHTML("beforeend",
    `<div class="stats-grid">${cards.map(([label, value, unit, note]) =>
      `<div class="stat-card"><div class="stat-label">${esc(label)}</div>` +
      `<div class="stat-value">${esc(String(value))}${unit ? `<small>${esc(unit)}</small>` : ""}</div>` +
      `<div class="stat-note">${esc(note)}</div></div>`).join("")}</div>`);

  const dist = [
    { label: "已生成", value: success },
    { label: "生成中", value: overview.running },
    { label: "待生成", value: overview.pending },
    { label: "失败", value: overview.failed },
  ].filter((d) => d.value > 0);
  if (dist.length) {
    main.insertAdjacentHTML("beforeend",
      `<section class="section-card"><div class="section-title"><div><h2>报告状态分布</h2></div></div>` +
      `<div class="section-body"><div class="chart-wrap" data-report-dist></div></div></section>`);
    Viz.hBars($("[data-report-dist]", main), {
      items: dist.map((d, i) => ({ label: d.label, value: d.value, color: seriesColor(i) })),
      title: "报告状态分布",
    });
  }
}

export function paintList(main, list) {
  const items = list.items || [];
  const rows = items.length
    ? items.map((item) =>
        `<tr><td class="mono">${esc(item.report_record_id)}</td>` +
        `<td><strong>${esc(item.report_name)}</strong></td>` +
        `<td>${esc(REPORT_CODE_NAMES[item.report_code] || item.report_code)}</td>` +
        `<td class="mono">${fmtTime(item.start_time)} ~ ${fmtTime(item.end_time)}</td>` +
        `<td>${statusBadge(item.status)}</td>` +
        `<td class="mono">${fmtTime(item.generated_at)}</td>` +
        `<td><button type="button" class="button secondary small" data-view="${esc(item.report_record_id)}">查看报告</button></td></tr>`)
        .join("")
    : `<tr><td colspan="7" class="empty-search">暂无授权可见的报告。</td></tr>`;

  const pages = Math.max(1, Math.ceil((list.total || 0) / (list.page_size || PAGE_SIZE)));
  const page = list.page || 1;
  main.insertAdjacentHTML("beforeend",
    `<section class="section-card" data-report-list><div class="section-title">` +
    `<div><h2>报告列表</h2></div>` +
    `<a class="button secondary small" href="generate.html">生成新报告</a></div>` +
    `<div class="section-body"><div class="table-wrap"><table class="data-table"><thead><tr>` +
    `<th scope="col">编号</th><th scope="col">报告名称</th><th scope="col">类别</th>` +
    `<th scope="col">统计范围</th><th scope="col">状态</th><th scope="col">生成时间</th><th scope="col">操作</th>` +
    `</tr></thead><tbody>${rows}</tbody></table></div>` +
    `<div class="pagination"><span>第 ${page} / ${pages} 页 · 共 ${list.total || 0} 条</span>` +
    `<div class="numbers"><button type="button" data-report-prev ${page <= 1 ? "disabled" : ""}>‹</button>` +
    `<button class="active" type="button">${page}</button>` +
    `<button type="button" data-report-next ${page >= pages ? "disabled" : ""}>›</button></div></div>` +
    `</div></section>`);

  $$("[data-view]", main).forEach((btn) => btn.addEventListener("click", () => {
    location.assign("detail.html?report_record_id=" + encodeURIComponent(btn.dataset.view));
  }));
  $("[data-report-prev]", main)?.addEventListener("click", () => loadListInto(main, page - 1));
  $("[data-report-next]", main)?.addEventListener("click", () => loadListInto(main, page + 1));
}

/* ---------- 详情 ---------- */

async function renderDetail(main, selected) {
  main.replaceChildren();
  const id = new URLSearchParams(location.search).get("report_record_id") || selected.report_record_id;
  const intro = node("p", "正在加载报告详情……", "live-status");
  main.append(intro);
  if (!id) {
    intro.textContent = "缺少报告编号，无法查看详情。";
    intro.className = "live-error";
    return;
  }
  try {
    const data = await API.get("/report/" + encodeURIComponent(id));
    main.replaceChildren();
    paintDetail(main, data, id);
  } catch (error) {
    main.replaceChildren();
    main.append(node("div", error.message, "live-error"));
  }
}

export function paintDetail(main, data, id) {
  main.insertAdjacentHTML("beforeend",
    `<div class="page-heading"><div><div class="eyebrow">REPORT DETAIL</div>` +
    `<h1>${esc(data.report_name || "报告详情")}</h1>` +
    `<p>${esc(REPORT_CODE_NAMES[data.report_code] || data.report_code || "")} · #${esc(id)}</p></div></div>`);

  const meta = [
    ["状态", statusBadge(data.status)],
    ["报告类型", esc(REPORT_CODE_NAMES[data.report_code] || data.report_code)],
    ["统计窗口", fmtTime(data.start_time) + " ~ " + fmtTime(data.end_time)],
    ["来源记录数", Viz.fmt(data.source_record_count)],
    ["指标快照", fmtTime(data.data_snapshot_at)],
    ["完成时间", fmtTime(data.generated_at)],
  ];
  main.insertAdjacentHTML("beforeend",
    `<section class="section-card"><div class="section-title"><div><h2>报告信息</h2></div></div>` +
    `<div class="section-body"><div class="live-result"><dl>` +
    meta.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join("") +
    `</dl></div></div></section>`);

  if (data.status === "failed" && data.fail_reason) {
    main.insertAdjacentHTML("beforeend",
      `<section class="section-card"><div class="section-title"><div><h2>未完成原因</h2></div></div>` +
      `<div class="section-body"><p class="live-error">${esc(data.fail_reason)}</p></div></section>`);
  }

  if (data.report_content) {
    main.insertAdjacentHTML("beforeend",
      `<section class="section-card"><div class="section-title"><div><h2>报告正文</h2></div></div>` +
      `<div class="section-body report-body">${renderMarkdown(data.report_content)}</div></section>`);
  }

  paintMetrics(main, data.metric_json || {});
}

function paintMetrics(main, entries) {
  const counts = [];
  const rates = [];
  const others = [];
  const unavailable = [];
  Object.entries(entries).forEach(([code, e]) => {
    const label = metricLabel(code);
    const available = e.availability === "available" && e.value != null;
    if (!available) unavailable.push({ label, note: e.reason || "" });
    else if (e.unit === "count") counts.push({ label, value: e.value });
    else if (e.unit === "rate") rates.push({ label, value: e.value });
    else others.push({ label, value: metricValue(e) });
  });

  if (counts.length) {
    main.insertAdjacentHTML("beforeend",
      `<section class="section-card"><div class="section-title"><div><h2>核心指标</h2></div></div>` +
      `<div class="section-body"><div class="chart-wrap" data-report-counts></div></div></section>`);
    Viz.hBars($("[data-report-counts]", main), {
      items: counts.map((c, i) => ({ label: c.label, value: c.value, color: seriesColor(i) })),
      title: "核心指标",
    });
  }

  if (rates.length) {
    main.insertAdjacentHTML("beforeend",
      `<section class="section-card"><div class="section-title"><div><h2>比例指标</h2></div></div>` +
      `<div class="section-body"><div class="chart-wrap" data-report-rates></div></div></section>`);
    Viz.hBars($("[data-report-rates]", main), {
      items: rates.map((r, i) => ({ label: r.label, value: r.value, color: seriesColor(i + 1) })),
      title: "比例指标（%）",
    });
  }

  if (others.length) {
    main.insertAdjacentHTML("beforeend",
      `<section class="section-card"><div class="section-title"><div><h2>其他指标</h2></div></div>` +
      `<div class="section-body"><div class="stats-grid">${others.map((o) =>
        `<div class="stat-card"><div class="stat-label">${esc(o.label)}</div>` +
        `<div class="stat-value stat-value--sm">${esc(o.value)}</div></div>`).join("")}</div></div></section>`);
  }

  if (unavailable.length) {
    main.insertAdjacentHTML("beforeend",
      `<section class="section-card"><div class="section-title"><div><h2>不可用指标</h2></div></div>` +
      `<div class="section-body"><div class="stats-grid">${unavailable.map((o) =>
        `<div class="stat-card"><div class="stat-label">${esc(o.label)}</div>` +
        `<div class="stat-value stat-value--sm">—</div>` +
        `<div class="stat-note">${esc(o.note || "当前不可用")}</div></div>`).join("")}</div></div></section>`);
  }

  if (!counts.length && !rates.length && !others.length && !unavailable.length) {
    main.insertAdjacentHTML("beforeend",
      `<section class="section-card"><div class="section-body"><p class="muted">暂无指标数据。</p></div></section>`);
  }
}

/* ---------- 入口 ---------- */

export async function mountReportWorkspace({ main, page, access, selected = {} }) {
  if (page === "report/detail.html") return renderDetail(main, selected);
  return renderOverview(main);
}
