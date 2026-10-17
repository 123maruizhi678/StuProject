# StuProject

后端按技术层分为api、core、schemas、services、repositories、models、clients、tasks，每层再按业务模块分包。

- 统一配置：根目录.env经app/config.py读取；不随模块复制配置。
- 开发启动（项目根目录）：`conda run -n SST python -m uvicorn app.main:app --reload`。
- 前端：启动后访问`/`主入口、`/login`统一登录、`/account`本人权限；公共资源位于frontend/js/common和frontend/css/common，资源URL以/static为前缀。JSON状态接口为`/health`。
- 报告结构预览（不连接数据库）：`conda run -n SST python scripts/report/init_report_tables.py --dry-run`。
- 学生成绩旧DSL导出脚本：scripts/student/export_student_scores.py，输出到dify/student/legacy；不是新增部署应用。
- 公共前端目录、模块分工及接入步骤见[frontend/README.md](frontend/README.md)。业务页面由各组在自己的目录交付，公共入口只负责登录、权限导航及页面装载。

尚未交付的enterprise_student旧重复入口及学生请假Dify适配器暂略。客服六接口已挂载到`/api/v1/agent`，真实模式经公共Dify HTTP工具调用已发布的客服Workflow；`.env`使用`DIFY_CLIENT=real`及独立`DIFY_AGENT_API_KEY`。接入不自动建表、启动任务或发布Dify，客服独立前端页面仍待业务组交付。

客服测试与接入契约见[tests/agent/README.md](tests/agent/README.md)。

客服 Agent 已按相同分包约定归位：HTTP 接口位于 `app/api/agent/`，业务编排与客服专属 Dify 客户端位于 `app/services/agent/`，ORM 位于 `app/models/agent/`，请求/响应模型位于 `app/schemas/agent/`。原文件名及职责沿用操作文档第七章，统一配置、数据库和公共 HTTP 工具继续复用公共模块；详细目录见客服接入说明。
