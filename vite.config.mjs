import { defineConfig } from 'vite';
import { frontendPort, localOrigin } from './scripts/local-address.mjs';

// 后端代理目标：默认本机 127.0.0.1:8000；需要连接局域网其他机器上的后端时，
// 启动前设置 BACKEND_ORIGIN，例如 BACKEND_ORIGIN=http://192.168.5.12:8000。
const backendOrigin = process.env.BACKEND_ORIGIN || 'http://127.0.0.1:8000';

export default defineConfig({
  root: 'frontend',
  appType: 'mpa',
  plugins: [{
    name: 'existing-page-routes',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const aliases = { '/': '/common/login.html', '/login.html': '/common/login.html', '/login': '/common/login.html', '/account': '/common/account.html',
          '/enterprise': '/enterprise/enterprise.html', '/student-assistant': '/student/student-assistant.html',
          '/admin': '/admin/accounts.html', '/admin/accounts': '/admin/accounts.html' };
        const [path, query] = req.url.split('?');
        const rewritten = aliases[path] || (path.startsWith('/static/') ? path.slice(7) : path);
        req.url = rewritten + (query ? '?' + query : '');
        next();
      });
    },
  }],
  server: {
    host: '0.0.0.0', port: frontendPort, strictPort: true,
    open: process.env.NO_OPEN !== '1' ? `${localOrigin}/login.html` : false,
    proxy: {
      '/api': { target: backendOrigin, changeOrigin: true },
      '/health': { target: backendOrigin, changeOrigin: true },
      '/openapi.json': { target: backendOrigin, changeOrigin: true },
    },
  },
});
