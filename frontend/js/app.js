/* 粤教服务智能业务平台 —— 前端单页应用 */
(function () {
  "use strict";

  /* ---------- 工具 ---------- */
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const STUDENTS = [
    { id: 1, name: "张三" }, { id: 2, name: "李四" }, { id: 3, name: "王五" },
    { id: 4, name: "赵六" }, { id: 5, name: "孙七" },
  ];

  function toast(msg, type = "") {
    const w = $("#toasts");
    const t = document.createElement("div");
    t.className = "toast " + type;
    t.textContent = msg;
    w.appendChild(t);
    setTimeout(() => t.remove(), 3600);
  }

  /* ---------- 主题 ---------- */
  function syncThemeIcon() {
    $("#themeBtn").textContent = document.documentElement.dataset.theme === "dark" ? "🌙" : "☀️";
  }
  function initTheme() {
    const saved = localStorage.getItem("yuejiao-theme") || "dark";
    document.documentElement.dataset.theme = saved;
    syncThemeIcon();
    $("#themeBtn").addEventListener("click", () => {
      const cur = document.documentElement.dataset.theme;
      const next = cur === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      localStorage.setItem("yuejiao-theme", next);
      syncThemeIcon();
      render(); // 图表颜色随主题重绘
    });
  }

  /* ---------- 路由 ---------- */
  const PAGES = {
    dashboard: { title: "数据看板", subtitle: "业务全景 · 一屏掌握核心经营指标", render: pageDashboard },
    judge: { title: "客户研判", subtitle: "多格式解析 · AI 画像研判", render: pageJudge },
    agent: { title: "客服 Agent", subtitle: "意图路由 · RAG 知识问答", render: pageAgent },
    enterprise: { title: "企业智能助手", subtitle: "客户 · 日报 · NL2SQL · 指令", render: pageEnterprise },
    student: { title: "学生智能助手", subtitle: "请假 · 心理关怀 · 售后 · 学业", render: pageStudent },
    report: { title: "智能报告", subtitle: "AI 聚合数据 · 一键生成", render: pageReport },
  };

  function currentRoute() {
    const h = location.hash.replace(/^#\/?/, "") || "dashboard";
    return PAGES[h] ? h : "dashboard";
  }

  function render() {
    const route = currentRoute();
    const page = PAGES[route];
    $$(".nav-item").forEach((n) => n.classList.toggle("active", n.dataset.route === route));
    $("#pageTitle").textContent = "粤教服务 · " + page.title;
    const app = $("#app");
    app.innerHTML = "";

    // 页面编辑式标题区（编号 + 大字标题 + 副标题 + 装饰线）
    const hero = document.createElement("header");
    hero.className = "page-hero";
    const idx = String(Object.keys(PAGES).indexOf(route) + 1).padStart(2, "0");
    hero.innerHTML = `
      <div class="hero-index">${idx}</div>
      <div class="hero-main">
        <h1 class="hero-title">${esc(page.title)}</h1>
        ${page.subtitle ? `<p class="hero-sub">${esc(page.subtitle)}</p>` : ""}
      </div>
      <div class="hero-mark" aria-hidden="true"></div>`;
    app.appendChild(hero);

    const body = document.createElement("div");
    body.className = "page-body";
    app.appendChild(body);
    try {
      page.render(body);
    } catch (e) {
      body.innerHTML = `<div class="card"><div class="empty">页面渲染失败：${esc(e.message)}</div></div>`;
    }
  }

  /* ---------- 简单 Markdown 渲染（报告用） ---------- */
  function md(src) {
    return String(src || "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .split("\n").map((line) => {
        if (/^# /.test(line)) return `<h1>${line.slice(2)}</h1>`;
        if (/^## /.test(line)) return `<h2>${line.slice(3)}</h2>`;
        if (/^### /.test(line)) return `<h3>${line.slice(4)}</h3>`;
        if (/^> /.test(line)) return `<blockquote>${line.slice(2)}</blockquote>`;
        if (/^- /.test(line)) return `<li>${line.slice(2)}</li>`;
        if (line.trim() === "") return "";
        return `<p>${line}</p>`;
      }).join("");
  }

  const riskBadge = (r) => {
    const m = { high: "critical", medium: "serious", low: "good" };
    const t = { high: "高危", medium: "中危", low: "低危" };
    return `<span class="badge ${m[r] || "neutral"}">${t[r] || r || "-"}</span>`;
  };
  const statusBadge = (s) => {
    const good = ["已签约", "已解决", "已同意", "已完成"];
    const bad = ["已流失", "已拒绝"];
    const warn = ["待处理", "待审批", "处理中", "待跟进", "意向中", "审核中"];
    if (good.includes(s)) return `<span class="badge good">${esc(s)}</span>`;
    if (bad.includes(s)) return `<span class="badge critical">${esc(s)}</span>`;
    if (warn.includes(s)) return `<span class="badge warning">${esc(s)}</span>`;
    return `<span class="badge neutral">${esc(s)}</span>`;
  };

  /* ============================================================
     数据看板
     ============================================================ */
  async function pageDashboard(root) {
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

  /* ============================================================
     客户研判
     ============================================================ */
  async function pageJudge(root) {
    root.innerHTML = `
      <div class="grid cols-2">
        <div class="card">
          <h3>提交客户信息研判</h3>
          <p class="desc">支持文本、PDF 简历、Excel 表格，系统解析字段后按画像规则研判（两个产品）</p>
          <div class="field"><label>来源类型</label>
            <select class="input" id="jType">
              <option value="text">文本</option>
              <option value="pdf">PDF 简历</option>
              <option value="excel">Excel 表格</option>
            </select></div>
          <div class="field"><label>文本内容（文本来源时填写）</label>
            <textarea class="input" id="jText" placeholder="例如：姓名：张三，本科，意向美国留学，电话13800000000"></textarea></div>
          <div class="field"><label>上传文件（PDF / Excel）</label>
            <input type="file" class="input" id="jFile" accept=".txt,.md,.pdf,.xlsx,.xls,.csv"></div>
          <button class="btn primary" id="jSubmit">开始研判</button>
          <div id="jResult" class="mt-16"></div>
        </div>
        <div class="card">
          <h3>画像研判规则</h3><p class="desc">甲方《用户画像研判规则》结构化的两个产品画像</p>
          <div id="jRules"><span class="spin"></span></div>
        </div>
      </div>
      <div class="card mt-16"><h3>研判记录</h3><div id="jRecords"><span class="spin"></span></div></div>`;

    const loadRules = async () => {
      try {
        const rules = await API.get("/customer/rules");
        $("#jRules").innerHTML = rules.map((r) => {
          const conds = (r.rule_content && r.rule_content.conditions) || [];
          return `<div class="card" style="box-shadow:none;border-color:var(--border);margin-top:12px">
            <div><b>${esc(r.product_name)}</b> <span class="badge neutral">${esc(r.product_code)}</span> <span class="muted small">${esc(r.version)}</span></div>
            <ul style="padding-left:20px;margin:8px 0 0">
              ${conds.map((c) => `<li class="small">${esc(c.label)}</li>`).join("")}
            </ul></div>`;
        }).join("") || `<div class="empty">暂无规则</div>`;
      } catch (e) { $("#jRules").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
    };
    const loadRecords = async () => {
      try {
        const recs = await API.get("/customer/records");
        $("#jRecords").innerHTML = recs.length ? `<table class="tbl"><thead><tr>
          <th>ID</th><th>来源</th><th>姓名</th><th>学历</th><th>意向国家</th><th>研判结果</th><th>时间</th></tr></thead><tbody>
          ${recs.map((r) => `<tr>
            <td>${r.customer_info_id}</td><td>${esc(r.source_type)}</td>
            <td>${esc((r.parsed_fields || {}).name || "-")}</td>
            <td>${esc((r.parsed_fields || {}).education || "-")}</td>
            <td>${esc((r.parsed_fields || {}).target_country || "-")}</td>
            <td>${(r.judgements || []).map((j) => `<span class="badge ${j.is_match ? "good" : "neutral"}">${esc(j.product_name)}${j.is_match ? "✓" : "✗"}</span>`).join(" ")}</td>
            <td class="small">${esc(r.created_at)}</td></tr>`).join("")}</tbody></table>` : `<div class="empty">暂无研判记录</div>`;
      } catch (e) { $("#jRecords").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
    };
    loadRules(); loadRecords();

    $("#jSubmit").addEventListener("click", async () => {
      const btn = $("#jSubmit"); btn.disabled = true; btn.textContent = "研判中…";
      try {
        const type = $("#jType").value;
        const text = $("#jText").value.trim();
        const file = $("#jFile").files[0];
        let res;
        if (file) {
          const fd = new FormData();
          fd.append("source_type", type);
          fd.append("file", file);
          if (text) fd.append("source_content", text);
          res = await API.upload("/customer/judge", fd);
        } else {
          if (!text) { toast("请填写文本内容或上传文件", "err"); return; }
          res = await API.post("/customer/judge", { source_type: type, source_content: text });
        }
        const pf = res.parsed_fields || {};
        $("#jResult").innerHTML = `
          <div class="small muted mb-8">已解析字段：${["name", "phone", "email", "education", "target_country", "target_school"]
            .map((k) => pf[k] ? `<b>${esc(k)}</b>=${esc(pf[k])}` : "").filter(Boolean).join(" · ") || "（未识别到关键字段）"}</div>
          ${res.judgements.map((j) => `<div class="card" style="box-shadow:none;margin-top:10px;border-left:3px solid ${j.is_match ? "var(--s3)" : "var(--s2)"}">
            <div><b>${esc(j.product_name)}</b> ${j.is_match ? `<span class="badge good">符合画像</span>` : `<span class="badge neutral">暂不符合</span>`}
              <span class="badge blue">匹配度 ${esc(j.match_level)}</span></div>
            <div class="small mt-8">${esc(j.judgement_reason)}</div>
            <details class="small mt-8"><summary>命中明细</summary>
              <div class="mono" style="margin-top:6px">${esc(JSON.stringify(j.evidence, null, 2))}</div></details>
          </div>`).join("")}`;
        toast("研判完成");
        loadRecords();
      } catch (e) { toast(e.message, "err"); $("#jResult").innerHTML = `<div class="small" style="color:var(--critical)">${esc(e.message)}</div>`; }
      finally { btn.disabled = false; btn.textContent = "开始研判"; }
    });
  }

  /* ============================================================
     客服 Agent
     ============================================================ */
  async function pageAgent(root) {
    root.innerHTML = `
      <div class="grid" style="grid-template-columns: 1.5fr 1fr">
        <div class="card" style="padding:0">
          <div class="chat-box" style="border:none;height:560px">
            <div class="chat-msgs" id="aMsgs">
              <div class="msg bot">哈喽～我是「粤小助」🙋 留学申请、语言培训、留学政策、活动报名都可以问我哦！</div>
            </div>
            <div class="quick-chips" id="aChips"></div>
            <div class="chat-input">
              <textarea class="input" id="aInput" placeholder="输入你的问题…"></textarea>
              <button class="btn primary" id="aSend">发送</button>
            </div>
          </div>
        </div>
        <div>
          <div class="card"><h3>近期活动</h3><div id="aEvents"><span class="spin"></span></div></div>
          <div class="card"><h3>课程项目</h3><div id="aCourses"><span class="spin"></span></div></div>
        </div>
      </div>`;

    const chips = ["你们公司有哪些留学项目？", "英国留学政策是怎样的？", "雅思7分冲刺班推荐", "近期有什么活动？", "留学申请流程是什么？", "服务费用大概多少？"];
    $("#aChips").innerHTML = chips.map((c) => `<button class="chip">${esc(c)}</button>`).join("");
    $$("#aChips .chip").forEach((ch) => ch.addEventListener("click", () => { $("#aInput").value = ch.textContent; send(); }));

    const addMsg = (text, who, tag) => {
      const box = $("#aMsgs");
      const m = document.createElement("div");
      m.className = "msg " + who;
      m.textContent = text;
      if (tag) { const t = document.createElement("div"); t.className = "tag"; t.textContent = tag; m.prepend(t); }
      box.appendChild(m);
      box.scrollTop = box.scrollHeight;
      return m;
    };

    async function send() {
      const input = $("#aInput");
      const text = input.value.trim();
      if (!text) return;
      addMsg(text, "user");
      input.value = "";
      const pending = addMsg("思考中…", "bot");
      try {
        const res = await API.post("/agent/chat", { user_id: "guest", message: text });
        const tagMap = { company_info: "公司信息", business_query: "业务查询", policy_query: "政策查询",
          course_recommend: "课程推荐", event_signup: "活动报名", faq: "常见问题", chitchat: "闲聊" };
        pending.remove();
        addMsg(res.reply || "（无回复）", "bot", tagMap[res.intent] || res.intent);
        if (res.events && res.events.length) renderEvents(res.events);
        if (res.recommendations && res.recommendations.length) renderCourses(res.recommendations);
      } catch (e) { pending.remove(); addMsg("出错了：" + e.message, "bot"); }
    }
    $("#aSend").addEventListener("click", send);
    $("#aInput").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } });

    async function renderEvents(override) {
      try {
        const events = override || await API.get("/agent/events");
        $("#aEvents").innerHTML = events.length ? events.map((ev) => `
          <div class="card" style="box-shadow:none;border-color:var(--border);margin-top:10px">
            <div><b>${esc(ev.event_name)}</b></div>
            <div class="small muted">🕒 ${esc(ev.time)} · 📍 ${esc(ev.location)} · 名额 ${ev.capacity}</div>
            <button class="btn sm primary mt-12" data-signup="${ev.event_id}">在线报名</button>
          </div>`).join("") : `<div class="empty">暂无活动</div>`;
        $$("#aEvents [data-signup]").forEach((b) => b.addEventListener("click", () => signup(b.dataset.signup, b)));
      } catch (e) { $("#aEvents").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
    }
    async function renderCourses(override) {
      try {
        const courses = override || await API.get("/agent/courses");
        $("#aCourses").innerHTML = courses.length ? courses.map((c) => `
          <div class="card" style="box-shadow:none;border-color:var(--border);margin-top:10px">
            <div><b>${esc(c.course_name)}</b> <span class="badge blue">${esc(c.category)}</span></div>
            <div class="small muted">${esc(c.target_audience || "")} · ${esc(c.target_country || "")}</div>
            <div class="small">${esc(c.description || "")}</div>
          </div>`).join("") : `<div class="empty">暂无课程</div>`;
      } catch (e) { $("#aCourses").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
    }
    async function signup(eventId, btn) {
      const name = prompt("请输入您的姓名：");
      if (!name) return;
      const phone = prompt("请输入您的手机号：");
      if (!phone) return;
      btn.disabled = true;
      try {
        const res = await API.post("/agent/events/signup", { event_id: Number(eventId), customer_info: { name, phone } });
        toast(`报名成功：${res.event_name}`);
        addMsg(`已为您完成「${res.event_name}」报名 ✅（${name}）`, "bot", "活动报名");
      } catch (e) { toast(e.message, "err"); }
      finally { btn.disabled = false; }
    }
    renderEvents(); renderCourses();
  }

  /* ============================================================
     企业智能助手
     ============================================================ */
  function pageEnterprise(root) {
    const tabs = ["意向客户", "日报", "NL2SQL", "指令处理", "组织架构", "新人指引", "学生成绩", "投诉"];
    root.innerHTML = `<div class="card"><div class="tabs" id="eTabs">
      ${tabs.map((t, i) => `<button class="tab ${i === 0 ? "active" : ""}" data-tab="${i}">${t}</button>`).join("")}
    </div><div id="eBody"></div></div>`;
    const body = $("#eBody");
    const renderers = [tCustomers, tDaily, tNl2sql, tCommand, tOrg, tOnboarding, tScore, tComplaints];
    const show = (i) => {
      $$("#eTabs .tab").forEach((t) => t.classList.toggle("active", Number(t.dataset.tab) === i));
      body.innerHTML = `<span class="spin"></span>`;
      renderers[i](body);
    };
    $$("#eTabs .tab").forEach((t) => t.addEventListener("click", () => show(Number(t.dataset.tab))));
    show(0);
  }

  async function tCustomers(root) {
    root.innerHTML = `
      <div class="grid cols-2">
        <div class="card" style="box-shadow:none">
          <h3>录入意向客户</h3><p class="desc">支持文字/口述整段录入，AI 自动解析结构化</p>
          <div class="field"><label>姓名</label><input class="input" id="cName"></div>
          <div class="field"><label>电话</label><input class="input" id="cPhone"></div>
          <div class="grid cols-2">
            <div class="field"><label>学历</label><input class="input" id="cEdu"></div>
            <div class="field"><label>意向国家</label><input class="input" id="cCountry"></div>
          </div>
          <div class="field"><label>跟进记录（可选）</label><input class="input" id="cFollow"></div>
          <div class="field"><label>或口述整段录入（AI 解析）</label><textarea class="input" id="cVoice" placeholder="例如：新客户周杰，本科，电话139...，意向英国留学"></textarea></div>
          <button class="btn primary" id="cSubmit">录入</button>
        </div>
        <div class="card" style="box-shadow:none"><h3>意向客户列表</h3>
          <div class="field mt-12"><input class="input" id="cSearch" placeholder="按姓名搜索…"></div>
          <div id="cList"></div></div>
      </div>`;

    const load = async (kw) => {
      try {
        const list = await API.get("/enterprise/customers" + (kw ? `?keyword=${encodeURIComponent(kw)}` : ""));
        $("#cList").innerHTML = list.length ? `<table class="tbl"><thead><tr><th>ID</th><th>姓名</th><th>电话</th><th>学历</th><th>意向国家</th><th>状态</th><th>操作</th></tr></thead><tbody>
          ${list.map((c) => `<tr><td>${c.customer_id}</td><td>${esc(c.name)}</td><td>${esc(c.phone || "-")}</td>
            <td>${esc(c.education || "-")}</td><td>${esc(c.target_country || "-")}</td>
            <td>${statusBadge(c.status)}</td>
            <td><button class="btn sm" data-view="${c.customer_id}">详情</button></td></tr>`).join("")}</tbody></table>`
          : `<div class="empty">暂无客户</div>`;
        $$("#cList [data-view]").forEach((b) => b.addEventListener("click", () => viewCustomer(b.dataset.view)));
      } catch (e) { $("#cList").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
    };
    async function viewCustomer(id) {
      try {
        const c = await API.get(`/enterprise/customer/${id}`);
        const fr = (c.follow_records || []).map((f) => `<li class="small">${esc(f.follow_time)} — ${esc(f.content)}</li>`).join("");
        const html = `<div style="position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:100;display:grid;place-items:center" id="modal">
          <div class="card" style="width:480px;max-width:92vw;max-height:84vh;overflow:auto">
            <h3>${esc(c.name)} 的客户档案</h3>
            <div class="small muted mb-8">电话：${esc(c.phone || "-")} · 学历：${esc(c.education || "-")} · 意向国家：${esc(c.target_country || "-")}</div>
            <div class="mb-8">状态：${statusBadge(c.status)}
              <button class="btn sm" data-st="${c.customer_id}:已签约">改签约</button>
              <button class="btn sm" data-st="${c.customer_id}:已流失">改流失</button></div>
            <div><b class="small">跟进记录</b><ul style="padding-left:18px">${fr || "<li class='small muted'>暂无</li>"}</ul></div>
            <div class="field mt-12"><label>新增跟进</label><input class="input" id="mFollow" placeholder="输入跟进内容"></div>
            <button class="btn primary sm" id="mAddFollow">保存跟进</button>
            <button class="btn sm" style="margin-left:8px" id="mClose">关闭</button>
          </div></div>`;
        document.body.insertAdjacentHTML("beforeend", html);
        $("#mClose").addEventListener("click", () => $("#modal").remove());
        $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") $("#modal").remove(); });
        $("#mAddFollow").addEventListener("click", async () => {
          const content = $("#mFollow").value.trim(); if (!content) return;
          try { await API.post(`/enterprise/customer/${id}/follow`, { content }); toast("已保存跟进"); viewCustomer(id); $("#modal").remove(); load(); }
          catch (e) { toast(e.message, "err"); }
        });
        $$("#modal [data-st]").forEach((b) => b.addEventListener("click", async () => {
          const [cid, st] = b.dataset.st.split(":");
          try { await API.put(`/enterprise/customer/${cid}/status`, { status: st }); toast("状态已更新"); $("#modal").remove(); load(); }
          catch (e) { toast(e.message, "err"); }
        }));
      } catch (e) { toast(e.message, "err"); }
    }
    $("#cSubmit").addEventListener("click", async () => {
      const name = $("#cName").value.trim();
      const voice = $("#cVoice").value.trim();
      if (!name && !voice) { toast("请填写姓名或口述内容", "err"); return; }
      const info = { name, phone: $("#cPhone").value.trim(), education: $("#cEdu").value.trim(), target_country: $("#cCountry").value.trim() };
      try {
        await API.post("/enterprise/customer", { customer_info: info, follow_records: $("#cFollow").value.trim() || undefined, source_text: voice || undefined });
        toast("客户录入成功");
        ["cName", "cPhone", "cEdu", "cCountry", "cFollow", "cVoice"].forEach((id) => $("#" + id).value = "");
        load();
      } catch (e) { toast(e.message, "err"); }
    });
    $("#cSearch").addEventListener("input", (e) => load(e.target.value));
    load();
  }

  async function tDaily(root) {
    root.innerHTML = `
      <div class="grid cols-2">
        <div class="card" style="box-shadow:none"><h3>口述日报</h3><p class="desc">AI 自动识别核心进展并结构化</p>
          <div class="field"><label>员工姓名</label><input class="input" id="dName" value="赵磊"></div>
          <div class="field"><label>部门</label><input class="input" id="dDept" value="销售部"></div>
          <div class="field"><label>日报内容</label><textarea class="input" id="dContent" placeholder="今天跟进了三个客户…"></textarea></div>
          <button class="btn primary" id="dSubmit">提交日报</button></div>
        <div class="card" style="box-shadow:none"><h3>日报列表</h3><div id="dList"></div></div>
      </div>`;
    const load = async () => {
      try {
        const list = await API.get("/enterprise/daily-report");
        $("#dList").innerHTML = list.length ? list.map((r) => `
          <div class="card" style="box-shadow:none;border-color:var(--border);margin-top:10px">
            <div><b>${esc(r.employee_name)}</b> <span class="badge neutral">${esc(r.department)}</span></div>
            <div class="small">${esc(r.content)}</div>
            ${r.structured ? `<div class="small muted mt-8">📌 进展：${esc(r.structured.core_progress || "")} ${r.structured.risk ? "· ⚠️ 风险：" + esc(r.structured.risk) : ""}</div>` : ""}
            <div class="small muted">${esc(r.submit_time)}</div></div>`).join("") : `<div class="empty">暂无日报</div>`;
      } catch (e) { $("#dList").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
    };
    $("#dSubmit").addEventListener("click", async () => {
      const content = $("#dContent").value.trim();
      if (!content) { toast("请输入日报内容", "err"); return; }
      try {
        const res = await API.post("/enterprise/daily-report", { employee_name: $("#dName").value, department: $("#dDept").value, voice_content: content });
        toast("日报已提交并结构化");
        $("#dContent").value = "";
        load();
      } catch (e) { toast(e.message, "err"); }
    });
    load();
  }

  async function tNl2sql(root) {
    root.innerHTML = `
      <div class="card" style="box-shadow:none"><h3>自然语言查数（NL2SQL）</h3>
        <p class="desc">只读安全查询，示例：查张三的跟进记录 / 查待处理投诉 / 查张三的成绩 / 查销售部日报</p>
        <div class="field"><textarea class="input" id="nQuery" placeholder="帮我查一下张三的最近跟进记录"></textarea></div>
        <button class="btn primary" id="nSubmit">查询</button>
        <div id="nResult" class="mt-16"></div></div>`;
    $("#nSubmit").addEventListener("click", async () => {
      const q = $("#nQuery").value.trim();
      if (!q) { toast("请输入查询内容", "err"); return; }
      try {
        const res = await API.post("/enterprise/nl2sql", { query: q });
        const rows = res.result || [];
        const cols = rows.length ? Object.keys(rows[0]) : [];
        $("#nResult").innerHTML = `
          <div class="mono mb-8">${esc(res.sql || "")}</div>
          <div class="small muted mb-8">${esc(res.summary || "")}</div>
          ${rows.length ? `<table class="tbl"><thead><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>
            ${rows.map((r) => `<tr>${cols.map((c) => `<td>${esc(r[c])}</td>`).join("")}</tr>`).join("")}</tbody></table>`
            : `<div class="empty">未查询到数据</div>`}`;
      } catch (e) { $("#nResult").innerHTML = `<div style="color:var(--critical)">${esc(e.message)}</div>`; }
    });
  }

  async function tCommand(root) {
    root.innerHTML = `
      <div class="grid cols-2">
        <div class="card" style="box-shadow:none"><h3>指令式业务处理</h3>
          <p class="desc">示例：同意张三同学的请假申请 / 把李四同学的投诉状态更新为【已解决】/ 把王五客户状态更新为【已签约】</p>
          <div class="field"><textarea class="input" id="cmdInput" placeholder="输入自然语言指令…"></textarea></div>
          <button class="btn primary" id="cmdSubmit">执行</button>
          <div id="cmdResult" class="mt-16"></div></div>
        <div class="card" style="box-shadow:none"><h3>主动待办推送</h3><div id="todoBox"></div></div>
      </div>`;
    const loadTodos = async () => {
      try {
        const t = await API.get("/enterprise/todos");
        $("#todoBox").innerHTML = `
          <div class="kpi"><div class="label">📝 待审批请假</div><div class="value">${t.pending_leave}</div></div>
          <div class="kpi mt-12"><div class="label">🎫 待跟进投诉</div><div class="value">${t.pending_complaint}</div></div>
          <div class="hint">${esc(t.message)}</div>`;
      } catch (e) { $("#todoBox").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
    };
    $("#cmdSubmit").addEventListener("click", async () => {
      const c = $("#cmdInput").value.trim();
      if (!c) { toast("请输入指令", "err"); return; }
      try {
        const res = await API.post("/enterprise/command", { command: c });
        $("#cmdResult").innerHTML = `<div class="card" style="box-shadow:none;border-left:3px solid ${res.status === "success" ? "var(--s3)" : "var(--s2)"}">
          <div><b>${esc(res.message || "执行完成")}</b></div>
          ${res.affected != null ? `<div class="small muted">影响 ${res.affected} 条记录</div>` : ""}
          ${res.hint ? `<div class="hint">${esc(res.hint)}</div>` : ""}</div>`;
        toast(res.status === "success" ? "执行成功" : "执行提示", res.status === "success" ? "ok" : "");
        loadTodos();
      } catch (e) { $("#cmdResult").innerHTML = `<div style="color:var(--critical)">${esc(e.message)}</div>`; }
    });
    loadTodos();
  }

  async function tOrg(root) {
    try {
      const org = await API.get("/enterprise/org");
      root.innerHTML = org.map((d) => `
        <div class="org-dept"><div class="dept-head"><span class="dept-name">${esc(d.department)}</span>
          <span class="dept-fn">${esc(d.function || "")} · 负责人 ${esc(d.leader || "-")}</span></div>
          <div class="org-members">${d.employees.map((e) => `<div class="member-chip"><b>${esc(e.name)}</b><span>${esc(e.position || "")} · ${esc(e.phone || "")}</span></div>`).join("")}</div></div>`).join("")
        || `<div class="empty">暂无组织架构数据</div>`;
    } catch (e) { root.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
  }

  async function tOnboarding(root) {
    try {
      const list = await API.get("/enterprise/onboarding");
      root.innerHTML = list.map((k) => `
        <div class="card" style="box-shadow:none;border-color:var(--border);margin-top:10px">
          <div><b>❓ ${esc(k.question)}</b> <span class="badge neutral">${esc(k.category)}</span></div>
          <div class="small mt-8">${esc(k.answer)}</div></div>`).join("") || `<div class="empty">暂无新人指引</div>`;
    } catch (e) { root.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
  }

  async function tScore(root) {
    root.innerHTML = `
      <div class="grid cols-2">
        <div class="card" style="box-shadow:none"><h3>录入学生成绩</h3>
          <div class="field"><label>学生</label><select class="input" id="sStu">${STUDENTS.map((s) => `<option value="${s.id}">${s.name}</option>`).join("")}</select></div>
          <div class="field"><label>科目</label><input class="input" id="sSubject" placeholder="雅思 / 托福 / GRE …"></div>
          <div class="field"><label>成绩</label><input class="input" id="sScore" type="number" step="0.5"></div>
          <button class="btn primary" id="sSubmit">录入</button></div>
        <div class="card" style="box-shadow:none"><h3>成绩列表</h3><div id="sList"></div></div>
      </div>`;
    const load = async () => {
      try {
        const list = await API.get("/enterprise/scores");
        $("#sList").innerHTML = list.length ? `<table class="tbl"><thead><tr><th>学生</th><th>科目</th><th>成绩</th></tr></thead><tbody>
          ${list.map((s) => `<tr><td>${esc(s.student_name)}</td><td>${esc(s.subject)}</td><td>${esc(s.score)}</td></tr>`).join("")}</tbody></table>`
          : `<div class="empty">暂无成绩</div>`;
      } catch (e) { $("#sList").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
    };
    $("#sSubmit").addEventListener("click", async () => {
      const sid = Number($("#sStu").value);
      const stu = STUDENTS.find((s) => s.id === sid);
      try {
        await API.post("/enterprise/score", { student_id: sid, student_name: stu.name, subject: $("#sSubject").value.trim(), score: Number($("#sScore").value) });
        toast("成绩已录入"); $("#sSubject").value = ""; $("#sScore").value = ""; load();
      } catch (e) { toast(e.message, "err"); }
    });
    load();
  }

  async function tComplaints(root) {
    try {
      const list = await API.get("/enterprise/complaints");
      root.innerHTML = list.length ? `<table class="tbl"><thead><tr><th>ID</th><th>学生</th><th>摘要</th><th>分类</th><th>状态</th><th>跟进人</th></tr></thead><tbody>
        ${list.map((c) => `<tr><td>${c.id}</td><td>${esc(c.student_name)}</td><td>${esc(c.summary || c.complaint_detail)}</td>
          <td>${esc(c.category || "-")}</td><td>${statusBadge(c.status)}</td><td>${esc(c.follower || "-")}</td></tr>`).join("")}</tbody></table>`
        : `<div class="empty">暂无投诉</div>`;
    } catch (e) { root.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
  }

  /* ============================================================
     学生智能助手
     ============================================================ */
  function pageStudent(root) {
    const tabs = ["请假", "心理关怀", "售后反馈", "学业考务", "进度追踪", "生活支持", "增值转化"];
    root.innerHTML = `<div class="card"><div class="tabs" id="sTabs">
      ${tabs.map((t, i) => `<button class="tab ${i === 0 ? "active" : ""}" data-tab="${i}">${t}</button>`).join("")}
    </div><div id="sBody"></div></div>`;
    const body = $("#sBody");
    const renderers = [tLeave, tMental, tFeedback, tAcademic, tProgress, tLife, tMarketing];
    const show = (i) => { $$("#sTabs .tab").forEach((t) => t.classList.toggle("active", Number(t.dataset.tab) === i)); body.innerHTML = `<span class="spin"></span>`; renderers[i](body); };
    $$("#sTabs .tab").forEach((t) => t.addEventListener("click", () => show(Number(t.dataset.tab))));
    show(0);
  }

  function studentSelect(id) {
    return `<select class="input" id="${id}">${STUDENTS.map((s) => `<option value="${s.id}">${s.name}</option>`).join("")}</select>`;
  }

  async function tLeave(root) {
    root.innerHTML = `
      <div class="grid cols-2">
        <div class="card" style="box-shadow:none"><h3>提交请假申请</h3><p class="desc">提交后自动推送班主任审批</p>
          <div class="field"><label>学生</label>${studentSelect("lStu")}</div>
          <div class="field"><label>请假内容</label><textarea class="input" id="lContent" placeholder="因病请假一天"></textarea></div>
          <button class="btn primary" id="lSubmit">提交申请</button></div>
        <div class="card" style="box-shadow:none"><h3>请假记录</h3><div id="lList"></div></div>
      </div>`;
    const load = async () => {
      try {
        const list = await API.get("/student/leave");
        $("#lList").innerHTML = list.length ? list.map((a) => `
          <div class="card" style="box-shadow:none;border-color:var(--border);margin-top:10px">
            <div><b>${esc(a.student_name)}</b> ${statusBadge(a.approval_status)} <span class="badge neutral">${esc(a.apply_type)}</span></div>
            <div class="small">${esc(a.apply_content)}</div>
            <div class="small muted">${esc(a.created_at)}</div></div>`).join("") : `<div class="empty">暂无请假记录</div>`;
      } catch (e) { $("#lList").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
    };
    $("#lSubmit").addEventListener("click", async () => {
      const sid = Number($("#lStu").value);
      const stu = STUDENTS.find((s) => s.id === sid);
      try {
        const res = await API.post("/student/leave", { student_id: sid, student_name: stu.name, leave_content: $("#lContent").value.trim() });
        toast(res.message); $("#lContent").value = ""; load();
      } catch (e) { toast(e.message, "err"); }
    });
    load();
  }

  async function tMental(root) {
    root.innerHTML = `
      <div class="grid cols-2">
        <div class="card" style="box-shadow:none"><h3>心理状态监测</h3><p class="desc">实时监测情绪，高危自动预警并通知老师</p>
          <div class="field"><label>学生</label>${studentSelect("mStu")}</div>
          <div class="field"><label>对话内容</label><textarea class="input" id="mContent" placeholder="最近压力好大，感觉撑不下去了"></textarea></div>
          <button class="btn primary" id="mSubmit">监测</button>
          <div id="mResult" class="mt-16"></div></div>
        <div class="card" style="box-shadow:none"><h3>心理预警记录</h3><div id="mList"></div></div>
      </div>`;
    const load = async () => {
      try {
        const list = await API.get("/student/mental/warnings");
        $("#mList").innerHTML = list.length ? list.map((w) => `
          <div class="card" style="box-shadow:none;border-color:var(--border);margin-top:10px">
            <div><b>${esc(w.student_name)}</b> ${riskBadge(w.risk_level)} ${statusBadge(w.follower_status)}</div>
            <div class="small">${esc(w.trigger_reason)}</div></div>`).join("") : `<div class="empty">暂无预警</div>`;
      } catch (e) { $("#mList").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
    };
    $("#mSubmit").addEventListener("click", async () => {
      const sid = Number($("#mStu").value);
      const stu = STUDENTS.find((s) => s.id === sid);
      try {
        const res = await API.post("/student/mental/monitor", { student_id: sid, student_name: stu.name, chat_content: $("#mContent").value.trim() });
        $("#mResult").innerHTML = `<div class="card" style="box-shadow:none;border-left:3px solid ${res.risk_level === "high" ? "var(--critical)" : res.risk_level === "medium" ? "var(--serious)" : "var(--good)"}">
          <div><b>情绪标签：${esc(res.emotion_tag)}</b> ${riskBadge(res.risk_level)} 分值 ${res.emotion_score}</div>
          <div class="small">${esc(res.message)}</div></div>`;
        toast(res.risk_level === "high" ? "已触发高危预警" : "监测完成", res.risk_level === "high" ? "err" : "");
        load();
      } catch (e) { toast(e.message, "err"); }
    });
    load();
  }

  async function tFeedback(root) {
    root.innerHTML = `
      <div class="grid cols-2">
        <div class="card" style="box-shadow:none"><h3>提交投诉 / 建议</h3><p class="desc">自动生成工单并提炼摘要</p>
          <div class="field"><label>学生</label>${studentSelect("fStu")}</div>
          <div class="field"><label>内容</label><textarea class="input" id="fContent" placeholder="签证办理进度太慢"></textarea></div>
          <button class="btn primary" id="fSubmit">提交工单</button></div>
        <div class="card" style="box-shadow:none"><h3>工单列表</h3><div id="fList"></div></div>
      </div>`;
    const load = async () => {
      try {
        const list = await API.get("/student/complaint");
        $("#fList").innerHTML = list.length ? list.map((t) => `
          <div class="card" style="box-shadow:none;border-color:var(--border);margin-top:10px">
            <div><b>${esc(t.student_name)}</b> ${statusBadge(t.process_status)} <span class="badge neutral">${esc(t.category)}</span></div>
            <div class="small">${esc(t.summary || t.complaint_content)}</div>
            ${t.process_status !== "已解决" ? `<button class="btn sm mt-8" data-resolve="${t.ticket_id}">标记解决</button>` : `<div class="small muted">✅ ${esc(t.solution || "已解决")}</div>`}
          </div>`).join("") : `<div class="empty">暂无工单</div>`;
        $$("#fList [data-resolve]").forEach((b) => b.addEventListener("click", async () => {
          const sol = prompt("请输入解决方案：");
          if (!sol) return;
          try { const r = await API.post(`/student/complaint/${b.dataset.resolve}/resolve`, { solution: sol }); toast(r.notify, "ok"); load(); }
          catch (e) { toast(e.message, "err"); }
        }));
      } catch (e) { $("#fList").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
    };
    $("#fSubmit").addEventListener("click", async () => {
      const sid = Number($("#fStu").value);
      const stu = STUDENTS.find((s) => s.id === sid);
      try {
        const res = await API.post("/student/complaint", { student_id: sid, student_name: stu.name, complaint_content: $("#fContent").value.trim() });
        toast(res.message); $("#fContent").value = ""; load();
      } catch (e) { toast(e.message, "err"); }
    });
    load();
  }

  async function tAcademic(root) {
    try {
      const list = await API.get("/student/academic");
      root.innerHTML = `<h3>学业考务节点</h3><p class="desc">论文 DDL、考试时间及智能提醒</p>` +
        (list.length ? `<table class="tbl"><thead><tr><th>学生</th><th>类型</th><th>事项</th><th>截止时间</th><th>提醒</th></tr></thead><tbody>
          ${list.map((a) => `<tr><td>${esc(a.student_name)}</td><td><span class="badge ${a.event_type === "exam" ? "blue" : "neutral"}">${a.event_type === "exam" ? "考试" : "DDL"}</span></td>
            <td>${esc(a.title)}</td><td>${esc(a.deadline)}</td><td>${a.remind ? "🔔 已开启" : "—"}</td></tr>`).join("")}</tbody></table>`
          : `<div class="empty">暂无考务数据</div>`);
    } catch (e) { root.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
  }

  async function tProgress(root) {
    root.innerHTML = `<div class="field"><label>选择学生</label>${studentSelect("pStu")}</div><div id="pResult" class="mt-16"></div>`;
    const load = async () => {
      const sid = Number($("#pStu").value);
      try {
        const p = await API.get(`/student/progress?student_id=${sid}`);
        const stages = [
          ["文书审核", p.document_review], ["院校申请", p.school_application], ["签证办理", p.visa_process],
        ];
        const pct = { "未开始": 10, "准备材料": 30, "审核中": 55, "已提交": 70, "已完成": 100, "已获offer": 100 };
        $("#pResult").innerHTML = `<h3>留学业务进度</h3><p class="desc">文书、申请、签证全流程追踪</p>` +
          stages.map(([label, status]) => `<div class="progress-row"><div class="p-label">${esc(label)}</div>
            <div class="progress-track"><div class="progress-fill" style="width:${pct[status] || 20}%"></div></div>
            <div class="p-val">${statusBadge(status)}</div></div>`).join("") +
          `<div class="hint">数据更新于：${esc(p.updated_at || "-")}</div>`;
      } catch (e) { $("#pResult").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
    };
    $("#pStu").addEventListener("change", load);
    load();
  }

  async function tLife(root) {
    root.innerHTML = `<div class="card" style="box-shadow:none"><h3>海外生活百事通</h3>
      <p class="desc">当地医疗、交通、租房、紧急求助等生活常识问答（示例：英国看病怎么注册？）</p>
      <div class="field"><textarea class="input" id="lifeQ" placeholder="英国看病怎么注册 NHS？"></textarea></div>
      <button class="btn primary" id="lifeBtn">提问</button><div id="lifeResult" class="mt-16"></div></div>`;
    $("#lifeBtn").addEventListener("click", async () => {
      const q = $("#lifeQ").value.trim();
      if (!q) { toast("请输入问题", "err"); return; }
      try {
        const r = await API.get(`/student/life?question=${encodeURIComponent(q)}`);
        $("#lifeResult").innerHTML = `<div class="card" style="box-shadow:none;border-left:3px solid var(--accent)">
          <div>${esc(r.reply)}</div>
          ${(r.sources || []).length ? `<div class="small muted mt-8">来源：${r.sources.map((s) => esc(s.doc_name)).join("、")}</div>` : ""}</div>`;
      } catch (e) { toast(e.message, "err"); }
    });
  }

  async function tMarketing(root) {
    root.innerHTML = `<div class="field"><label>选择学生（基于画像生成推荐）</label>${studentSelect("mkStu")}</div>
      <button class="btn primary" id="mkBtn">生成推荐话术</button><div id="mkResult" class="mt-16"></div>`;
    $("#mkBtn").addEventListener("click", async () => {
      const sid = Number($("#mkStu").value);
      try {
        const r = await API.get(`/student/marketing?student_id=${sid}`);
        $("#mkResult").innerHTML = `<div class="card" style="box-shadow:none;border-left:3px solid var(--s3)"><div>${esc(r.reply)}</div></div>`;
      } catch (e) { toast(e.message, "err"); }
    });
  }

  /* ============================================================
     智能报告
     ============================================================ */
  async function pageReport(root) {
    root.innerHTML = `
      <div class="grid cols-2">
        <div class="card"><h3>生成报告</h3><p class="desc">选择报告类型，AI 基于聚合数据生成</p>
          <div class="field"><label>报告类型</label><select class="input" id="rType">
            <option value="customer_analysis">全域客户经营分析报告</option>
            <option value="daily">员工日报汇总报告（日）</option>
            <option value="weekly">员工日报汇总报告（周）</option>
            <option value="mental_weekly">学生心理健康周报</option>
            <option value="complaint_weekly">投诉处理周报</option>
          </select></div>
          <button class="btn primary" id="rGenerate">生成报告</button></div>
        <div class="card"><h3>历史报告</h3><div id="rList"></div></div>
      </div>
      <div class="card mt-16" id="rContent" style="display:none"><div class="report-md" id="rBody"></div></div>`;
    const load = async () => {
      try {
        const list = await API.get("/report/list");
        $("#rList").innerHTML = list.length ? list.map((r) => `
          <div class="card" style="box-shadow:none;border-color:var(--border);margin-top:10px;cursor:pointer" data-view="${r.report_id}">
            <div><b>${esc(r.report_name)}</b></div><div class="small muted">${esc(r.generated_at)}</div></div>`).join("")
          : `<div class="empty">暂无报告</div>`;
        $$("#rList [data-view]").forEach((b) => b.addEventListener("click", async () => {
          const r = await API.get(`/report/${b.dataset.view}`);
          $("#rContent").style.display = "block";
          $("#rBody").innerHTML = md(r.report_content);
          $("#rContent").scrollIntoView({ behavior: "smooth" });
        }));
      } catch (e) { $("#rList").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
    };
    $("#rGenerate").addEventListener("click", async () => {
      const btn = $("#rGenerate"); btn.disabled = true; btn.textContent = "生成中…";
      try {
        const r = await API.post("/report/generate", { report_type: $("#rType").value });
        toast("报告已生成", "ok");
        $("#rContent").style.display = "block";
        $("#rBody").innerHTML = md(r.report_content);
        $("#rContent").scrollIntoView({ behavior: "smooth" });
        load();
      } catch (e) { toast(e.message, "err"); }
      finally { btn.disabled = false; btn.textContent = "生成报告"; }
    });
    load();
  }

  /* ---------- 启动 ---------- */
  async function loadMeta() {
    try {
      const meta = await API.get("/meta");
      $("#difyBadge").textContent = meta.dify_enabled ? "AI 能力：Dify" : "AI 能力：本地引擎";
      $("#difyBadge").className = "badge " + (meta.dify_enabled ? "good" : "neutral");
    } catch (e) { /* 忽略 */ }
  }

  /* ---------- 侧边栏导航 ---------- */
  $$("#nav .nav-item").forEach((b) => b.addEventListener("click", () => {
    const route = b.dataset.route;
    if (currentRoute() !== route) location.hash = "#/" + route;
    else render();
  }));

  window.addEventListener("hashchange", render);
  initTheme();
  loadMeta();
  render();
})();
