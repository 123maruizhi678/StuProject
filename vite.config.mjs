import { defineConfig } from 'vite';

export default defineConfig({
  root: 'frontend',
  appType: 'mpa',
  plugins: [{
    name: 'existing-page-routes',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const aliases = { '/login': '/common/login.html', '/account': '/common/account.html',
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
    host: '127.0.0.1', port: 5173, strictPort: true,
    open: process.env.NO_OPEN !== '1' ? '/common/login.html' : false,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/openapi.json': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
});
