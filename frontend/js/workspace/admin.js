import { request, createRequestId } from '../common/api.js';
import { operationsForPage, operationsForAccess } from './pages.js';

const node = (tag, text, cls) => {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (cls) element.className = cls;
  return element;
};
const definitions = {
  'admin/accounts.html': { path: '/api/v1/admin/accounts', title: '查看 账号', create: '/api/v1/auth/register', createTitle: '新增账号' },
  'admin/permissions.html': { path: '/api/v1/enterprise/employees', title: '查看 员工', create: '/api/v1/enterprise/employees', createTitle: '新增员工' },
  'admin/audit.html': { path: '/api/v1/enterprise/operation-logs', title: '查看 操作记录' },
  'admin/settings.html': { path: '/api/v1/report/configs', title: '查看 报告配置' },
};
const roleNames = { employee: '员工', consultant: '客户顾问', manager: '部门主管', teacher: '班主任', academic: '教务', admin: '员工管理员', analyst: '研判人员', reviewer: '规则复核人员', counselor: '关怀老师' };

export async function mountAdminWorkspace({ main, page, schema, access, options, field, readFields, resolve, setValue, format, label, buildBodyFields }) {
  const definition = definitions[page];
  if (!definition) return;
  const operations = operationsForAccess(operationsForPage(page, schema.paths), access);
  const find = (method, path) => operations.find(operation => operation.method === method && operation.path === path);
  const can = permission => access.identity_type === 'admin' || access.permissions?.includes(permission);
  const adminCreationPage = page === 'admin/permissions.html' && access.identity_type === 'admin';
  const isPlatformAdminRow = row => row.identity_type === 'admin' || row.role_codes?.includes('admin') ||
    options.positions?.[row.position_title]?.includes('admin') || ['平台管理员', '企业管理员', '企业配置管理员'].includes(row.position_title);
  const listOp = find('GET', definition.path);
  if (!listOp) { main.append(node('p', '当前身份没有可用操作。', 'live-status')); return; }
  const employeeUpdate = can('enterprise.employee.manage') && find('PUT', definition.path + '/{employee_id}');
  const roleUpdate = can('enterprise.role.manage') && find('PUT', definition.path + '/{employee_id}/roles');
  const configUpdate = find('PUT', definition.path + '/{report_code}');
  const createOp = adminCreationPage ? find('POST', '/api/v1/auth/register')
    : (page !== 'admin/permissions.html' || can('enterprise.employee.manage')) && find('POST', definition.create);
  const createTitle = adminCreationPage ? '新建平台管理员' : definition.createTitle;
  const card = node('section', undefined, 'section-card admin-list'); card.dataset.operation = 'GET ' + definition.path;
  const heading = node('div', undefined, 'section-title'), body = node('div', undefined, 'section-body');
  heading.append(node('h2', definition.title)); card.append(heading, body); main.append(card);
  const feedback = node('div'), result = node('div', undefined, 'live-result');
  feedback.setAttribute('aria-live', 'polite');
  if (createOp) {
    const toolbar = node('div', undefined, 'admin-list-toolbar'), add = node('button', createTitle, 'button');
    add.type = 'button'; add.onclick = () => openEditor(createOp, createTitle);
    toolbar.append(add); body.append(toolbar);
  }
  body.append(feedback, result);
  let offset = 0, generation = 0;
  const size = 10;
  const reportConfig = page === 'admin/settings.html';
  const employeeList = page === 'admin/permissions.html';
  const message = (text, error = false) => feedback.replaceChildren(node('p', text, error ? 'live-error' : 'live-status'));

  async function load() {
    const current = ++generation;
    message('正在读取数据……');
    try {
      const data = await request(definition.path.slice('/api/v1'.length) + (reportConfig ? '' : `?limit=${size}&offset=${offset}`));
      if (current !== generation) return;
      const rows = Array.isArray(data) ? data : data.items || data.rows || [];
      const total = data.total ?? rows.length;
      // A deletion or changed filter can leave a previously populated last page empty.
      if (!reportConfig && !rows.length && offset > 0 && offset >= total) { offset = Math.max(0, Math.ceil(total / size) * size - size); return load(); }
      feedback.replaceChildren(); result.replaceChildren(node('p', `共 ${total} 条记录。`, 'admin-list-count'));
      if (!rows.length) { result.append(node('p', '暂无记录。')); return; }
      const excluded = key => /password|ciphertext|lookup_token|secret|request_hash|parameters_hash/.test(key) || ['token', 'action_token', 'conversation_token', 'request_key'].includes(key) || key.startsWith('__');
      const keys = employeeList ? ['full_name', 'employee_no', 'department_id', 'position_title', 'work_email', 'status', 'row_version']
        : [...new Set(rows.flatMap(row => Object.keys(row)))].filter(key => !excluded(key));
      const columnLabel = key => employeeList && key === 'department_id' ? '部门' : label(key);
      const priority = ['full_name', 'username', 'employee_no', 'identity_type', 'position_title', 'work_email', 'status', 'report_name', 'report_code', 'enabled', 'cron_expr'];
      if (!employeeList) keys.sort((a, b) => (priority.includes(a) ? priority.indexOf(a) : 99) - (priority.includes(b) ? priority.indexOf(b) : 99));
      const table = node('table', undefined, 'data-table'), wrap = node('div', undefined, 'table-wrap');
      const thead = node('thead'), header = node('tr'), tbody = node('tbody');
      for (const key of keys) { const th = node('th', columnLabel(key)); th.scope = 'col'; header.append(th); }
      if (employeeUpdate || roleUpdate || configUpdate) { const th = node('th', '操作'); th.scope = 'col'; header.append(th); }
      thead.append(header); table.append(thead, tbody); wrap.append(table); result.append(wrap);
      for (const row of rows) {
        const tr = node('tr');
        for (const key of keys) {
          const value = key === 'department_id' ? options.departments?.find(item => item.department_id === row[key])?.department_name ?? format(row[key]) : format(row[key]);
          const td = node('td', value); td.dataset.label = columnLabel(key); tr.append(td);
        }
        if (employeeUpdate || roleUpdate || configUpdate) {
          const td = node('td', undefined, 'admin-record-actions'); td.dataset.label = '操作';
          const addAction = (text, operation, mode) => {
            if (!operation) return;
            const button = node('button', text, 'button secondary small'); button.type = 'button';
            button.onclick = () => openEditor(operation, text, row, mode); td.append(button);
          };
          if (!employeeList || !isPlatformAdminRow(row)) {
            addAction('编辑员工', employeeUpdate);
            addAction('调整角色', roleUpdate, 'roles');
          } else td.append(node('span', '仅查看', 'muted'));
          addAction('修改配置', configUpdate);
          tr.append(td);
        }
        tbody.append(tr);
      }
      if (!reportConfig) {
        const pager = node('div', undefined, 'live-paging');
        for (const [text, next, disabled] of [['上一页', offset - size, offset === 0], ['下一页', offset + size, offset + size >= total]]) {
          const button = node('button', text, 'button secondary small'); button.type = 'button'; button.disabled = disabled;
          button.onclick = () => { offset = next; load(); }; pager.append(button);
          if (text === '上一页') pager.append(node('span', `第 ${Math.floor(offset / size) + 1} 页`));
        }
        result.append(pager);
      }
    } catch (error) { if (current === generation) message(error.message, true); }
  }

  function openEditor(operation, title, row = null, mode = '') {
    if (employeeList && row && isPlatformAdminRow(row)) return;
    const dialog = node('dialog', undefined, 'enterprise-dialog admin-dialog'); dialog.setAttribute('aria-label', title);
    const scroll = node('div', undefined, 'enterprise-dialog-scroll'), head = node('header', undefined, 'enterprise-dialog-head');
    const close = node('button', '×', 'icon-button'); close.type = 'button'; close.setAttribute('aria-label', '关闭弹窗');
    head.append(node('h2', title), close);
    const content = node('div', undefined, 'enterprise-dialog-content'), form = node('form', undefined, 'live-form');
    form.dataset.operation = operation.method + ' ' + operation.path;
    const response = node('div', undefined, 'wide admin-action-result'); response.setAttribute('aria-live', 'polite');
    const bodySpec = resolve(operation.requestBody?.content?.['application/json']?.schema);
    const adminRegistration = adminCreationPage && !row && operation.path === '/api/v1/auth/register';
    const adminSpec = adminRegistration && [bodySpec, ...(bodySpec.oneOf || []).map(resolve)]
      .find(spec => resolve(spec.properties?.identity_type).const === 'admin');
    const initial = new Map();
    if (row) content.append(node('p', row.full_name || row.report_name || '', 'enterprise-record-name'));
    const addField = (name, raw, required) => {
      field(form, name, raw, required);
      const input = form.elements.namedItem(name);
      if (row && name !== 'reason' && Object.hasOwn(row, name)) setValue(input, row[name]);
      if (input) initial.set(name, input.value);
      return input;
    };
    let position;
    if (adminRegistration) {
      form.append(node('p', '账号身份：平台管理员', 'wide enterprise-form-context'));
      if (adminSpec) {
        for (const [name, raw] of Object.entries(adminSpec.properties || {})) {
          if (name !== 'identity_type') addField(name, raw, (adminSpec.required || []).includes(name));
        }
      } else form.append(node('p', '暂时无法读取平台管理员开户表单，请刷新后重试。', 'wide live-error'));
    } else if (mode === 'roles') {
      const positionSpec = resolve(employeeUpdate?.requestBody?.content?.['application/json']?.schema)?.properties?.position_title;
      if (positionSpec && options.positions) {
        position = addField('position_title', positionSpec, true);
        const preview = node('p', undefined, 'wide enterprise-form-context');
        const updatePreview = () => { preview.textContent = '对应角色：' + (options.positions[position.value] || []).map(role => roleNames[role] || role).join('、') + '。保存后按职位配置调整权限。'; };
        position.addEventListener('change', updatePreview); updatePreview(); form.append(preview);
      } else form.append(node('p', '业务角色由职位决定。此处仅同步当前职位对应角色。', 'wide enterprise-form-context'));
      const reasonSpec = bodySpec.properties?.reason || { type: 'string', minLength: 1, maxLength: 1000 };
      addField('reason', reasonSpec, true);
    } else if (row) {
      for (const [name, raw] of Object.entries(bodySpec.properties || {})) {
        if (['row_version', 'expected_version'].includes(name)) continue;
        // The employee read API does not expose left_date. Do not clear an existing value implicitly.
        const input = addField(name, raw, (bodySpec.required || []).includes(name) || (employeeList && ['full_name', 'position_title'].includes(name) && Boolean(row[name])));
        if (employeeList && name === 'position_title' && !can('enterprise.role.manage')) input.disabled = true;
      }
      if (employeeList) {
        const status = form.elements.namedItem('status'), leftDate = form.elements.namedItem('left_date');
        const updateLeftDate = () => { if (leftDate) leftDate.required = status?.value === 'left' && row.status !== 'left'; };
        status?.addEventListener('change', updateLeftDate); updateLeftDate();
      }
    } else buildBodyFields(operation, form);
    const actions = node('div', undefined, 'form-actions'), cancel = node('button', '取消', 'button secondary'); cancel.type = 'button';
    const submit = node('button', row ? '保存' : '确认提交', 'button'); submit.type = 'submit';
    if (adminRegistration && !adminSpec) submit.disabled = true;
    actions.append(cancel, submit); form.append(actions, response); content.append(form); scroll.append(head, content); dialog.append(scroll);
    document.body.append(dialog);
    let busy = false, signature = null, pendingKey = null;
    close.onclick = cancel.onclick = () => { if (!busy) dialog.close(); };
    dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
    dialog.addEventListener('close', () => dialog.remove());
    form.addEventListener('submit', async event => {
      event.preventDefault(); if (busy || !form.reportValidity()) return;
      busy = true; submit.disabled = cancel.disabled = close.disabled = true; response.replaceChildren();
      try {
        let op = operation, values = readFields(form);
        if (adminRegistration) {
          if (!adminSpec || op.method !== 'POST') throw new Error('暂时无法读取平台管理员开户表单，请刷新后重试。');
          values = { username: values.username, identity_type: 'admin' };
        }
        if (employeeList && row && isPlatformAdminRow(row)) throw new Error('平台管理员记录仅支持查看。');
        if (row) {
          if (!Number.isInteger(row.row_version) || row.row_version < 1) throw new Error('当前记录缺少版本，请刷新列表后重试。');
          if (mode === 'roles') {
            const chosenPosition = position?.value || row.position_title;
            const mapped = options.positions?.[chosenPosition];
            if (!Array.isArray(mapped) || !mapped.length) throw new Error('该职位尚未配置角色，请选择有效职位。');
            const reason = values.reason;
            if (chosenPosition !== row.position_title && employeeUpdate) {
              op = employeeUpdate; values = { position_title: chosenPosition, reason };
            } else values = { role_codes: mapped, reason };
          } else if (employeeList) {
            // Submit changed employee fields only, preserving fields absent from read responses.
            values = Object.fromEntries(Object.entries(values).filter(([name]) => name === 'reason' || form.elements.namedItem(name)?.value !== initial.get(name)));
            for (const [name, previous] of initial) {
              const input = form.elements.namedItem(name), raw = bodySpec.properties[name];
              if (input?.value === '' && previous !== '' && raw?.anyOf?.some(spec => spec.type === 'null')) values[name] = null;
            }
            if (!Object.keys(values).some(name => name !== 'reason')) throw new Error('请先修改员工信息。');
          }
          const versionField = reportConfig ? 'row_version' : 'expected_version';
          values[versionField] = row.row_version;
          if (reportConfig && form.elements.namedItem('cron_expr')?.value === '') values.cron_expr = null;
        }
        let path = op.path;
        for (const match of path.matchAll(/\{([^}]+)\}/g)) {
          const value = row?.[match[1]];
          if (value === undefined || value === null) throw new Error('当前记录缺少编号，请刷新列表后重试。');
          path = path.replace(match[0], encodeURIComponent(value));
        }
        const nextSignature = JSON.stringify({ path, method: op.method, values });
        if (signature !== nextSignature) { signature = nextSignature; pendingKey = createRequestId(); }
        await request(path.slice('/api/v1'.length), { method: op.method, body: values, headers: { 'Idempotency-Key': pendingKey } });
        dialog.close(); await load();
      } catch (error) { response.replaceChildren(node('p', error.message, 'live-error')); }
      finally { busy = false; submit.disabled = cancel.disabled = close.disabled = false; }
    });
    dialog.showModal();
  }
  await load();
}
