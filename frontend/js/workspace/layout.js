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
    document.querySelectorAll('.map-link').forEach(link=>link.hidden=!link.textContent.includes(term));
  }
});
import('./live.js').catch(error => {
  const node = document.createElement('p');
  node.className = 'live-error'; node.setAttribute('role','alert');
  node.textContent = '页面加载失败：' + error.message;
  (document.querySelector('main') || document.body).prepend(node);
});
