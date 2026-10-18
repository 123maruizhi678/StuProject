/** Public loading regression: delayed scripts, styles and APIs; every API is mocked. */
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium, expect } from '@playwright/test';
import { createServer } from 'vite';

const routes = ['/admin/accounts.html', '/admin/permissions.html', '/admin/audit.html'];
const titles = ['账号管理', '角色与权限', '操作记录'];
const access = { user_id: 1, identity_type: 'admin', display_name: '模拟管理员', roles: ['admin'], permissions: [],
  navigation: { routes: Object.fromEntries(routes.map((route, i) => [route, { title: titles[i], module: 'admin_workspace' }])),
    modules: [{ id: 'admin_workspace', title: '平台管理', entry: routes[0], pages: routes.map((route, i) => ({ route, title: titles[i] })) }] } };
const schema = { paths: { '/api/v1/enterprise/employees': { get: {} }, '/api/v1/enterprise/operation-logs': { get: {} },
  '/api/v1/agent/chat': { post: { requestBody: { content: { 'application/json': { schema: { type: 'object', properties: { message: { type: 'string' } }, required: ['message'] } } } } } },
}, components: { schemas: {} } };
const publicAccess = { navigation: { routes: { '/agent/agent.html': { module: 'agent_center' } },
  modules: [{ id: 'agent_center', title: '客服咨询', entry: '/agent/agent.html', pages: [{ route: '/agent/agent.html', title: '智能咨询' }] }] } };
