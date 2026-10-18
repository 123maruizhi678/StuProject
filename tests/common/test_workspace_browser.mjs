/** 公共工作台回归：真实权限计算 + 虚构账号/SQLite，不修改真实业务数据。 */
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
const server = await createServer({ configFile: 'vite.config.mjs', server: { host: '127.0.0.1', port: 4174, strictPort: true, open: false } });
await server.listen();
const base = 'http://127.0.0.1:4174';
const browser = await chromium.launch({ channel: 'msedge', headless: true });
await mkdir('.runtime/workspace-review', { recursive: true });
const results = [];
const moduleSchema = { paths: {
  '/api/v1/customer/source': { get: {}, post: {} },
  '/api/v1/customer/source/{source_id}': { get: {} },
  '/api/v1/customer/source/{source_id}/file': { get: {} },
  '/api/v1/customer/source/{source_id}/parse': { post: {} },
  '/api/v1/customer/result': { get: {} }, '/api/v1/customer/result/{result_id}': { get: {} },
  '/api/v1/customer/judge': { post: {} }, '/api/v1/customer/judge/batch': { post: {} },
  '/api/v1/customer/rule': { get: {}, put: {} }, '/api/v1/customer/product': { get: {} },
  '/api/v1/report/list': { get: {} }, '/api/v1/report/{report_record_id}': { get: {} },
  '/api/v1/report/generate': { post: { requestBody: { content: { 'application/json': { schema: {
    type: 'object', required: ['report_code'], properties: { report_code: { type: 'string' },
      start_time: { type: 'string', format: 'date-time' }, end_time: { type: 'string', format: 'date-time' } },
  } } } } } }, '/api/v1/report/configs': { get: {} },
  '/api/v1/report/configs/{report_code}': { put: {} },
}, components: { schemas: {} } };
try {
  for (const role of Object.keys(fixtures).filter(role => role !== 'public')) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
    let active = role;
    const requests = [], errors = [];
    const reportAttempts = [];
    await context.route('**/openapi.json', route => route.fulfill({ json: moduleSchema }));
    await context.route('**/api/**', route => {
      const request = route.request(), pathname = new URL(request.url()).pathname;
      requests.push(pathname);
      if (pathname.endsWith('/auth/login')) {
        return route.fulfill({ json: { code: 0, data: { access_token: 'fictional-token', token_type: 'bearer', expires_in: 3600,
          user_id: fixtures[role].user_id, identity_type: fixtures[role].identity_type, display_name: fixtures[role].display_name } } });
      }
      if (pathname.endsWith('/auth/me/access')) return route.fulfill({ json: { code: 0, data: fixtures[active] } });
      if (pathname.endsWith('/auth/public-access')) return route.fulfill({ json: { code: 0, data: fixtures.public } });
      if (pathname.endsWith('/report/generate') && request.method() === 'POST') {
        reportAttempts.push({ key: request.headers()['idempotency-key'], body: request.postDataJSON() });
        return route.fulfill({ json: reportAttempts.length === 1 ? { code: 503, message: '模拟生成失败，请重试', data: null }
          : { code: 0, data: { report_record_id: 7, status: 'pending' } } });
      }
      if (pathname.endsWith('/report/list')) return route.fulfill({ json: { code: 0, data: {
        items: [{ report_record_id: 7, report_name: '虚构报告', status: 'success' }], total: 1,
      } } });
      if (pathname.endsWith('/report/7')) return route.fulfill({ json: { code: 0, data: {
        report_record_id: 7, report_content: '虚构报告正文', status: 'success',
      } } });
      if (pathname.endsWith('/common/announcements') || pathname.endsWith('/common/notifications')) return route.fulfill({ json: { code: 0, data: { items: [], total: 0, unread_count: 0 } } });
      if (pathname.endsWith('/openapi.json')) return route.fulfill({ json: { paths: {}, components: { schemas: {} } } });
      return route.fulfill({ json: { code: 0, data: {} } });
    });
    const page = await context.newPage();
    const platformAdmin = fixtures[role].identity_type === 'admin';
    const entry = platformAdmin ? '/admin/accounts.html' : '/common/workspace.html';
    const ready = platformAdmin ? 'html[data-live-ready=true]' : 'html[data-workspace-ready=true]';
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + '/common/workspace.html');
    await page.waitForURL('**/common/login.html?next=**');
    if (role === 'admin') {
      await page.goto(base + '/common/password-reset.html');
      await expect(page.getByRole('heading', { name: '需要账号协助？', exact: true })).toBeVisible();
      assert.ok(page.url().endsWith('/common/password-reset.html'));
      await page.goto(base + '/common/login.html');
    }
    await page.locator('[name=username]').fill('fictional-' + role);
    await page.locator('[name=password]').fill('Fictional!2026');
    await page.getByRole('button', { name: '登录', exact: true }).click();
    await page.waitForURL('**' + entry);
    await page.locator(ready).waitFor();
    const expected = fixtures[role].navigation.modules.map(module => module.id).sort();
    if (!platformAdmin) await page.locator('html[data-notification-ready=true]').waitFor();
    assert.equal(await page.locator('.workspace-module-card').count(), 0);
    if (!platformAdmin) {
      await expect(page.locator('#public-title')).toHaveText('公共通知');
      await expect(page.locator('#personal-title')).toHaveText('与我相关');
    }
    const sidebar = await page.locator('.rail-scroll > .rail-link:not(.sub)').allTextContents();
    const admin = fixtures[role].identity_type === 'admin' || fixtures[role].roles.includes('admin');
    assert.deepEqual(sidebar, [...(platformAdmin ? [] : ['通知中心']), ...fixtures[role].navigation.modules.filter(module => module.id !== 'agent_center' || admin).map(module => module.title)]);
    assert.equal(await page.locator('.rail-label, .rail-foot').count(), 0);
    if (role === 'admin') await page.screenshot({ path: '.runtime/workspace-review/admin-desktop.png', fullPage: true });
    await page.locator('.rail-brand').click();
    await expect(page.locator('.nav-login')).toHaveText(fixtures[role].display_name);
    await page.locator('.nav-login').click();
    await page.waitForURL('**' + entry);
    await page.locator(ready).waitFor();
    if (role === 'student' || role === 'customer') {
      const start = requests.length;
      await page.goto(base + '/customer/customer.html');
      await expect(page.locator('#main-content')).toContainText('暂无访问权限');
      assert.ok(!requests.slice(start).some(url => url.startsWith('/api/v1/customer/')));
      assert.equal(await page.locator('.rail-scroll a[href="/admin/accounts.html"]').count(), 0);
      await page.goto(base + '/common/account.html');
      await expect(page.locator('#account-name')).toHaveText(fixtures[role].display_name);
      await expect(page.locator('#main-content input, #main-content form, #main-content button')).toHaveCount(0);
      await expect(page.locator('.rail-scroll .sub')).toHaveCount(0);
      await expect(page.locator('.rail-scroll a[aria-current=page]')).toHaveText('个人中心');
      await expect(page.locator('#main-content a')).toHaveCount(0);
      assert.ok(!requests.slice(start).includes('/api/v1/enterprise/me/permissions'));
      await page.goto(base + '/common/sitemap.html');
      await page.locator('[data-map-search]').fill('客户');
      assert.equal(await page.locator('.map-link[href="../customer/customer.html"]:visible').count(), 0);
      await page.locator('[data-map-search]').fill('');
      assert.equal(await page.locator('.map-link[href="../admin/accounts.html"]:visible').count(), 0);
      await page.goto(base + '/common/workspace.html');
    }
    if (role === 'manager' || role === 'admin') {
      for (const route of ['/customer/customer.html', '/customer/sources.html', '/customer/results.html',
        '/customer/rules.html', '/customer/products.html', '/report/report.html', '/report/list.html']) {
        await page.goto(base + route);
        await page.locator('html[data-live-ready=true]').waitFor();
        await expect(page.locator('.live-error')).toHaveCount(0);
        if (route.startsWith('/report/')) {
          await expect(page.locator('#main-content .data-table')).toContainText('虚构报告');
          if (role === 'admin') await expect(page.locator('#main-content a[href="generate.html"]:visible').first()).toBeVisible();
          continue;
        }
        assert.ok(await page.locator('[data-operation^="GET "]').count() > 0, route + ' 应有查询');
        const writes = page.locator('[data-operation^="POST "], [data-operation^="PUT "]');
        if (role === 'manager') {
          await expect(writes).toHaveCount(0);
          await expect(page.locator('[data-operation$="/file"]')).toHaveCount(0);
          await expect(page.locator('.rail-scroll a[href="/customer/extract.html"], .rail-scroll a[href="/report/generate.html"], .rail-scroll a[href="/report/configs.html"]')).toHaveCount(0);
        } else if (['/customer/customer.html', '/customer/results.html', '/customer/rules.html', '/report/report.html'].includes(route)) {
          assert.ok(await writes.count() > 0, '管理员原有写入操作应保留');
        }
      }
      if (role === 'manager') {
        await page.goto(base + '/customer/source-detail.html');
        await page.locator('html[data-live-ready=true]').waitFor();
        await expect(page.locator('.rail-scroll .sub.active')).toHaveAttribute('href', '/customer/sources.html');
        await expect(page.locator('[data-operation^="POST "], [data-operation$="/file"]')).toHaveCount(0);
        await page.goto(base + '/report/generate.html');
        await expect(page.locator('#main-content')).toContainText('暂无访问权限');
      }
      await page.goto(base + '/report/list.html');
      await page.locator('html[data-live-ready=true]').waitFor();
      await page.getByRole('link', { name: '查看报告', exact: true }).click();
      await page.waitForURL('**/report/detail.html?report_record_id=7');
      await expect(page.locator('.report-md')).toContainText('虚构报告正文');
      await expect(page.locator('.rail-scroll .sub.active')).toHaveAttribute('href', '/report/list.html');
      await page.reload();
      await expect(page.locator('.report-md')).toContainText('虚构报告正文');
      if (role === 'admin') {
        await page.goto(base + '/report/generate.html');
        await page.locator('html[data-live-ready=true]').waitFor();
        await page.locator('#main-content select').selectOption('daily_report');
        await page.locator('#main-content input[type=date]').nth(0).fill('2026-10-17');
        await page.locator('#main-content input[type=date]').nth(1).fill('2026-10-18');
        await page.getByRole('button', { name: '提交生成', exact: true }).click();
        await expect(page.locator('.live-error')).toContainText('模拟生成失败');
        await page.getByRole('button', { name: '提交生成', exact: true }).click();
        await expect(page.locator('#main-content .live-status')).toContainText('待生成');
        assert.equal(reportAttempts.length, 2);
        assert.ok(reportAttempts[0].key);
        assert.equal(reportAttempts[0].key, reportAttempts[1].key);
        assert.equal(reportAttempts[1].body.start_time, '2026-10-17T00:00+08:00');
      } else assert.equal(reportAttempts.length, 0);
      await page.goto(base + '/common/workspace.html');
    }
    if (role === 'counselor') {
      await page.setViewportSize({ width: 1440, height: 600 });
      for (const [detail, parent] of [['warning-detail', 'warnings']]) {
        assert.ok(fixtures[role].navigation.routes['/enterprise/' + detail + '.html']);
        await page.goto(base + '/enterprise/' + detail + '.html');
        const selected = page.locator('.rail-scroll .sub.active');
        await expect(selected).toHaveAttribute('href', '/enterprise/' + parent + '.html');
        await expect(selected).toHaveAttribute('aria-current', 'location');
        await expect.poll(() => page.evaluate(() => {
          const element = document.querySelector('.rail-scroll .sub.active');
          if (!element) return false;
          const item = element.getBoundingClientRect(), rail = element.parentElement.getBoundingClientRect();
          return item.top >= rail.top - 1 && item.bottom <= rail.bottom + 1;
        }), { message: '当前目录应位于侧栏可见区域' }).toBe(true);
      }
      await page.setViewportSize({ width: 1440, height: 1000 });
      await page.goto(base + '/common/workspace.html');
    }
    if (role === 'teacher') {
      await page.goto(base + '/enterprise/enterprise.html');
      await page.locator('html[data-live-ready=true]').waitFor();
      assert.equal(await page.locator('.rail-scroll a[href="/enterprise/scores.html"]').count(), 1);
      assert.equal(await page.locator('.rail-scroll a[href="/enterprise/customers.html"]').count(), 0);
      active = 'consultant';
      await page.evaluate(() => window.dispatchEvent(new Event('focus')));
      await expect(page.locator('.rail-scroll a[href="/enterprise/customers.html"]')).toHaveCount(1);
      assert.equal(await page.locator('.rail-scroll a[href="/enterprise/scores.html"]').count(), 0);
      active = 'teacher';
      await page.goto(base + '/enterprise/scores.html');
      await page.locator('html[data-live-ready=true]').waitFor();
      active = 'consultant';
      await page.evaluate(() => window.dispatchEvent(new Event('focus')));
      await expect(page.locator('#main-content')).toContainText('暂无访问权限');
      active = role;
      await page.goto(base + '/common/workspace.html');
    }
    if (role === 'student') {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.locator('html[data-workspace-ready=true]').waitFor();
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({ path: '.runtime/workspace-review/student-mobile.png', fullPage: true });
      await page.locator('[data-menu]').click();
      await expect(page.locator('.rail-scroll')).toBeVisible();
      await page.keyboard.press('Escape');
    }
    await page.getByRole('button', { name: '退出登录', exact: true }).click();
    await page.waitForURL('**/common/login.html');
    assert.equal(await page.evaluate(() => sessionStorage.getItem('stuproject.auth.session')), null);
    assert.deepEqual(errors, []);
    await context.close();
    results.push(role + ': passed');
  }
  console.log(results.join('\n'));
} finally { await browser.close(); await server.close(); }
