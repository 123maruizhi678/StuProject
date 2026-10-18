/** Platform management regression. Every API request is intercepted; no real database is used. */
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium, expect } from '@playwright/test';
import { createServer } from 'vite';

const nullable = spec => ({ anyOf: [spec, { type: 'null' }] });
const string = { type: 'string' }, integer = { type: 'integer', minimum: 1 };
const body = (properties, required = []) => ({ requestBody: { content: { 'application/json': { schema: { type: 'object', properties, required } } } } });
const mutation = { expected_version: nullable(integer), reason: nullable({ type: 'string', minLength: 1 }) };
const publicSchema = { components: { schemas: {} }, paths: {
  '/api/v1/auth/me/access': { get: {} }, '/api/v1/enterprise/me/permissions': { get: {} },
  '/api/v1/enterprise/employees': { get: {}, post: body({ full_name: string }, ['full_name']) },
  '/api/v1/enterprise/employees/{employee_id}': { get: {}, put: body({ ...mutation,
    full_name: nullable({ type: 'string', minLength: 1 }), position_title: nullable(string),
    work_email: nullable(string), status: nullable({ type: 'string', enum: ['active', 'disabled', 'left'] }),
    left_date: nullable({ type: 'string', format: 'date' }),
  }) },
  '/api/v1/enterprise/employees/{employee_id}/roles': { put: body({ ...mutation, role_codes: { type: 'array', items: string } }, ['role_codes', 'reason']) },
  '/api/v1/enterprise/operation-logs': { get: {} },
  '/api/v1/report/configs': { get: {} },
  '/api/v1/report/configs/{report_code}': { put: body({ row_version: integer, report_name: string,
    cron_expr: nullable(string), enabled: { type: 'boolean' } }, ['row_version', 'report_name', 'enabled']) },
} };
const adminSchema = { components: { schemas: {} }, paths: {
  '/api/v1/admin/accounts': { get: {} }, '/api/v1/admin/accounts/options': { get: {} },
  '/api/v1/auth/register': { post: body({ username: { type: 'string', minLength: 1 } }, ['username']) },
} };
const routes = ['/admin/accounts.html', '/admin/permissions.html', '/admin/audit.html', '/admin/settings.html'];
const titles = ['账号管理', '角色与权限', '操作记录', '平台设置'];
const access = { user_id: 1, display_name: '测试管理员', identity_type: 'admin', roles: ['admin'],
  permissions: ['report.config.read', 'report.config.write'],
  navigation: { routes: Object.fromEntries(routes.map(route => [route, { title: '平台管理', module: 'admin_workspace' }])),
    modules: [{ id: 'admin_workspace', title: '平台管理', entry: routes[0], pages: routes.map((route, i) => ({ title: titles[i], route })) }] } };
