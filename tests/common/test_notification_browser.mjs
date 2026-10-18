/** 通知中心交互回归；所有消息和公告写入均为浏览器拦截的虚构数据。 */
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
await mkdir('.runtime/notification-review', { recursive: true });
try {
  for (const role of ['admin', 'student']) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
    await context.addInitScript(identity => sessionStorage.setItem('stuproject.auth.session', JSON.stringify({
      accessToken: 'fictional-token', expiresAt: Date.now() + 3600000,
      identity: { displayName: identity.display_name, identityType: identity.identity_type },
    })), fixtures[role]);
    const read = new Set(), errors = [];
    let readFails = false;
    const announcements = [{ announcement_id: 1, title: '留学服务安排', content: '<script>window.noticeInjected=true</script>\n第二段正文',
      status: 'published', pinned: true, published_at: '2026-10-18T01:00:00Z', expires_at: null, row_version: 1 }];
    const messages = Array.from({ length: 23 }, (_, i) => ({ key: 'business:' + (23 - i), title: (i % 3 === 1 ? '服务回复' : '办理提醒') + (23 - i),
      content: '消息正文内容', kind: ['status', 'reply', 'important'][i % 3], created_at: '2026-10-18T02:00:00Z', read_at: null }));
    await context.route('**/openapi.json', route => route.fulfill({ json: { paths: {
      '/api/v1/student/leave': { get: {} }, '/api/v1/student/leave/{apply_id}': { get: {} },
      '/api/v1/enterprise/customer': { get: {} }, '/api/v1/enterprise/customer/{customer_id}': { get: {} },
    }, components: { schemas: {} } } }));
    await context.route('**/api/**', async route => {
      const request = route.request(), url = new URL(request.url()), pathname = decodeURIComponent(url.pathname);
      const send = (data, status = 200) => route.fulfill({ status, json: { code: status === 200 ? 0 : status, data, message: status === 200 ? 'ok' : '测试错误' } });
      if (pathname.endsWith('/auth/me/access')) return send(fixtures[role]);
      if (pathname.endsWith('/admin/openapi.json')) return route.fulfill({ json: { paths: {}, components: { schemas: {} } } });
      if (pathname.endsWith('/enterprise/customer/31')) return send({ customer_id: 31, full_name: '通知关联客户', row_version: 2 });
      if (pathname.endsWith('/enterprise/customer')) return send({ items: [], total: 0 });
      if (pathname.endsWith('/common/announcements/manage')) return send({ items: announcements.map(item => ({ ...item, key: 'announcement:' + item.announcement_id })), total: announcements.length });
      if (pathname.endsWith('/common/announcements') && request.method() === 'POST') {
        const body = request.postDataJSON();
        const saved = { ...body, announcement_id: announcements.length + 1, row_version: 1, published_at: body.published_at || '2026-10-18T03:00:00Z' };
        announcements.push(saved); return send(saved);
      }
      if (/\/common\/announcements\/\d+$/.test(pathname) && request.method() === 'PATCH') {
        const index = announcements.findIndex(item => item.announcement_id === Number(pathname.split('/').at(-1)));
        const body = request.postDataJSON(); assert.equal(body.expected_version, announcements[index].row_version);
        announcements[index] = { ...announcements[index], ...body, row_version: body.expected_version + 1 };
        return send(announcements[index]);
      }
      if (pathname.endsWith('/common/announcements')) return send({ items: announcements.filter(item => item.status === 'published').map(item => ({ ...item, key: 'announcement:' + item.announcement_id, read_at: read.has('announcement:' + item.announcement_id) ? '2026-10-18T03:00:00Z' : null })), total: announcements.length });
      if (pathname.endsWith('/common/notifications')) {
        const all = messages.map(item => ({ ...item, read_at: read.has(item.key) ? '2026-10-18T03:00:00Z' : null }));
        const filtered = all.filter(item => (url.searchParams.get('unread') !== 'true' || !item.read_at) &&
          (!url.searchParams.get('kind') || item.kind === url.searchParams.get('kind')) &&
          (!url.searchParams.get('q') || item.title.includes(url.searchParams.get('q'))));
        const offset = Number(url.searchParams.get('offset') || 0), limit = Number(url.searchParams.get('limit') || 20);
        return send({ items: filtered.slice(offset, offset + limit), total: filtered.length, unread_count: all.filter(item => !item.read_at).length });
      }
      if (pathname.includes('/common/notifications/')) {
        const parts = pathname.split('/'), reading = parts.at(-1) === 'read', key = parts.at(reading ? -2 : -1);
        const item = key.startsWith('announcement:') ? announcements.find(item => 'announcement:' + item.announcement_id === key) : messages.find(item => item.key === key);
        if (!item) return send(null, 404);
        if (reading) { if (readFails) return send(null, 500); read.add(key); return send({ key, read_at: '2026-10-18T03:00:00Z' }); }
        return send({ ...item, key, kind: key.startsWith('announcement:') ? 'announcement' : item.kind,
          related: key.startsWith('business:') ? (role === 'student'
            ? { route: '/student/leave-detail.html', selection: { apply_id: 77 } }
            : { route: '/enterprise/customer-detail.html', selection: { customer_id: 31 } }) : null });
      }
      return send({});
    });
    const page = await context.newPage(); page.on('pageerror', error => errors.push(error.message));
    const overview = async () => { await page.goto(base + '/common/workspace.html'); await page.locator('html[data-notification-ready=true]').waitFor(); };
    await overview();
    await expect(page.locator('h1')).toHaveText('通知中心');
    assert.equal(await page.locator('.rail-label,.rail-foot,.workspace-module-card').count(), 0);
    assert.equal(await page.locator('#personal-notices .notice-row').count(), 20);
    await page.screenshot({ path: `.runtime/notification-review/${role}-desktop.png`, fullPage: true });
    await page.locator('#notice-next').click(); await expect(page.locator('#notice-page')).toContainText('第 2 页');
    assert.equal(await page.locator('#personal-notices .notice-row').count(), 3);
    await page.locator('#notice-prev').click(); await expect(page.locator('#notice-page')).toContainText('第 1 页');
    await page.locator('#public-notices .notice-row').first().click();
    await expect(page.locator('#detail-status')).toHaveText('已读');
    assert.ok((await page.locator('#detail-body').textContent()).includes('<script>'));
    assert.equal(await page.locator('#detail-body script').count(), 0);
    assert.equal(await page.evaluate(() => window.noticeInjected), undefined);
    await page.getByRole('link', { name: '返回通知中心', exact: true }).click();
    await page.locator('html[data-notification-ready=true]').waitFor();
    await expect(page.locator('#public-notices .notice-read-state').first()).toHaveText('已读');
    await page.locator('#personal-notices .notice-row').first().click();
    await expect(page.locator('#detail-status')).toHaveText('已读');
    await expect(page.locator('.rail-scroll > [aria-current=location]')).toHaveText('通知中心');
    if (role === 'student') {
      await expect(page.locator('#notice-related')).toHaveAttribute('href', '/student/leave-detail.html');
      await page.locator('#notice-related').click();
      await page.locator('html[data-live-ready=true]').waitFor();
      await expect(page.locator('.live-error')).toHaveCount(0);
      await expect(page.locator('[name=apply_id]')).toHaveValue('77');
      assert.equal(await page.evaluate(() => JSON.parse(sessionStorage.getItem('stuproject.live.selection')).apply_id), 77);
      const directory = page.locator('.rail-scroll .sub.active');
      await expect(directory).toHaveText('请假办理');
      await expect(directory).toHaveAttribute('href', '/student/leave.html');
      await expect(directory).toHaveAttribute('aria-current', 'location');
      await expect(page.locator('.rail-scroll > [aria-expanded=true]')).toHaveCount(1);
      await page.reload();
      await page.locator('html[data-live-ready=true]').waitFor();
      await expect(directory).toHaveText('请假办理');
      await page.goBack();
      await expect(page.locator('#detail-status')).toHaveText('已读');
      await page.goForward();
      await expect(directory).toHaveText('请假办理');
    } else {
      await page.locator('#notice-related').click();
      await page.locator('html[data-live-ready=true]').waitFor();
      await expect(page.locator('.enterprise-dialog')).toBeVisible();
      await expect(page.locator('.enterprise-dialog')).toContainText('通知关联客户');
      await expect(page.locator('.live-error')).toHaveCount(0);
      await expect(page.locator('.rail-scroll .sub.active')).toHaveAttribute('href', '/enterprise/customers.html');
    }
    await overview(); await expect(page.locator('#personal-unread')).toHaveText('22 条未读');
    await page.locator('#notice-read').selectOption('unread');
    await expect(page.locator('#notice-page')).toContainText('共 22 条');
    await page.locator('#notice-kind').selectOption('reply');
    await expect(page.locator('#personal-notices .notice-kind').first()).toHaveText('服务回复');
    await page.locator('#notice-query').fill('不存在的标题');
    await page.getByRole('button', { name: '查询', exact: true }).click();
    await expect(page.locator('#personal-notices')).toContainText('暂无符合条件');
    await overview();
    readFails = true;
    await page.locator('#personal-notices .notice-row').nth(1).click();
    await expect(page.locator('#detail-status')).toContainText('标记已读失败');
    readFails = false;
    await page.goto(base + '/common/notification-detail.html?key=business%3A999');
    await expect(page.locator('#detail-status')).toContainText('测试错误');
    await expect(page.locator('#notice-detail')).toBeHidden();
    if (role === 'admin') {
      await page.goto(base + '/common/announcement-manage.html'); await page.locator('html[data-notification-ready=true]').waitFor();
      await page.locator('#announcement-title').fill('新建的公共通知'); await page.locator('#announcement-content').fill('发布正文');
      await page.locator('#announcement-state').selectOption('published'); await page.locator('#announcement-pinned').check();
      await page.locator('#announcement-save').click(); await expect(page.locator('#announcement-form-status')).toHaveText('保存成功。');
      assert.equal(announcements.at(-1).title, '新建的公共通知');
      await page.locator('#announcement-state').selectOption('withdrawn'); await page.locator('#announcement-save').click();
      await expect(page.locator('#announcement-form-status')).toHaveText('保存成功。');
      assert.equal(announcements.at(-1).status, 'withdrawn');
    } else {
      await page.goto(base + '/common/announcement-manage.html'); await expect(page.locator('#main-content')).toContainText('暂无访问权限');
    }
    await overview();
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 844 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({ path: `.runtime/notification-review/${role}-${width}.png`, fullPage: true });
    }
    assert.deepEqual(errors, []); await context.close();
    console.log(role + ': overview, filters, pagination, details, read state, permissions and mobile passed');
  }
} finally { await browser.close(); await server.close(); }
