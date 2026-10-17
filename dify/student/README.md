# 学生统一 Workflow

唯一部署资产：student_assistant.yml。七类意图复用一个应用；legacy/ 为历史最小单元参考，不注册第二个学生智能体。

代码按 开发文档/操作文档.md 的附录B及051—062最终约定实现。新入口位于 app/api/student、app/services/student；公共身份/传输位于 common，旧导入仅保留转发。

## 配置与启动

从项目根目录执行：

- python scripts/student/run_student_app.py --port 8010
- python scripts/student/run_student_tasks.py --once（站内发布与接管检查）；常驻默认每300秒。
- python scripts/student/init_student_assistant.py --dry-run（只读核验数据库）
- python -m pytest tests/student -q

页面 /login 使用统一账号登录，学生页面 /student-assistant。环境变量 AUTH_SECRET_KEY 负责公共JWT，STUDENT_ACTION_SECRET 只负责会话/确认签名；两者分别从启动环境注入，均不复用Dify Key。学生应用使用 DIFY_API_BASE、DIFY_API_TIMEOUT_SECONDS、STUDENT_DIFY_KEY，默认读取无密钥 .env.sample，不再加载 .env 或 .env.student.local。

SQL scripts/sql/student/20261017_student_tables.sql 为7张学生表的最终DDL，仅适用于对应表缺失且公共依赖已具备的场景；已有表必须先按最终DDL核对并迁移。发现旧 student_leave_request 或旧通知表时停止自动切换，按主键映射、状态映射及真实审批审计迁移，不能覆盖新增业务。

课程和本人选课来源为受控本地文件，格式参见 app/student_courses.example.json；真实 app/student_courses.json 被Git忽略。文件不存在返回503，不从成绩或招生项目猜选课。

本地教务/CRM维护分别为 PUT /api/v1/internal/student/academic/{student_id}、PUT /api/v1/internal/student/progress/{student_id}；人员授权、学生关系与版本在固定服务核验。前者须academic及有效学生绑定，后者须负责顾问或本部门主管。外部同步默认关闭，不作为本地维护前置；启用时必须配置独立服务凭据、允许来源及学生范围。

## 验证边界

回归使用SQLite隔离库和明确模型替身；不代表MySQL真实库、Dify供应商/模型绑定或企业页面已经联调。DSL供应商和模型仍为文档指定占位，需要部署时替换并发布。

模型调用前持久化轮次占位；未知结果不自动重发，python scripts/student/run_student_tasks.py --pending-models 可列出待核实轮次。核实应依据Dify运行记录和原回执，不能直接删除占位重发。学生会话及心理跟进历史永久保留。

最终操作文档048规定本地权威不适用同步时 synced_at=NULL；源建表SQL中两张本地镜像表仍为NOT NULL。本模块模型及配套学生DDL按操作文档修正为可空，原开发文档未改。已有库需据此核对两列可空性。

公共配置迁移：运行时读取根 .env.sample 的公共默认值，同名环境变量优先。真实数据库密码、JWT签名密钥、学生应用Key等只在启动终端或部署平台注入，不再保存 .env 文件。Windows PowerShell可在当前会话通过 $env:变量名 设置后再启动；模板禁止填写真实凭据。
