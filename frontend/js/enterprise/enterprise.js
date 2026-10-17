import { API } from "../common/module-api.js";
import { $, $$, esc, toast, riskBadge, statusBadge, studentSelect } from "../common/ui.js";

  export function render(root) {
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
          <div class="field"><label>学生</label>${studentSelect("sStu")}</div>
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

      try {
        await API.post("/enterprise/score", { student_id: sid, subject: $("#sSubject").value.trim(), score: Number($("#sScore").value) });
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
