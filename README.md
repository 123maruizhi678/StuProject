# StuProject

## 本机启动命令（Windows PowerShell）

先确认本地 MySQL 服务已启动，端口为 `3306`；项目根目录 `.env` 中的数据库连接指向本地 `education_agent`。当前环境无需启动 Redis。

### 一键启动整个系统（推荐）

打开 PowerShell，执行：

```powershell
Set-Location D:\AI\StuProject
npm run dev
```

`npm start` 与 `npm run dev` 等效，选择其中一个即可。首次拉取代码或 `node_modules` 不存在时，先在项目根目录执行一次 `npm ci`。

此命令会依次启动后端、学生通知任务、企业通知任务和 Vite；后端就绪后自动打开浏览器登录页。终端需要保持运行。

- 登录页（本机及局域网）：[http://192.168.5.12/login.html](http://192.168.5.12/login.html)
- 后端：[http://127.0.0.1:8000](http://127.0.0.1:8000)
- 健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- 管理员账号：`root`；密码：`root`。
- 多角色模拟账号初始密码均为 `123456`，完整账号见 [多角色模拟报告](scripts/testing/ROLE_SIMULATION_REPORT.md)。

前端通过 Vite 将 `/api`、`/health` 和 `/openapi.json` 代理到 `127.0.0.1:8000`，无需单独设置代理。请通过上述登录页访问，不要直接双击 HTML 文件。

局域网访问：本机当前 IPv4 地址为 `192.168.5.12`，Vite 监听 `0.0.0.0:80`。浏览器默认使用 HTTP 80 端口，地址栏不需要输入端口号。同一局域网设备直接打开上述登录页，无需配置 hosts 或 DNS；打开 `http://192.168.5.12` 也会显示登录页。本机也可通过 `http://127.0.0.1/login.html` 访问。后端和数据库继续通过本机地址连接。若本机 IP 变化，需要同步调整访问地址及 `vite.config.mjs` 中的自动打开地址。

首次启用局域网访问时，在本机以管理员身份打开 PowerShell，执行以下命令，允许局域网设备访问 HTTP 80 端口：

```powershell
Set-Location D:\AI\StuProject
powershell -ExecutionPolicy Bypass -File .\scripts\setup-lan.ps1
```

防火墙规则只放行本机 `192.168.5.12` 的 TCP 80，来源范围为本地子网，保留正常的账号登录与角色权限。如果启动时提示 80 端口被占用，请先确认占用程序并处理端口冲突；Vite 不会自动切换到其他端口。

启动脚本会优先使用本机 `D:\anaconda3\envs\SST\python.exe`，并自动加载 `.runtime/backend-deps`。如需指定其他已安装依赖的 Python，在启动前执行：

```powershell
$env:STUPROJECT_PYTHON = 'D:\anaconda3\envs\SST\python.exe'
npm run dev
```

### 分别启动各服务

排查问题或单独开发时，可以打开四个 PowerShell 终端，分别执行以下命令。不要与一键启动同时运行，以免端口或通知任务重复。

终端一：启动后端。

```powershell
Set-Location D:\AI\StuProject
$env:PYTHONPATH = "$PWD\.runtime\backend-deps"
$env:PYTHONUTF8 = '1'
& 'D:\anaconda3\envs\SST\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

终端二：启动前端。Vite 会自动打开登录页，并使用已配置的代理连接后端。

```powershell
Set-Location D:\AI\StuProject
npm run dev:frontend
```

终端三：启动学生通知任务。

```powershell
Set-Location D:\AI\StuProject
$env:PYTHONPATH = "$PWD\.runtime\backend-deps"
$env:PYTHONUTF8 = '1'
& 'D:\anaconda3\envs\SST\python.exe' scripts/student/run_student_tasks.py
```

终端四：启动企业通知任务。

```powershell
Set-Location D:\AI\StuProject
$env:PYTHONPATH = "$PWD\.runtime\backend-deps"
$env:PYTHONUTF8 = '1'
& 'D:\anaconda3\envs\SST\python.exe' scripts/enterprise/run_enterprise_tasks.py --watch
```

只开前后端可以访问业务页面；完整运行还需要两个通知任务。分开启动时，各 Python 进程直接读取 `.env` 配置；一键启动额外默认屏蔽历史外部模型配置，符合当前未接入外部服务的测试范围。

### 停止服务

在启动终端按 `Ctrl+C`。分开启动时，在各终端分别按 `Ctrl+C`。如果系统是通过一键入口在后台启动的，执行：

```powershell
Set-Location D:\AI\StuProject
powershell -File .\scripts\stop.ps1
```

停止脚本只处理一键入口记录的本次进程；一键启动复用的已有后端，以及自行分开启动的进程，需要到对应终端停止。

## 项目说明

后端按技术层分为api、core、schemas、services、repositories、models、clients、tasks，每层再按业务模块分包。

- 统一配置：根目录.env经app/config.py读取；不随模块复制配置。
- 完整开发启动（项目根目录）：`npm run dev`（或 `npm start`）。会启动本地后端、学生/企业通知任务和 Vite，并自动打开浏览器登录页。
- 前端地址：`http://192.168.5.12/login.html`；后端：`http://127.0.0.1:8000`。前端的 `/api`、`/health`、`/openapi.json` 由 Vite 代理到后端。
- 仅启动后端：`conda run -n SST python -m uvicorn app.main:app --reload`；此命令不启动 Vite。
- 本地管理员已创建：账号 `root`，密码 `root`。密码以 Argon2 哈希入库。学生本人业务仍需使用管理员创建的学生账号。
- 停止完整服务：终端按 Ctrl+C；后台启动时运行 `powershell -File scripts/stop.ps1`。
- 报告结构预览（不连接数据库）：`conda run -n SST python scripts/report/init_report_tables.py --dry-run`。
- 学生成绩旧DSL导出脚本：scripts/student/export_student_scores.py，输出到dify/student/legacy；不是新增部署应用。
- 公共前端目录、模块分工及接入步骤见[frontend/README.md](frontend/README.md)。业务页面由各组在自己的目录交付，公共入口只负责登录、权限导航及页面装载。

学生、客户研判、企业、报告和客服接口均已挂载。学生与企业共用学业、提醒、申请进度模型；学生课程查询使用数据库中的真实选课关系。历史 enterprise_student 重复入口仍未交付。

当前验收未接入外部服务。完整启动默认屏蔽旧配置中的模型调用，缺失服务明确返回不可用；请假与工单原文仍可提交。确需恢复实际外部调用时，核对配置后设置 `STUPROJECT_ENABLE_EXTERNAL=1`。不会自动发布工作流或下载语音模型。

本机 SST 环境已有应用依赖；此次缺少的测试/解析包位于 `.runtime/backend-deps`，完整启动入口自动加载。新环境先安装项目依赖，再执行 `npm ci`。Python 路径可通过 `STUPROJECT_PYTHON` 指定。

真实业务库的增量准备脚本：`python scripts/testing/prepare_backend.py`，仅允许本机 education_agent，保留原有表与记录，增加缺失字段及课程表、初始化空报告配置和缺失的本地密钥。脚本不会重置已存在的 root 账号。

验收报告见 [scripts/testing/SYSTEM_TEST_REPORT.md](scripts/testing/SYSTEM_TEST_REPORT.md)，外部依赖后续方案见 [scripts/testing/EXTERNAL_SERVICES_PLAN.md](scripts/testing/EXTERNAL_SERVICES_PLAN.md)。

客服测试与接入契约见[tests/agent/README.md](tests/agent/README.md)。

客服 Agent 已按相同分包约定归位：HTTP 接口位于 `app/api/agent/`，业务编排与客服专属 Dify 客户端位于 `app/services/agent/`，ORM 位于 `app/models/agent/`，请求/响应模型位于 `app/schemas/agent/`。原文件名及职责沿用操作文档第七章，统一配置、数据库和公共 HTTP 工具继续复用公共模块；详细目录见客服接入说明。
