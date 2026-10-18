import { API, request, readSession, saveSession, clearSession, createRequestId } from '../common/api.js';
import { PAGE_RESOURCES, operationsForPage, operationsForAccess, LABELS } from './pages.js';

const $ = (q, root=document) => root.querySelector(q);
const $$ = (q, root=document) => [...root.querySelectorAll(q)];
const page = location.pathname.replace(/^\/static\//,'/').replace(/^\//,'');
const style = document.createElement('link'); style.rel='stylesheet'; style.href='/css/workspace/live.css'; document.head.append(style);
const node = (tag, text, cls) => { const n=document.createElement(tag); if(text!==undefined)n.textContent=text; if(cls)n.className=cls;return n; };
const label = key => LABELS[key] || (key ? key.replaceAll('_',' ') : '业务记录');
const status = (root, text, error=false) => { root.replaceChildren(node('p',text,error?'live-error':'live-status')); };
const enums = {admin:'平台管理员',employee:'员工',student:'学生',customer:'客户',approved:'同意',rejected:'驳回',
  active:'有效',disabled:'停用',pending:'待处理',in_progress:'进行中',completed:'已完成',cancelled:'已取消',
  new:'新客户',contacting:'跟进中',qualified:'意向确认',signed:'已签约',lost:'已流失',local:'本地维护',admin_registration:'管理员开户',
  complaint:'投诉',suggestion:'建议',personal:'事假',exam:'考试',ddl:'截止事项',student_visible:'学生可见',internal:'内部',
  document_review:'文书审核',school_application:'院校申请',visa_process:'签证办理',class_teacher:'班主任',score_editor:'成绩维护',
  service_advisor:'服务顾问',customer_overview:'客户经营分析',daily_report:'员工日报汇总',weekly_report:'员工周报',
  mental_weekly:'学生心理周报',complaint_weekly:'投诉处理周报',
  running:'生成中',success:'已生成',failed:'失败','Asia/Shanghai':'北京时间'};
const privateField=key=>/password|ciphertext|lookup_token|secret|request_hash|parameters_hash/.test(key)||['token','action_token','conversation_token','request_key','__path'].includes(key);
const publicValue=value=>Array.isArray(value)?value.map(publicValue):value&&typeof value==='object'?Object.fromEntries(Object.entries(value).filter(([key])=>!privateField(key)).map(([key,item])=>[key,publicValue(item)])):value;
const format = value => value===null||value===undefined?'—':typeof value==='boolean'?(value?'是':'否'):typeof value==='object'?JSON.stringify(publicValue(value),null,2):enums[value]||String(value);
let schema, selected={}, options={}, studentWorkspace=null, studentAccess=null;
const forms=[], listQueries=[];
const resourceKey=path=>path.split('/').slice(3,path.includes('/internal/')?6:5).join('/');
const resolve = raw => {
  let value = raw || {};
  if (value.$ref) value = schema.components?.schemas?.[value.$ref.split('/').at(-1)] || {};
  if (value.anyOf) value = { ...value, ...resolve(value.anyOf.find(x => x.type !== 'null') || {}) };
  return value;
};
function remember(row, path = '') {
  selected = { ...selected, ...row, __path: path };
  const idKeys = {
    customer: 'customer_id', 'daily-report': 'report_id', scores: 'score_id', students: 'student_id', courses: 'course_id',
    'student-courses': 'enrollment_id', 'academic-events': 'event_id', 'application-progress': 'progress_id',
    knowledge: 'knowledge_id', employees: 'employee_id', departments: 'department_id', 'student-bindings': 'binding_id',
    leave: 'apply_id', warnings: 'warning_id', reminders: 'reminder_id', source: 'source_id', result: 'result_id', events: 'event_id'
  };
  for (const [resource, idKey] of Object.entries(idKeys)) if (path.includes('/' + resource) && row.id !== undefined) selected[idKey] = row.id;
  if (row.daily_report_id) selected.report_id = row.daily_report_id;
  if (row.row_version) selected.expected_version = row.row_version;
  if (row.event_version) selected.expected_event_version = row.event_version;
  if (row.updated_at) selected.expected_updated_at = row.updated_at;
  // Preview receipts only populate the confirmation form; confirmation always requires a separate submit.
  if (row.token) sessionStorage.setItem('stuproject.command.preview', JSON.stringify(row));
  if (row.action_token) sessionStorage.setItem('stuproject.student.preview', JSON.stringify(row));
  sessionStorage.setItem('stuproject.live.selection', JSON.stringify(selected));
  for (const form of forms) for (const input of $$('[data-field]', form)) {
    if (path && form.dataset.resource !== resourceKey(path)) continue;
    const name = input.dataset.field;
    if (Object.hasOwn(selected, name) && !name.includes('.')) setValue(input, selected[name]);
  }
}
function setValue(input, value) {
  if (value === null || value === undefined) return;
  if (input.type === 'datetime-local') {
    const date = new Date(/Z$|[+-]\d\d:\d\d$/.test(String(value)) ? value : value + 'Z');
    if (!Number.isNaN(date.valueOf())) input.value = new Date(date.valueOf() + 8 * 3600000).toISOString().slice(0, 19);
  } else if (input.type !== 'file') input.value = typeof value === 'object' ? JSON.stringify(value) : String(value);
}
function renderData(root, data, path) {
  root.replaceChildren();
  if (data === null || data === undefined) { root.append(node('p', '操作成功。')); return; }
  const rows = Array.isArray(data) ? data : Array.isArray(data.items) ? data.items : Array.isArray(data.rows) ? data.rows : null;
  if (rows) {
    root.append(node('p', `共 ${data.total ?? rows.length} 条记录。` + (readOnlyView ? '点击查看记录，可查看详细信息。' : '选择记录后，可在下方操作中使用其编号和当前版本。')));
    if (!rows.length) { root.append(node('p', '暂无记录。')); return; }
    const keys = [...new Set(rows.flatMap(row => Object.keys(row)))].filter(k => !/(password|ciphertext|lookup_token|secret|request_hash)/i.test(k));
    const priority = ['full_name', 'username', 'course_name', 'title', 'report_name', 'customer_no', 'student_no', 'course_code', 'report_date', 'status', 'row_version'];
    keys.sort((a, b) => (priority.includes(a) ? priority.indexOf(a) : 99) - (priority.includes(b) ? priority.indexOf(b) : 99));
    const visible = keys.slice(0, 8), wrap = node('div', undefined, 'table-wrap'), table = node('table', undefined, 'data-table');
    const head = node('tr'); for (const k of visible) head.append(node('th', label(k))); head.append(node('th', '操作'));
    const thead = node('thead'); thead.append(head); table.append(thead);
    const body = node('tbody');
    for (const row of rows) {
      const tr = node('tr'); for (const k of visible) tr.append(node('td', format(row[k])));
      const td = node('td'), choose = node('button', readOnlyView ? '查看记录' : '选择记录', 'button secondary small'); choose.type = 'button';
      choose.onclick = () => { remember(row, path); detail.replaceChildren(node('p', '已选择此记录。', 'live-selection')); renderObject(detail, row); }; td.append(choose); tr.append(td); body.append(tr);
    }
    table.append(body); wrap.append(table); root.append(wrap); const detail = node('div'); root.append(detail);
  } else if (typeof data === 'object') {
    remember(data, path);
    if (data.pending_action?.action_token) remember(data.pending_action, '/api/v1/student/actions/confirm');
    renderObject(root, data);
  } else root.append(node('p', String(data)));
}
function renderObject(root, data) {
  const dl = node('dl'); for (const [key, value] of Object.entries(data)) {
    if (privateField(key)) continue;
    dl.append(node('dt', label(key)), node('dd', format(value)));
  } root.append(dl);
}
function field(parent, name, raw, required = false, prefix = '') {
  const spec = resolve(raw), full = prefix + name;
  if (spec.type === 'object' && spec.properties) {
    const group = node('fieldset'); group.append(node('legend', label(name)));
    for (const [key, value] of Object.entries(spec.properties)) field(group, key, value, (spec.required || []).includes(key), full + '.');
    parent.append(group); return;
  }
  const box = node('div', undefined, 'form-field'), id = 'live-' + createRequestId(), caption = node('label', label(name) + (required ? ' *' : '')); caption.htmlFor = id;
  let input;
  const choices = spec.enum || (spec.const !== undefined ? [spec.const] : null);
  if (choices || spec.type === 'boolean' || (name === 'position_title' && options.positions) || (name === 'department_id' && options.departments)) {
    input = node('select'); input.append(new Option(required ? '请选择' : '不设置', ''));
    let entries = choices ? choices.map(x => [x, enums[x] || x]) : spec.type === 'boolean' ? [[true, '是'], [false, '否']] : name === 'position_title' ? Object.keys(options.positions).map(x => [x, x]) : options.departments.map(x => [x.department_id, x.department_name]);
    for (const [v, text] of entries) input.append(new Option(text, String(v)));
    if (spec.const !== undefined) input.value = String(spec.const);
  } else if (spec.type === 'object' || spec.type === 'array' || (!spec.type && !spec.format) || ['content', 'submitted_content', 'leave_content', 'chat_content', 'message', 'text', 'answer', 'content_text'].includes(name)) {
    input = node('textarea'); box.classList.add('wide');
  } else {
    input = node('input'); input.type = name === 'expected_updated_at' ? 'text' : spec.format === 'binary' || spec.contentMediaType ? 'file' : spec.format === 'date-time' ? 'datetime-local' : spec.format === 'date' ? 'date' : ['integer', 'number'].includes(spec.type) ? 'number' : 'text';
    if (name === 'expected_updated_at') input.readOnly = true; // Preserve the exact microsecond version returned by the server.
    if (input.type === 'number') input.step = spec.type === 'integer' ? '1' : 'any';
    if (input.type === 'datetime-local') input.step = '0.000001';
  }
  input.id = id; input.name = full; input.dataset.field = full; input.dataset.type = spec.type || 'object';
  input.dataset.format = spec.format || ''; input.required = required;
  if (spec.minimum !== undefined) input.min = spec.minimum; if (spec.maximum !== undefined) input.max = spec.maximum;
  if (spec.exclusiveMinimum !== undefined) input.min = spec.exclusiveMinimum + 1;
  if (spec.minLength !== undefined) input.minLength = spec.minLength; if (spec.maxLength !== undefined) input.maxLength = spec.maxLength;
  if (spec.default !== undefined && spec.default !== null) setValue(input, spec.default);
  const leaf = full.split('.').at(-1);
  if (name === 'timezone') input.value = 'Asia/Shanghai';
  if (name === 'rule_content') input.value = '{"logic":"all","conditions":[{"field":"age","op":">=","value":18}]}';
  if (name === 'filters' || name === 'target') input.value = '{}';
  box.append(caption, input); parent.append(box);
}
function readFields(form) {
  const value = {};
  for (const input of $$('[data-field]', form)) {
    if (input.disabled || input.type === 'file' || input.value === '') continue;
    let item = input.value;
    if (['number', 'integer'].includes(input.dataset.type)) item = Number(item);
    else if (input.dataset.type === 'boolean') item = item === 'true';
    else if (['object', 'array'].includes(input.dataset.type)) {
      try { item = JSON.parse(item); } catch { throw new Error(label(input.dataset.field.split('.').at(-1)) + '的格式不正确，请填写有效内容。'); }
    } else if (input.type === 'datetime-local') item = item + '+08:00';
    const parts = input.dataset.field.split('.'); let target = value;
    parts.forEach((part, index) => { if (index === parts.length - 1) target[part] = item; else target = target[part] ??= {}; });
  } return value;
}
function operationTitle(op) {
  const parts = op.path.split('/').filter(x => x && !x.startsWith('{')).slice(3);
  const names = parts.filter(x => !['internal', 'student', 'enterprise', 'agent', 'auth', 'report'].includes(x)).map(label);
  const action = op.method === 'GET' ? '查看' : op.method === 'POST' ? '提交' : op.method === 'PUT' ? '修改' : op.method === 'DELETE' ? '撤销或停用' : '更新';
  return action + ' ' + (names.join(' · ') || label(parts.at(-1))) + (op.method === 'GET' && op.path.includes('{') ? '详情' : '');
}
function operationCard(op, index) {
  const card = node('details', undefined, 'section-card live-section'); card.dataset.operation = op.method + ' ' + op.path;
  if (index === 0) card.open = true; card.append(node('summary', operationTitle(op)));
  const body = node('div', undefined, 'live-body'), form = node('form', undefined, 'live-form'), response = node('div', undefined, 'live-result'), message = node('div');
  forms.push(form); form.dataset.resource = resourceKey(op.path); const params = (op.parameters || []).filter(p => p.in !== 'header' &&
    (p.name !== 'unread_only' || op.path.includes('/notifications')) && (p.name !== 'manage' || op.path.includes('/knowledge')));
  // Request-based enterprise routes declare identifiers in the URL; infer any omitted schema parameters.
  for (const match of op.path.matchAll(/\{([^}]+)\}/g)) if (!params.some(p => p.name === match[1])) params.push({ name: match[1], in: 'path', required: true, schema: { type: match[1].endsWith('_code') ? 'string' : 'integer', minimum: 1 } });
  for (const p of params) field(form, p.name, p.schema, p.required);
  if (resourceKey(selected.__path || '') === resourceKey(op.path)) for (const p of params.filter(p => p.in === 'path')) {
    const input = $('[name="' + p.name + '"]', form); if (input && selected[p.name] !== undefined) setValue(input, selected[p.name]);
  }
  const content = op.requestBody?.content || {}, mime = Object.keys(content)[0], bodySpec = resolve(content[mime]?.schema);
  let bodyContainer = form;
  function bodyFields(spec) { for (const [name, raw] of Object.entries(spec.properties || {})) field(bodyContainer, name, raw, (spec.required || []).includes(name)); }
  if (bodySpec.oneOf) {
    const picker = node('select'); picker.name = 'identity-choice'; picker.setAttribute('aria-label', '账号身份'); picker.required = true;
    const box = node('div', undefined, 'form-field'); box.append(node('label', '账号身份 *'), picker); form.append(box);
    const branches = bodySpec.oneOf.map(resolve); for (let n = 0; n < branches.length; n++) {
      const identity = resolve(branches[n].properties.identity_type).const; picker.append(new Option(enums[identity] || identity, String(n)));
    }
    const region = node('div', undefined, 'wide live-form'); form.append(region); bodyContainer = region;
    const fill = () => { region.replaceChildren(); bodyFields(branches[Number(picker.value)]); }; picker.onchange = fill; fill();
  } else bodyFields(bodySpec);
  const actions = node('div', undefined, 'form-actions'), submit = node('button', op.method === 'GET' ? '查询' : '确认提交', 'button'); submit.type = 'submit'; actions.append(submit); form.append(actions);
  let pendingKey = null, signature = null, hasList = false;
  async function execute() {
    message.replaceChildren(); submit.disabled = true;
    try {
      if (!form.reportValidity()) return;
      let path = op.path, values = readFields(form), query = new URLSearchParams();
      for (const p of params) {
        const v = values[p.name]; delete values[p.name]; if (v === undefined) continue;
        if (p.in === 'path') path = path.replace('{' + p.name + '}', encodeURIComponent(v)); else query.set(p.name, String(v));
      }
      if (path.includes('{')) throw new Error('请先选择记录或填写对应编号。');
      const sign = JSON.stringify({ path, values, query: String(query) });
      if (sign !== signature) { signature = sign; pendingKey = createRequestId(); }
      let payload = values;
      if (mime === 'multipart/form-data') {
        payload = new FormData(); for (const [k, v] of Object.entries(values)) payload.append(k, String(v));
        for (const input of $$('input[type=file]', form)) if (input.files[0]) payload.append(input.name, input.files[0]);
      }
      if (op.method === 'GET' && op.path.endsWith('/file')) {
        const auth = readSession(); const r = await fetch(path, { headers: auth ? { Authorization: 'Bearer ' + auth.accessToken } : {} });
        if (!r.ok || r.headers.get('content-type')?.includes('json')) { const error = await r.json(); throw new Error(error.message || error.detail || '原件不可用'); }
        const url = URL.createObjectURL(await r.blob()), link = node('a'); link.href = url; link.download = '资料原件'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); status(message, '原件已下载。'); return;
      }
      const data = await request(path.slice('/api/v1'.length) + (query.size ? '?' + query : ''), {
        method: op.method, authenticated: !path.includes('/agent/'), body: op.method === 'GET' ? undefined : payload,
        headers: op.method === 'GET' ? {} : { 'Idempotency-Key': pendingKey }, timeoutMs: 20000
      });
      if (op.method !== 'GET' && path.startsWith('/api/v1/student/notifications/')) window.dispatchEvent(new Event('student:notifications-changed'));
      pendingKey = null; renderData(response, data, path); status(message, op.method === 'GET' ? '已读取最新数据。' : '操作成功，结果已由服务保存。');
      hasList = Array.isArray(data) || Array.isArray(data?.items) || Array.isArray(data?.rows);
      // Selection must use current versions after a successful write. Refresh only
      // lists already queried by the user; never repeat another business mutation.
      if (op.method !== 'GET') await Promise.allSettled(listQueries.map(refresh => refresh()));
    } catch (error) { status(message, error.message, true); } finally { submit.disabled = false; }
  }
  form.addEventListener('submit', event => { event.preventDefault(); execute(); }); body.append(form, message, response); card.append(body);
  // Query-only cards can be opened without issuing writes. Never submit a mutation automatically.
  let loaded = false; card.addEventListener('toggle', () => { if (card.open && !loaded && op.method === 'GET' && !params.some(p => p.required)) { loaded = true; execute(); } });
  if (op.method === 'GET' && !params.some(p => p.required)) listQueries.push(() => hasList ? execute() : undefined);
  if (index === 0 && op.method === 'GET' && !params.some(p => p.required)) { loaded = true; queueMicrotask(execute); }
  if (op.path.endsWith('/confirm')) {
    const storage = op.path.includes('/enterprise/') ? 'stuproject.command.preview' : 'stuproject.student.preview';
    try { const receipt = JSON.parse(sessionStorage.getItem(storage) || 'null'); if (receipt) remember(receipt, op.path); } catch { }
  }
  return card;
}
async function login() {
  const form = $('[data-login-preview]'); if (!form) return;
  const name = $('input[type=text]', form), password = $('input[type=password]', form), button = $('button[type=submit]', form);
  name.name = 'username'; name.autocomplete = 'username'; password.name = 'password'; password.autocomplete = 'current-password'; button.textContent = '登录';
  $('.login-disclaimer').textContent = '账号由平台管理员创建。登录后按当前身份访问业务。';
  $('.preview-link').textContent = '浏览公开页面'; $('.preview-link').href = '/index.html'; const message = node('div'); form.append(message);
  form.addEventListener('submit', async event => {
    event.preventDefault(); button.disabled = true; message.replaceChildren();
    try {
      const data = await API.login(name.value.trim(), password.value); saveSession(data); password.value = '';
      const access = await API.myAccess();
      location.assign(access.identity_type === 'student' ? '/student/student-assistant.html' : access.identity_type === 'employee' ? '/enterprise/enterprise.html' : access.identity_type === 'customer' ? '/common/account.html' : '/dashboard/dashboard.html');
    }
    catch (error) { status(message, error.message, true); } finally { button.disabled = false; }
  });
}
async function start() {
  await login(); if ($('[data-login-preview]')) return;
  $$('.preview-tag').forEach(x => x.textContent = '本地服务'); $$('.preview-notice').forEach(x => x.remove());
  if (page === 'common/sitemap.html') return;
  if (page === 'common/password-reset.html') {
    const main = $('main'); if (main) { main.replaceChildren(node('h1', '账号协助'), node('p', '请联系平台管理员核实账号。当前系统未配置短信、邮件或自助密码重置服务。')); } return;
  }
  if (!PAGE_RESOURCES[page]) return;
  const main = $('#main-content'); if (!main) return;
  const heading = $('.page-heading', main)?.cloneNode(true); if (heading) $$('.actions', heading).forEach(x => x.remove());
  const footer = $('.page-footer', main)?.cloneNode(true); main.replaceChildren(); if (heading) main.append(heading);
  const intro = node('p', '正在连接本地服务……', 'live-status'); main.append(intro);
  const isPublic = page.startsWith('agent/');
  if (!readSession() && !isPublic) { intro.textContent = '请先登录后使用此功能。'; const link = node('a', '前往登录', 'button'); link.href = '/common/login.html'; main.append(link); return; }
  try {
    try { selected = JSON.parse(sessionStorage.getItem('stuproject.live.selection') || '{}'); } catch { }
    const response = await fetch('/openapi.json'); if (!response.ok) throw new Error('服务契约暂时不可用。'); schema = await response.json();
    if (readSession()) {
      access = await API.myAccess();
      $$('.user-name').forEach(x => x.textContent = (enums[access.identity_type] || access.identity_type) + ' #' + access.user_id);
      if (access.identity_type === 'admin') {
        const r = await fetch('/api/v1/admin/openapi.json', { headers: { Authorization: 'Bearer ' + readSession().accessToken } });
        if (r.ok) { const admin = await r.json(); schema.paths = { ...schema.paths, ...admin.paths }; schema.components.schemas = { ...schema.components.schemas, ...admin.components.schemas }; }
        options = await request('/admin/accounts/options');
      }
      const logout = node('button', '退出登录', 'button secondary small'); logout.type = 'button'; logout.onclick = () => { clearSession(); location.assign('/common/login.html'); }; $('.top-actions')?.append(logout);
      if (page.startsWith('student/')) {
        studentAccess = access; studentWorkspace = await import('../student/workspace-enhancements.js');
        if (await studentWorkspace.initializeStudentWorkspace({ access, main, page })) {
          intro.remove();
          if (footer) main.append(footer); document.documentElement.dataset.liveReady = 'true'; return;
        }
      }
    }
    intro.textContent = '数据来自当前本地业务库。修改前请选择记录，提交时使用其当前版本。';
    const operations = operationsForPage(page, schema.paths);
    for (let index = 0; index < operations.length; index++)main.append(operationCard(operations[index], index));
    if (!operations.length) intro.textContent = '当前身份没有可用操作。';
  } catch (error) { status(intro, error.message, true); }
  if (footer) main.append(footer);
  document.documentElement.dataset.liveReady = 'true';
}
window.addEventListener('auth:expired', () => location.assign('/common/login.html'));
await start();
