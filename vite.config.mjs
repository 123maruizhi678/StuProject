import { defineConfig } from 'vite';
import { frontendPort, localOrigin } from './scripts/local-address.mjs';
import { existsSync } from 'node:fs';
const backendTarget = process.env.STUPROJECT_BACKEND_URL || 'http://192.168.5.12:8000';
const localVoice = Boolean(process.env.ASR_MODEL_PATH || existsSync(new URL('./.runtime/models/faster-whisper-base/model.bin', import.meta.url)));

export default defineConfig({
  root: 'frontend',
  appType: 'mpa',
  plugins: [{
    name: 'existing-page-routes',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const aliases = { '/': '/common/login.html', '/login.html': '/common/login.html', '/login': '/common/login.html', '/account': '/common/account.html',
          '/enterprise': '/enterprise/assistant.html', '/student-assistant': '/student/student-assistant.html',
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
      ...(localVoice ? {
        '/api/v1/enterprise/voice/transcribe': { target: 'http://127.0.0.1:8011', changeOrigin: true, timeout: 180000, proxyTimeout: 180000 },
        '/local-voice-health': { target: 'http://127.0.0.1:8011', changeOrigin: true },
      } : {}),
      '/api': { target: backendTarget, changeOrigin: true },
      '/health': { target: backendTarget, changeOrigin: true },
      '/openapi.json': { target: backendTarget, changeOrigin: true },
    },
  },
});
