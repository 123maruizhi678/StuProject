import { API } from "../common/module-api.js";
import { $, $$, esc, toast, riskBadge, statusBadge, studentSelect } from "../common/ui.js";

  export function render(root) {
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

      try {
        const res = await API.post("/student/leave", { student_id: sid, leave_content: $("#lContent").value.trim() });
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

      try {
        const res = await API.post("/student/mental/monitor", { student_id: sid, chat_content: $("#mContent").value.trim() });
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

      try {
        const res = await API.post("/student/complaint", { student_id: sid, complaint_content: $("#fContent").value.trim() });
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
