import { defineConfig } from 'vite';
import { frontendPort, localOrigin } from './scripts/local-address.mjs';

const backendTarget = process.env.STUPROJECT_BACKEND_TARGET || 'http://192.168.5.12:8000';

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
      '/api': { target: backendTarget, changeOrigin: true },
      '/health': { target: backendTarget, changeOrigin: true },
      '/openapi.json': { target: backendTarget, changeOrigin: true },
    },
  },
});
