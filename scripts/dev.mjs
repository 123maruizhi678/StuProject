import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import net from 'node:net';
import { homedir } from 'node:os';
import { localOrigin } from './local-address.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const children = [];
const records=[];
mkdirSync(path.join(root,'.runtime'),{recursive:true});
const saveProcesses=()=>writeFileSync(path.join(root,'.runtime/dev-session.json'),JSON.stringify({pid:process.pid,children:records},null,2));
saveProcesses();
const env = { ...process.env, PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1',
  PYTHONPATH: [path.join(root, '.runtime/backend-deps'), process.env.PYTHONPATH].filter(Boolean).join(path.delimiter) };
// 当前验收范围未配置外部服务；显式返回依赖不可用，不发送旧配置中的模型请求。
if (process.env.STUPROJECT_ENABLE_EXTERNAL !== '1') {
  for (const key of ['DIFY_API_KEY','DIFY_AGENT_API_KEY','STUDENT_DIFY_KEY','ENTERPRISE_DIFY_API_KEY','REPORT_DIFY_API_KEY','CUSTOMER_EXTRACT_DIFY_API_KEY']) env[key] = '';
  env.DIFY_CLIENT = 'real';
}
const pythonCandidates = [
  process.env.CONDA_PREFIX && path.join(process.env.CONDA_PREFIX, 'python.exe'),
  path.join(homedir(), 'anaconda3/envs/SST/python.exe'),
  path.join(homedir(), 'miniconda3/envs/SST/python.exe'),
  'D:/anaconda3/envs/SST/python.exe',
].filter(Boolean);
const python = process.env.STUPROJECT_PYTHON || pythonCandidates.find(existsSync) || 'python';
async function health() {
  try { const r = await fetch('http://127.0.0.1:8000/health', {signal: AbortSignal.timeout(1000)});
    return r.ok && (await r.json()).data?.service === 'StuProject'; } catch { return false; }
}
async function backendPortOpen() {
  return new Promise(resolve => {
    const socket=net.connect({host:'127.0.0.1',port:8000});
    socket.setTimeout(1000);
    socket.once('connect',()=>{socket.destroy();resolve(true);});
    socket.once('error',()=>resolve(false));
    socket.once('timeout',()=>{socket.destroy();resolve(false);});
  });
}
function launch(command, args) {
  const child = spawn(command, args, { cwd: root, env, stdio: 'inherit', windowsHide: true });
  children.push(child);
  records.push({pid:child.pid,command,args});saveProcesses();
  child.on('error', error => { console.error(error.message); stop(1); });
  child.on('exit', code => { if (code && !stopping) stop(code); });
  return child;
}
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) child.kill();
  process.exitCode = code;
}
process.on('SIGINT', () => stop());
process.on('SIGTERM', () => stop());
if (!await health()) {
  if (!await backendPortOpen()) launch(python, ['-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000']);
  let ready = false;
  for (let i = 0; i < 60 && !stopping; i++) {
    if (await health()) { ready = true; break; }
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  if (!ready) { console.error('后端启动失败，请检查 MySQL 和 .env。'); stop(1); }
}
if (!stopping) {
  if (existsSync(path.join(root, '.runtime/models/faster-whisper-base/model.bin')) || process.env.ASR_MODEL_PATH) {
    launch(python, ['scripts/enterprise/local_voice.py']);
  }
  console.log(`后端已就绪。局域网登录地址 ${localOrigin}/login.html，通过 Vite 代理访问后端。`);
  launch(python, ['scripts/student/run_student_tasks.py']);
  launch(python, ['scripts/enterprise/run_enterprise_tasks.py', '--watch']);
  launch(python, ['scripts/report/run_report_tasks.py', '--interval', '300']);
  launch(process.execPath, ['node_modules/vite/bin/vite.js', '--config', 'vite.config.mjs']);
}
