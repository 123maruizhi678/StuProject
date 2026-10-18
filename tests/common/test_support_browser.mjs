/** 首页客服容器与只读个人中心回归；业务响应均采用虚构数据。 */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect } from '@playwright/test';
import { createServer } from 'vite';
const python = process.env.STUPROJECT_PYTHON || (existsSync('D:/anaconda3/envs/SST/python.exe') ? 'D:/anaconda3/envs/SST/python.exe' : 'python');
const generated = spawnSync(python, ['-m', 'tests.common.navigation_fixtures'], { encoding: 'utf8', windowsHide: true,
  env: { ...process.env, PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1',
    PYTHONPATH: [process.cwd(), path.resolve('.runtime/backend-deps'), process.env.PYTHONPATH].filter(Boolean).join(path.delimiter) } });
assert.equal(generated.status, 0, generated.stderr);
const fixtures = JSON.parse(generated.stdout);
const schema = { paths: {
  '/api/v1/agent/chat': { post: { requestBody: { content: { 'application/json': { schema: {
    type: 'object', properties: { message: { type: 'string' } }, required: ['message'],
  } } } } } },
  '/api/v1/agent/courses': { get: {} }, '/api/v1/agent/events': { get: {} }, '/api/v1/agent/faq': { get: {} },
}, components: { schemas: {} } };
const server = await createServer({ configFile: 'vite.config.mjs', server: { host: '127.0.0.1', port: 4174, strictPort: true, open: false } });
await server.listen();
const base = 'http://127.0.0.1:4174';
const browser = await chromium.launch({ channel: 'msedge', headless: true });
await mkdir('.runtime/support-review', { recursive: true });
try {
  for (const role of ['public', 'admin', 'employee_admin', 'teacher', 'student', 'customer']) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
    const access = structuredClone(fixtures[role]), errors = [], requests = [];
    if (role !== 'public') await context.addInitScript(identity => {
      if (!sessionStorage.getItem('stuproject.auth.session')) sessionStorage.setItem('stuproject.auth.session', JSON.stringify({
        accessToken: 'fictional-token', expiresAt: Date.now() + 3600000,
        identity: { displayName: identity.display_name, identityType: identity.identity_type },
      }));
    }, access);
    await context.route('**/openapi.json', route => route.fulfill({ json: schema }));
    await context.route('**/api/**', route => {
      const request = route.request(), pathname = new URL(request.url()).pathname;
      requests.push(pathname);
      const send = (data, status = 200) => route.fulfill({ status, json: { code: status === 200 ? 0 : status, message: status === 200 ? 'ok' : '保存失败，请重试', data } });
      if (pathname.endsWith('/openapi.json')) return route.fulfill({ json: schema });
      if (pathname.endsWith('/auth/public-access')) return send(fixtures.public);
      if (pathname.endsWith('/auth/me/access')) {
        assert.equal(request.headers().authorization, 'Bearer fictional-token');
        return send(access);
      }
      if (pathname.endsWith('/auth/me/profile')) {
        assert.fail('只读个人中心不能发起资料修改请求');
      }
      if (pathname.endsWith('/agent/chat')) return send({ answer: '虚构客服回复' });
      if (pathname.includes('/agent/')) return send({ items: [{ title: '虚构客服资料' }], total: 1 });
      return send({ items: [], total: 0, unread_count: 0 });
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + '/index.html');
    assert.equal(await page.locator('#support-frame').getAttribute('src'), null, '点击前不加载客服业务页面');
    await page.getByRole('button', { name: '打开客服咨询' }).click();
    const frame = page.frameLocator('#support-frame');
    await expect(frame.locator('html[data-live-ready=true]')).toHaveCount(1);
    await expect(frame.locator('.support-tabs a')).toHaveText(['智能咨询', '课程与项目', '活动与讲座', '常见问题']);
    await expect(frame.locator('.app-rail')).toBeHidden();
    await expect(frame.locator('.app-topbar')).toBeHidden();
    assert.ok((await frame.locator('a:visible').evaluateAll(links => links.map(link => new URL(link.href).pathname))).every(route => route.startsWith('/agent/') || route.endsWith('/agent.html')));
    await frame.locator('[name=message]').fill('虚构咨询问题');
    await frame.getByRole('button', { name: '确认提交', exact: true }).click();
    await expect(frame.locator('.live-result')).toContainText('虚构客服回复');
    await frame.getByRole('link', { name: '课程与项目', exact: true }).click();
    await expect(frame.locator('.live-result')).toContainText('虚构客服资料');
    await frame.getByRole('link', { name: '活动与讲座', exact: true }).click();
    await expect(frame.locator('.live-result')).toContainText('虚构客服资料');
    await frame.getByRole('link', { name: '常见问题', exact: true }).click();
    await expect(frame.locator('.live-result')).toContainText('虚构客服资料');
    await page.screenshot({ path: `.runtime/support-review/${role}-desktop.png` });
    await frame.locator('body').press('Escape');
    await expect(page.locator('#support-dialog')).not.toBeVisible();
    await expect(page.locator('#support-open')).toBeFocused();
    await page.locator('#support-open').click();
    await expect(frame.locator('.support-tabs [aria-current]')).toHaveText('常见问题');
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 844 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      assert.ok(await frame.locator('html').evaluate(element => element.scrollWidth <= innerWidth));
      await expect(page.locator('#support-close')).toBeVisible();
      await page.screenshot({ path: `.runtime/support-review/${role}-${width}.png` });
    }
    await page.locator('#support-close').click();
    await page.setViewportSize({ width: 1440, height: 1000 });
    assert.ok(page.url().endsWith('/index.html'));
    if (role !== 'public') {
      assert.equal(await page.evaluate(() => JSON.parse(sessionStorage.getItem('stuproject.auth.session')).accessToken), 'fictional-token');
      await page.goto(base + '/common/account.html');
      await expect(page.locator('#account-name')).toHaveText(access.display_name);
      await expect(page.locator('.rail-scroll .sub')).toHaveCount(0);
      await expect(page.locator('.rail-scroll a[aria-current]')).toHaveText('个人中心');
      await expect(page.locator('#main-content a')).toHaveCount(0);
      const agentTitle = fixtures.admin.navigation.modules.find(module => module.id === 'agent_center').title;
      await expect(page.locator('.rail-scroll').getByRole('button', { name: agentTitle, exact: true })).toHaveCount(['admin', 'employee_admin'].includes(role) ? 1 : 0);
      await expect(page.locator('#main-content input, #main-content textarea, #main-content select, #main-content form, #main-content button')).toHaveCount(0);
      await expect(page.locator('.user-name')).toHaveText(access.display_name);
      await page.reload();
      await expect(page.locator('#account-name')).toHaveText(access.display_name);
      await page.screenshot({ path: `.runtime/support-review/${role}-account-readonly.png`, fullPage: true });
      await page.goto(base + '/index.html');
      await expect(page.locator('.nav-login')).toHaveText(access.display_name);
      await page.locator('.nav-login').click();
      await page.waitForURL(access.identity_type === 'admin' ? '**/admin/accounts.html' : '**/common/workspace.html');
    }
    assert.ok(!requests.some(route => /^\/api\/v1\/(enterprise|student|customer|report)\//.test(route)));
    assert.deepEqual(errors, []);
    await context.close();
    console.log(role + ': support-only panel, chat, tabs, identity, desktop/mobile and profile passed');
  }
} finally { await browser.close(); await server.close(); }