const adminSchema = { paths: { '/api/v1/admin/accounts': { get: {} } }, components: { schemas: {} } };
const server = await createServer({ configFile: 'vite.config.mjs', server: { host: '127.0.0.1', port: 4187, strictPort: true, open: false } });
await server.listen();
let browser;
const gates = new Map();
function hold(key) {
  let release;
  const promise = new Promise(resolve => { release = resolve; });
  gates.set(key, promise);
  return () => { gates.delete(key); release(); };
}
const waitGate = async key => { const pending = gates.get(key); if (pending) await pending; };
try {
  browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
  await context.addInitScript(() => {
    if (!sessionStorage.getItem('stuproject.auth.session') && !sessionStorage.getItem('loading-test-logged-out')) {
      sessionStorage.setItem('stuproject.auth.session', JSON.stringify({ accessToken: 'fictional-loading-token', expiresAt: Date.now() + 3600000,
        identity: { identityType: 'admin', userId: 1, displayName: '模拟管理员' } }));
    }
  });
  const requests = [], errors = [];
  let currentAccess = structuredClone(access), unauthorized = false;
  await context.route('**/js/workspace/layout.js', async route => { await waitGate('script'); await route.continue(); });
  await context.route('**/css/workspace/live.css', async route => { await waitGate('style'); await route.continue(); });
  await context.route('**/openapi.json', route => route.fulfill({ json: schema }));
  await context.route('**/api/**', async route => {
    const req = route.request(), path = new URL(req.url()).pathname;
    requests.push({ path, method: req.method() });
    assert.equal(req.method(), 'GET', 'Loading checks must not issue business mutations');
    const ok = data => route.fulfill({ json: { code: 0, data } });
    if (path === '/api/v1/auth/public-access') return ok(publicAccess);
    if (path === '/api/v1/auth/me/access') {
      await waitGate('access');
      if (unauthorized) return route.fulfill({ status: 401, json: { code: 401, message: '模拟登录过期', data: null } });
      return ok(currentAccess);
    }
    if (path === '/api/v1/admin/openapi.json') return route.fulfill({ json: adminSchema });
    if (path === '/api/v1/admin/accounts/options') return ok({ positions: {}, departments: [] });
    if (path === '/api/v1/admin/accounts') { await waitGate('data'); return ok({ items: [{ username: '模拟账号', identity_type: 'admin' }], total: 1 }); }
    if (path === '/api/v1/enterprise/employees') { await waitGate('employees'); return ok({ items: [{ employee_id: 7, full_name: '模拟员工', employee_no: 'TEST-007', position_title: '顾问', status: 'active', row_version: 1 }], total: 1 }); }
    if (path === '/api/v1/enterprise/operation-logs') return ok({ items: [], total: 0 });
    return route.abort('blockedbyclient');
  });
  const page = await context.newPage(); page.on('pageerror', error => errors.push(error.message));
  const accessCount = () => requests.filter(item => item.path === '/api/v1/auth/me/access').length;
  const ready = () => page.locator('html[data-page-ready=true]').waitFor();
  const releaseScript = hold('script'), releaseAccess = hold('access'), releaseData = hold('data'), releaseStyle = hold('style');
  await page.goto('http://127.0.0.1:4187' + routes[0], { waitUntil: 'commit' });
  await page.locator('.workspace-main').waitFor({ state: 'attached' });
  await expect.poll(() => page.evaluate(() => Boolean(document.querySelector('link[href*="layout.css"]')?.sheet))).toBe(true);
  await expect(page.locator('.workspace-main>.page-heading')).toBeHidden();
  await expect(page.locator('.rail-scroll')).toBeHidden();
  assert.equal(accessCount(), 0, 'Static sample content is hidden even before the deferred script runs');
  releaseScript();
  await expect.poll(accessCount).toBe(1);
  await expect(page.locator('.workspace-main>.page-heading')).toBeHidden();
  releaseAccess();
  await expect(page.locator('.rail-scroll')).toBeVisible();
  await expect.poll(() => requests.some(item => item.path === '/api/v1/admin/accounts')).toBe(true);
  await expect(page.locator('.workspace-main>.page-heading')).toBeHidden();
  await expect(page.locator('.user-name')).toHaveText('模拟管理员');
  await mkdir('.runtime/loading-review', { recursive: true });
  await page.screenshot({ path: '.runtime/loading-review/pending-data.png' });
  releaseData();
  await page.locator('html[data-live-ready=true]').waitFor();
  assert.equal(await page.locator('html').getAttribute('data-page-ready'), null, 'Content remains behind skeleton until its stylesheet is ready');
  releaseStyle(); await ready();
  await expect(page.locator('.admin-list')).toBeVisible();
  await expect(page.locator('.workspace-main')).toHaveAttribute('aria-busy', 'false');
  assert.equal(accessCount(), 1, 'Navigation and page content reuse one fresh authorization request');

  // An unchanged permission response keeps the exact same sidebar nodes and emits no duplicate update.
  await page.evaluate(() => {
    window.originalMenuButton = document.querySelector('.rail-scroll>button');
    window.navMutations = 0; window.navUpdates = 0;
    new MutationObserver(records => { window.navMutations += records.length; }).observe(document.querySelector('.rail-scroll'), { childList: true, subtree: true });
    window.addEventListener('navigation:updated', () => window.navUpdates++);
  });
  const refreshed = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/auth/me/access');
  await page.evaluate(() => window.dispatchEvent(new Event('focus'))); await refreshed;
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)));
  assert.equal(await page.evaluate(() => window.originalMenuButton === document.querySelector('.rail-scroll>button')), true);
  assert.equal(await page.evaluate(() => window.navMutations), 0);
  assert.equal(await page.evaluate(() => window.navUpdates), 0);

  // Cached navigation is displayed during the next page's live permission check, without exposing content.
  await page.locator('.rail-scroll>button').click(); await page.locator('.rail-scroll>button').click();
  const nextCount = accessCount(), releaseNextAccess = hold('access');
  await page.locator('.rail-scroll a[href="/admin/permissions.html"]').click({ noWaitAfter: true });
  await expect.poll(accessCount).toBe(nextCount + 1);
  await page.locator('html[data-navigation-ready=true]').waitFor();
  await expect(page.locator('.rail-scroll')).toBeVisible();
  await expect(page.locator('.rail-scroll>button')).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('.workspace-main>.page-heading')).toBeHidden();
  const contentCallsBefore = requests.filter(item => item.path === '/api/v1/enterprise/employees').length;
  assert.equal(contentCallsBefore, 0);
  releaseNextAccess(); await ready();
  assert.equal(accessCount(), nextCount + 1);
  await expect(page.locator('.admin-list')).toContainText('模拟员工');
  await page.screenshot({ path: '.runtime/loading-review/ready.png' });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.locator('[data-menu]').click(); await expect(page.locator('body')).toHaveClass(/rail-open/);
  await page.keyboard.press('Escape'); await expect(page.locator('body')).not.toHaveClass(/rail-open/);
  await page.screenshot({ path: '.runtime/loading-review/mobile-ready.png' });
  await page.setViewportSize({ width: 1440, height: 1000 });

  // Revocation during a slow business read must not be undone by the final layout render.
  const employeeReads = requests.filter(item => item.path === '/api/v1/enterprise/employees').length;
  const releaseEmployees = hold('employees');
  await page.goto('http://127.0.0.1:4187' + routes[1], { waitUntil: 'domcontentloaded' });
  await expect.poll(() => requests.filter(item => item.path === '/api/v1/enterprise/employees').length).toBe(employeeReads + 1);
  currentAccess = structuredClone(access); delete currentAccess.navigation.routes[routes[1]];
  const revoked = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/auth/me/access');
  await page.evaluate(() => window.dispatchEvent(new Event('focus'))); await revoked;
  await expect(page.locator('.workspace-main')).toContainText('暂无访问权限');
  releaseEmployees();
  await page.locator('html[data-live-ready=true]').waitFor(); await ready();
  await expect(page.locator('.rail-scroll a[href="/admin/permissions.html"]')).toHaveCount(0);
  await expect(page.locator('.workspace-main')).toContainText('暂无访问权限');

  // A revoked route shown by the preview cannot start a business read before fresh authorization.
  currentAccess = structuredClone(access); delete currentAccess.navigation.routes[routes[2]];
  const releaseDeniedAccess = hold('access');
  await page.goto('http://127.0.0.1:4187' + routes[2], { waitUntil: 'domcontentloaded' });
  await page.locator('html[data-navigation-ready=true]').waitFor();
  await expect(page.locator('.workspace-main>.page-heading')).toBeHidden();
  releaseDeniedAccess(); await ready();
  await expect(page.locator('.workspace-main')).toContainText('暂无访问权限');
  assert.equal(requests.filter(item => item.path === '/api/v1/enterprise/operation-logs').length, 0);
  await expect(page.locator('.rail-scroll a[href="/admin/audit.html"]')).toHaveCount(0);

  // A failed authorization request shows a usable error instead of an endless loading skeleton.
  await context.route('**/api/v1/auth/me/access', route => route.fulfill({ status: 503, json: { code: 503, message: '模拟权限服务暂不可用', data: null } }));
  await page.goto('http://127.0.0.1:4187' + routes[0]); await ready();
  await expect(page.locator('.workspace-main')).toContainText('暂时无法读取访问权限');
  await expect(page.getByRole('button', { name: '重新检查权限' })).toBeVisible();
  await context.unroute('**/api/v1/auth/me/access');

  unauthorized = true;
  await page.evaluate(() => sessionStorage.setItem('loading-test-logged-out', 'true'));
  await page.goto('http://127.0.0.1:4187' + routes[0]);
  await page.waitForURL('**/common/login.html');
  await ready();
  assert.equal(await page.evaluate(() => sessionStorage.getItem('stuproject.auth.session')), null);
  await page.goto('http://127.0.0.1:4187/index.html');
  await page.getByRole('button', { name: '打开客服咨询' }).click();
  const frame = page.frameLocator('#support-frame');
  await expect(frame.locator('html[data-page-ready=true]')).toHaveCount(1);
  await expect(frame.locator('.live-section')).toBeVisible();
  await expect(frame.locator('.app-rail')).toBeHidden();
  await expect(frame.locator('.support-tabs')).toContainText('智能咨询');
  assert.deepEqual(errors, []);
  console.log('PASS: no sample flash, stable cached navigation, one access request per page, no redundant sidebar rebuild, delayed stylesheet/data, revocation, failure and logout. All APIs mocked.');
} finally { for (const key of [...gates.keys()]) gates.delete(key); await browser?.close(); await server.close(); }
