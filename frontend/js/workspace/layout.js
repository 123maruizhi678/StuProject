/* Shared navigation; business interactions use the live workspace. */
document.addEventListener('click', event => {
  if (event.target.closest('[data-menu]')) document.body.classList.toggle('rail-open');
  if (event.target.closest('.mobile-scrim')) document.body.classList.remove('rail-open');
  if (event.target.closest('[data-print]')) window.print();
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') document.body.classList.remove('rail-open');
});
document.addEventListener('input', event => {
  if(event.target.matches('[data-map-search]')) {
    const term=event.target.value.trim();
    document.querySelectorAll('.map-link').forEach(link=>link.hidden=link.dataset.permissionHidden==='true'||!link.textContent.includes(term));
  }
});
document.documentElement.classList.add('permission-loading');
const permissionStyle = document.createElement('link');
permissionStyle.rel = 'stylesheet'; permissionStyle.href = '/css/common/workspace.css';
document.head.append(permissionStyle);
const startPublicLayout = async () => {
  const { prepareSupportFrame } = await import('../common/support-context.js');
  if (!prepareSupportFrame()) return;
  if (location.pathname.replace(/^\/static\//, '/') === '/common/notifications.html') {
    location.replace('/common/workspace.html');
    return;
  }
  if (document.querySelector('[data-login-preview]')) {
    document.documentElement.classList.remove('permission-loading');
    await import('../common/login-page.js');
    return;
  }
  const { mountNavigation, renderNavigation } = await import('../common/navigation.js');
  const access = await mountNavigation();
  if (!access) return;
  if (location.pathname.replace(/^\/static\//, '/') === '/common/account.html') {
    const { renderAccount } = await import('../common/account-page.js');
    renderAccount(access);
  } else await import('./live.js');
  renderNavigation(access);
};
startPublicLayout().catch(error => {
  document.documentElement.classList.remove('permission-loading');
  const node = document.createElement('p');
  node.className = 'live-error'; node.setAttribute('role','alert');
  node.textContent = '页面加载失败：' + error.message;
  (document.querySelector('main') || document.body).prepend(node);
});
