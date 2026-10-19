import { clearSession, readSession } from './api.js';
import { WORKSPACE_PATH, canOpenPage, navigationLocation, visibleModules } from './navigation-model.js';

const icon = paths => `<svg class="icon" aria-hidden="true" viewBox="0 0 24 24">${paths}</svg>`;

// 各模块只提供导航元数据，顶部栏结构、身份入口和菜单行为由公共布局维护。
export function renderTopbar(access) {
  const header = document.querySelector('.workspace > .app-topbar');
  if (!header) return;
  if (!header.hasAttribute('data-common-topbar')) {
    header.setAttribute('data-common-topbar', '');
    header.innerHTML = `
      <button type="button" class="icon-button menu-button" data-menu aria-label="打开导航" aria-expanded="false">${icon('<path d="M4 6h16M4 12h16M4 18h16"/>')}</button>
      <nav class="crumb" aria-label="当前位置"></nav>
      <div class="top-spacer"></div>
      <div class="top-actions">
        <a class="icon-button" data-topbar-notifications aria-label="查看通知">${icon('<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4"/>')}</a>
        <a class="user-chip" href="/common/account.html" aria-label="个人中心"><span class="avatar">·</span><span class="user-name"></span></a>
        <button class="button secondary small" id="workspace-logout" type="button">退出登录</button>
        <a class="button secondary small" data-topbar-login href="/common/login.html">登录</a>
      </div>`;
    const menu = header.querySelector('[data-menu]');
    const closeMenu = () => {
      document.body.classList.remove('rail-open');
      menu.setAttribute('aria-expanded', 'false');
    };
    menu.addEventListener('click', event => {
      // 兼容旧页面保留的菜单事件，避免同一次点击切换两次。
      event.stopImmediatePropagation();
      const open = document.body.classList.toggle('rail-open');
      menu.setAttribute('aria-expanded', String(open));
    });
    document.querySelector('.mobile-scrim')?.addEventListener('click', closeMenu);
    document.addEventListener('keydown', event => { if (event.key === 'Escape') closeMenu(); });
    header.querySelector('#workspace-logout').onclick = () => {
      clearSession();
      location.replace('/common/login.html');
    };
  }

  const { current, moduleId } = navigationLocation(location.pathname, access);
  const metadata = access?.navigation?.routes?.[current];
  const module = visibleModules(access).find(item => item.id === moduleId);
  const crumb = header.querySelector('.crumb');
  const separator = () => {
    const span = document.createElement('span');
    span.textContent = '/';
    span.setAttribute('aria-hidden', 'true');
    return span;
  };
  crumb.replaceChildren();
  if (current !== WORKSPACE_PATH && canOpenPage(WORKSPACE_PATH, access)) {
    const home = document.createElement('a');
    home.href = WORKSPACE_PATH;
    home.textContent = '通知中心';
    crumb.append(home, separator());
  }
  if (module && module.title !== metadata?.title) {
    const name = document.createElement('span');
    name.textContent = module.title;
    crumb.append(name, separator());
  }
  const title = document.createElement('b');
  title.textContent = metadata?.title || '工作空间';
  title.setAttribute('aria-current', 'page');
  crumb.append(title);

  const authenticated = Boolean(readSession());
  header.querySelector('#workspace-logout').hidden = !authenticated;
  header.querySelector('[data-topbar-login]').hidden = authenticated;
  const notification = header.querySelector('[data-topbar-notifications]');
  notification.href = WORKSPACE_PATH;
  notification.hidden = !canOpenPage(WORKSPACE_PATH, access);
  header.querySelector('.user-chip').hidden = !canOpenPage('/common/account.html', access);
}