const server = await createServer({ configFile: 'vite.config.mjs', server: { host: '127.0.0.1', port: 4186, strictPort: true, open: false } });
let browser;
await server.listen();
try {
  browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.addInitScript(() => sessionStorage.setItem('stuproject.auth.session', JSON.stringify({ accessToken: 'fictional-admin', expiresAt: Date.now() + 3600000 })));
  let employee = { employee_id: 7, employee_no: 'TEST-007', full_name: '模拟员工', department_id: 3, position_title: '顾问', work_email: 'test@example.invalid', status: 'active', row_version: 4 };
  let config = { report_code: 'daily_report', report_name: '模拟日报', cron_expr: '0 8 * * *', enabled: true, row_version: 2 };
  let failEmployee = false;
  const writes = [], reads = [], errors = [];
  await context.route('**/openapi.json', route => route.fulfill({ json: publicSchema }));
  await context.route('**/api/**', async route => {
    const req = route.request(), url = new URL(req.url()), path = url.pathname;
    const ok = data => route.fulfill({ json: { code: 0, data } });
    if (req.method() === 'GET') {
      reads.push(path + url.search);
      if (path === '/api/v1/auth/me/access') return ok(access);
      if (path === '/api/v1/admin/openapi.json') return route.fulfill({ json: adminSchema });
      if (path === '/api/v1/admin/accounts/options') return ok({ positions: { 顾问: ['employee', 'consultant'], 主管: ['employee', 'manager'] }, departments: [{ department_id: 3, department_name: '模拟部门' }] });
      if (path === '/api/v1/admin/accounts') return ok({ items: [{ username: '模拟账号', identity_type: 'employee', full_name: '模拟员工', status: 'active' }], total: 11 });
      if (path === '/api/v1/enterprise/employees') return ok({ items: [employee], total: 1 });
      if (path === '/api/v1/enterprise/operation-logs') return ok({ items: [{ operation_log_id: 1, action_code: '模拟操作', operation_status: 'succeeded' }], total: 1 });
      if (path === '/api/v1/report/configs') return ok([config]);
      return route.abort('blockedbyclient');
    }
    const payload = req.postDataJSON(); writes.push({ path, method: req.method(), payload, key: req.headers()['idempotency-key'] });
    if (path === '/api/v1/enterprise/employees/7' && failEmployee) {
      failEmployee = false;
      return route.fulfill({ json: { code: 409, message: '模拟版本冲突，请刷新后重试', data: null } });
    }
    if (path === '/api/v1/enterprise/employees/7' || path === '/api/v1/enterprise/employees/7/roles') {
      const changes = Object.fromEntries(Object.entries(payload).filter(([name]) => !['expected_version', 'reason', 'role_codes'].includes(name)));
      employee = { ...employee, ...changes, row_version: employee.row_version + 1 };
    }
    if (path === '/api/v1/report/configs/daily_report') config = { ...config, ...payload, row_version: config.row_version + 1 };
    return ok({});
  });
  const page = await context.newPage(); page.on('pageerror', error => errors.push(error.message));
  const open = async route => {
    await page.goto('http://127.0.0.1:4186' + route);
    await page.locator('html[data-live-ready=true]').waitFor();
    await expect(page.locator('.admin-list tbody tr').first()).toBeVisible();
    await expect(page.locator('.live-error')).toHaveCount(0);
  };
  const save = async () => {
    await page.getByRole('dialog').getByRole('button', { name: '保存', exact: true }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.locator('.admin-list .live-status')).toHaveCount(0);
  };
  await mkdir('.runtime/admin-review', { recursive: true });

  await open(routes[0]);
  await expect(page.locator('#main-content [data-operation]')).toHaveCount(1);
  await expect(page.locator('#main-content')).not.toContainText('开户选项');
  await expect(page.locator('#main-content')).not.toContainText('点击');
  await page.locator('.admin-list tbody tr').click(); await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.locator('.admin-list tbody tr')).not.toHaveAttribute('tabindex', '0');
  const spacing = await page.evaluate(() => document.querySelector('.admin-list-toolbar').getBoundingClientRect().top - document.querySelector('.admin-list>.section-title').getBoundingClientRect().bottom);
  assert.ok(spacing >= 0 && spacing <= 16, 'No empty form action row above create button');
  for (let i = 0; i < 2; i++) {
    await page.getByRole('button', { name: '新增账号', exact: true }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click();
  }
  assert.equal(writes.length, 0, 'Opening dialogs must never submit');
  await page.getByRole('button', { name: '新增账号', exact: true }).click();
  await page.locator('dialog [name=username]').fill('模拟新账号');
  await page.getByRole('dialog').getByRole('button', { name: '确认提交', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  assert.equal(writes.at(-1).path, '/api/v1/auth/register');
  await page.getByRole('button', { name: '下一页', exact: true }).click();
  await expect(page.locator('.live-paging')).toContainText('第 2 页');
  assert.ok(reads.some(url => url === '/api/v1/admin/accounts?limit=10&offset=10'));
  await page.screenshot({ path: '.runtime/admin-review/accounts-desktop.png', fullPage: true });

  await open(routes[1]);
  await expect(page.locator('#main-content [data-operation]')).toHaveCount(1);
  await expect(page.locator('#main-content')).not.toContainText('访问权限');
  await page.locator('.admin-list tbody td').first().click(); await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('button', { name: '新增员工', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click();
  await page.getByRole('button', { name: '编辑员工', exact: true }).click();
  await expect(page.locator('dialog [name=full_name]')).toHaveValue('模拟员工');
  await page.locator('dialog [name=full_name]').fill('更新后员工');
  failEmployee = true;
  await page.getByRole('dialog').getByRole('button', { name: '保存', exact: true }).click();
  await expect(page.locator('dialog .live-error')).toContainText('模拟版本冲突');
  const failed = writes.at(-1);
  await save();
  assert.equal(writes.at(-1).key, failed.key, 'Retry preserves idempotency key');
  assert.deepEqual(writes.at(-1).payload, { full_name: '更新后员工', expected_version: 4 });
  await expect(page.locator('.admin-list')).toContainText('更新后员工');
  await page.getByRole('button', { name: '编辑员工', exact: true }).click();
  await page.locator('dialog [name=work_email]').fill(''); await save();
  assert.deepEqual(writes.at(-1).payload, { work_email: null, expected_version: 5 });
  await page.getByRole('button', { name: '调整角色', exact: true }).click();
  await page.locator('dialog [name=position_title]').selectOption('主管');
  await expect(page.getByRole('dialog')).toContainText('部门主管');
  await page.locator('dialog [name=reason]').fill('模拟职位调整'); await save();
  assert.equal(writes.at(-1).path, '/api/v1/enterprise/employees/7');
  assert.deepEqual(writes.at(-1).payload, { position_title: '主管', reason: '模拟职位调整', expected_version: 6 });
  await page.getByRole('button', { name: '调整角色', exact: true }).click();
  await page.locator('dialog [name=reason]').fill('模拟角色同步'); await save();
  assert.equal(writes.at(-1).path, '/api/v1/enterprise/employees/7/roles');
  assert.deepEqual(writes.at(-1).payload, { role_codes: ['employee', 'manager'], reason: '模拟角色同步', expected_version: 7 });
  await page.screenshot({ path: '.runtime/admin-review/employees-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: '调整角色', exact: true }).click();
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.screenshot({ path: '.runtime/admin-review/roles-mobile.png', fullPage: true });
  await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click();
  await page.setViewportSize({ width: 1440, height: 1000 });

  await open(routes[2]);
  await page.locator('.admin-list tbody tr').click(); await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.locator('.admin-record-actions')).toHaveCount(0);
  await open(routes[3]);
  assert.ok(!reads.some(url => url.startsWith('/api/v1/report/configs?')), 'Config request has no unsupported pagination parameters');
  await page.locator('.admin-list tbody td').first().click(); await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('button', { name: '修改配置', exact: true }).click();
  await expect(page.locator('dialog [name=report_name]')).toHaveValue('模拟日报');
  await page.locator('dialog [name=cron_expr]').fill('');
  await page.locator('dialog [name=enabled]').selectOption('false'); await save();
  assert.deepEqual(writes.at(-1).payload, { report_name: '模拟日报', enabled: false, row_version: 2, cron_expr: null });
  await page.screenshot({ path: '.runtime/admin-review/settings-desktop.png', fullPage: true });
  assert.ok(writes.every(write => write.key));
  assert.ok(!reads.some(url => url.startsWith('/api/v1/enterprise/me/permissions')));
  assert.deepEqual(errors, []);
  console.log('PASS: admin lists, no read-only dialogs, compact toolbar, create/reopen, edit/retry/version, role mapping, pagination, mobile, config update. All APIs mocked.');
} finally { await browser?.close(); await server.close(); }
