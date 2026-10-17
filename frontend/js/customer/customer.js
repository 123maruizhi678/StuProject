import { API } from "../common/module-api.js";
import { $, $$, esc, toast, riskBadge, statusBadge, studentSelect } from "../common/ui.js";

  export async function render(root) {
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
