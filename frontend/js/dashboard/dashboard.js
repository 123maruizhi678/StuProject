import { API } from "../common/module-api.js";
import { $, $$, esc, toast, riskBadge, statusBadge, studentSelect } from "../common/ui.js";
import { Viz } from "../common/charts.js";

  export async function render(root) {
    root.innerHTML = `<div class="empty"><span class="spin"></span> 加载中…</div>`;
    let data;
    try { data = await API.get("/dashboard/overview"); } catch (e) { root.innerHTML = `<div class="card"><div class="empty">${esc(e.message)}</div></div>`; return; }

    const c = data.cards || [];
    const kpiIcons = { customers: "👤", tickets: "🎫", warnings: "⚠️", leave: "📝", events: "📅", students: "🎓" };
    let html = `<div class="kpi-grid">`;
    c.forEach((k) => {
      html += `<div class="kpi"><div class="label">${kpiIcons[k.key] || "•"} ${esc(k.label)}</div>
        <div class="value">${Viz.fmt(k.value)}</div>
        <div class="delta">${esc(k.delta || "")}</div></div>`;
    });
    html += `</div>`;

    // 客户增长趋势 + 状态分布
    const growth = data.growth || [];
    const statusDist = data.status_dist || {};
    const ticketDist = data.ticket_dist || {};

    html += `<div class="grid cols-2 mt-16">
      <div class="card"><h3>近 7 天意向客户增长</h3><p class="desc">每日新增意向客户数量趋势</p>
        <div id="chartGrowth" class="chart-wrap"></div></div>
      <div class="card"><h3>客户状态分布</h3><p class="desc">意向 / 成交 / 流失客群占比</p>
        <div id="chartStatus" class="chart-wrap"></div></div>
    </div>
    <div class="card mt-16"><h3>售后工单状态分布</h3><p class="desc">投诉与建议工单的处理进度</p>
      <div id="chartTicket" class="chart-wrap"></div></div>`;

    root.innerHTML = html;

    Viz.lineArea($("#chartGrowth"), {
      labels: growth.map((g) => g.date.slice(5)),
      values: growth.map((g) => g.count),
      color: Viz.cssVar("--s1"), title: "意向客户增长趋势",
    });
    const catColors = [Viz.cssVar("--s1"), Viz.cssVar("--s3"), Viz.cssVar("--s2")];
    Viz.hBars($("#chartStatus"), {
      items: Object.entries(statusDist).map(([k, v], i) => ({ label: k, value: v, color: catColors[i % 3] })),
      title: "客户状态分布",
    });
    const ticketColors = [Viz.cssVar("--s3"), Viz.cssVar("--s4"), Viz.cssVar("--s2")];
    Viz.hBars($("#chartTicket"), {
      items: Object.entries(ticketDist).map(([k, v], i) => ({ label: k, value: v, color: ticketColors[i % 3] })),
      title: "工单状态分布",
    });
  }
