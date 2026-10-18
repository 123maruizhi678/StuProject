# StuProject

后端按技术层分为api、core、schemas、services、repositories、models、clients、tasks，每层再按业务模块分包。

- 统一配置：根目录.env经app/config.py读取；不随模块复制配置。
- 完整开发启动（项目根目录）：`npm run dev`（或 `npm start`）。会启动本地后端、学生/企业通知任务和 Vite，并自动打开浏览器登录页。
- 前端地址：`http://127.0.0.1:5173`；后端：`http://127.0.0.1:8000`。前端的 `/api`、`/health`、`/openapi.json` 由 Vite 代理到后端。
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
