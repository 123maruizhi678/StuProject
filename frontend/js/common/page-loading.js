// Shared page lifecycle. Cached navigation is visual only; content waits for fresh authorization.
let pageAccess = null, pageToken = null;

export function setPageAccess(access, token) {
  pageAccess = access;
  pageToken = token;
}

export function getPageAccess(token) {
  return token === pageToken ? pageAccess : null;
}

export function beginPageLoading() {
  document.documentElement.classList.add('permission-loading');
  document.querySelector('.workspace-main')?.setAttribute('aria-busy', 'true');
}

export async function finishPageLoading() {
  await Promise.all([...document.querySelectorAll('link[rel="stylesheet"]')].map(link => {
    if (link.sheet) return;
    return new Promise(resolve => {
      const done = () => { clearTimeout(timer); link.removeEventListener('load', done); link.removeEventListener('error', done); resolve(); };
      const timer = setTimeout(done, 3000);
      link.addEventListener('load', done, { once: true });
      link.addEventListener('error', done, { once: true });
    });
  }));
  document.documentElement.dataset.pageReady = 'true';
  document.documentElement.classList.remove('permission-loading');
  document.querySelector('.workspace-main')?.setAttribute('aria-busy', 'false');
}

export async function failPageLoading(error) {
  const message = document.createElement('p');
  message.className = 'live-error'; message.setAttribute('role', 'alert');
  message.textContent = '页面加载失败：' + error.message;
  (document.querySelector('main') || document.body).replaceChildren(message);
  await finishPageLoading();
}
