# allm.md — 公共基础能力、客服 Agent 与智能报告合并说明

- 主体文档：`业务文档/09杂谈/马睿智/操作文档.md`
- 合并来源：`mrz.md`（公共基础能力）、`hzl.md`（客服 Agent）、`cyl.md`（智能报告）
- 模块负责人：公共（马睿智）、客服（何至朗）、智能报告（陈宇林）
- 整理日期：2026-10-16
- 统一系统目录：`D:\AI\StuProject`

本文是合并的实施总览：说明统一后的目录结构、数据库表结构与关联关系、三模块功能联动与调用流程，以及合并步骤、数据迁移与注意事项。本文只做设计与核对，不含实现代码；未执行建表、迁移、代码合并或部署。

---

## 一、合并概览

| 项目 | 内容 |
| --- | --- |
| 主体 | 公共登录与权限入口（公共基础能力），为所有业务接口提供 JWT、鉴权、日志、统一返回、数据库会话、本地 Dify HTTP 传输 |
| 合并模块 1 | 客服 Agent（对外开放模块）：六个匿名接口，只有对话入口调用 Dify |
| 合并模块 2 | 智能报告（管理层报告模块）：五个管理员专属接口，只有生成入口调用 Dify |
| 统一目录 | `D:\AI\StuProject` |
| 输出 | 合并后的 `马睿智/操作文档.md` + 本 allm.md |

**访问模型对照：** 客服模块「匿名开放」，不接公共 JWT；智能报告「管理员专属」，复用公共 JWT 与逐接口鉴权。两模块共用同一套公共组件，但授权方向相反，合并时不得互相污染授权范围。

---

## 二、统一目录层级与命名冲突处理

### 2.1 统一目录树（合并后）

```text
D:/AI/StuProject/
├── .env                               服务端配置（数据库、日志、JWT、各业务 Dify Key）
├── environment.yml                    依赖与环境
├── .gitignore                         忽略规则（.env、日志、缓存、本地运行数据）
├── app/
│   ├── main.py                        FastAPI 入口：挂载 auth / agent / report 路由
│   ├── config.py                      统一配置
│   ├── database.py                    连接池、ORM 基类、get_db 会话
│   ├── access_control.yaml            身份→权限映射（含 report.* 收敛）
│   ├── api/
│   │   ├── auth.py                    公共：登录、公开清单、当前权限（3 个接口）
│   │   ├── agent.py                   客服：对话、活动、报名、课程、FAQ（6 个接口）
│   │   └── report.py                  报告：生成、查单份、列表、查/改配置（5 个接口）
│   ├── core/
│   │   ├── auth.py                    JWT 身份认证
│   │   ├── authorization.py           逐接口鉴权
│   │   ├── logger.py                  日志
│   │   ├── response.py                统一返回与异常
│   │   ├── dify.py                    本地 Dify HTTP 传输（同步/异步）
│   │   └── report_auth.py             报告管理员鉴权依赖（新建）
│   ├── services/
│   │   ├── auth_service.py            公共账号与 JWT
│   │   ├── agent_service.py           客服业务编排
│   │   ├── dify_client.py             客服 mock/real 客户端
│   │   ├── report_service.py          报告配置读写 + 异步生成
│   │   ├── report_metrics.py          报告取数与固定指标（新建）
│   │   └── report_anonymizer.py       心理周报脱敏（新建）
│   ├── models/
│   │   ├── user_account.py            公共账号
│   │   ├── agent.py                   客服六表 ORM
│   │   └── report.py                  报告三表 ORM
│   ├── schemas/
│   │   ├── auth.py / agent.py / report.py
│   ├── clients/
│   │   ├── nl2sql_dify.py             NL2SQL 场景适配
│   │   └── report_dify.py             报告 Workflow 适配
│   ├── tasks/
│   │   └── report_tasks.py            报告定时生成（新建）
│   └── logs/                          运行日志
├── dify/
│   ├── 客服Agent-Chatflow.yml          客服 Workflow DSL（待交付核实）
│   ├── README.md / knowledge/          客服知识库资产（待交付核实）
│   └── report/
│       ├── report.yml                  智能报告生成 Workflow DSL
│       └── README.md                  报告 Workflow 说明
└── scripts/
    ├── init_report_tables.py          报告三表初始化
    ├── run_report_tasks.py            报告调度进程（新建）
    ├── reupload_dify_kb.py / test_dify_kb.py / test_workflow_run.py   客服联调（待交付核实）
    └── sql/
        ├── all.sql                     统一建表脚本（含全部表）
        ├── agent_seed.sql              客服种子（待交付核实）
        └── bk/智能报告/
            └── report_module_ddl.sql   报告三表 DDL（与 all.sql 一致）
```

### 2.2 路径统一

| 冲突点 | 处理方式 |
| --- | --- |
| `D:\AI\StuProject`（主体口径） vs `C:\Users\Windows\PycharmProjects\project_1\StuProject`（另一工作副本） | 文档统一采用主体的 `D:\AI\StuProject`；另一副本仅作为工作副本线索保留，不作为合并基座 |
| 各模块文档使用相对路径（`app/`、`dify/`、`scripts/`） | 均按统一系统目录拼成全路径，相对层级不变 |
| `客户需求表.xlsx` 等桌面路径 | 属个人本地参考，不入统一目录树 |

### 2.3 命名冲突处理

| 命名冲突 | 处理方式 |
| --- | --- |
| 客服 `agent` 前缀文件 vs 报告 `report` 前缀文件 | 分属不同文件名，无冲突；`app/api/agent.py` 与 `app/api/report.py`、`app/models/agent.py` 与 `app/models/report.py` 并列 |
| `dify/README.md`（客服） vs `dify/report/README.md`（报告） | 分属不同子目录，按完整相对路径区分；不因同名改名或覆盖 |
| `app/clients/report_dify.py`（报告） vs `app/clients/nl2sql_dify.py`（NL2SQL） | 都是场景适配器，复用公共 `core/dify.py`，各自维护业务解析 |
| `scripts/sql/all.sql`（全量） vs `report_module_ddl.sql`（报告） | 报告 DDL 是 all.sql 的抽取，保持一致；不做两份独立版本 |
| 多模块共用 `main.py` / `config.py` / `database.py` / `core/*.py` | 全项目只保留一份实际实现，各模块复用同一文件，不复制成平行代码 |

---

## 三、数据库表结构及关联关系

### 3.1 表清单（合并涉及范围）

| 类别 | 表 | 归属 |
| --- | --- | --- |
| 公共账号 | `user_account` | 公共模块 |
| 共享依赖 | `org_department`、`employee`、`customer_profile`、`student_profile` | 各业务模块 |
| 客服（6） | `course_project`、`lecture_event`、`event_signup`、`faq`、`chat_session`、`chat_message` | 客服模块 |
| 报告专属（3） | `report_config`、`report_record`、`report_metric` | 报告模块 |
| 报告只读上游（6） | `customer_followup`、`customer_judgement`（未落地）、`employee_daily_report`、`mental_health_profile`、`mental_warning`、`service_ticket` | 企业 / 客户研判 / 学生 / 投诉模块 |

本合并展开 **14 张相关表** 的完整字段（公共账号 5 + 客服 6 + 报告 3）；报告只读的 6 张上游表由对应业务模块维护，报告模块不持有其 ORM、不回写，本合并不展开其字段。

### 3.2 关联关系

```text
user_account.employee_id ──► employee.employee_id
user_account.customer_id ──► customer_profile.customer_id
user_account.student_id ───► student_profile.student_id
employee.department_id ────► org_department.department_id
customer_profile.department_id ─► org_department.department_id
student_profile.department_id ──► org_department.department_id

event_signup.event_id ─────► lecture_event.id
chat_message.session_id ───► chat_session.session_id

report_record.report_config_id ─► report_config.report_config_id
report_metric.report_record_id ─► report_record.report_record_id

报告模块（只读，不建 FK）：
  customer_overview ◄── customer_profile、customer_followup、customer_judgement
  daily_report / weekly_report ◄── employee_daily_report
  mental_weekly ◄── mental_health_profile、mental_warning
  complaint_weekly ◄── service_ticket
```

### 3.3 字段与表关联冲突解决

| 冲突 / 风险点 | 结论 |
| --- | --- |
| `customer_profile` 两处来源（公共共享表 vs 报告只读源表） | 两侧均为 22 字段，口径一致，无冲突；报告只读该表，字段定义以第九章共享表为准 |
| `report.read` 权限：`access_control.yaml` 中 employee 现含 `report.read`，与报告「仅管理员」冲突 | 收敛为 `report.*` 仅授予 `admin`，移除 employee 的 `report.read` |
| 报告三张专属表 | 全新表，与已有表无字段/外键冲突；主外键只在三表内部闭合 |
| `customer_judgement`、`customer_profile.deal_amount` | 尚未落地，报告的经营分析研判维度依赖它们，排最后接入，不在本次合并落地 |
| 报告上游源表（`mental_health_profile` 等）未在本合并展开字段 | 属学生/投诉等其它模块，报告只读；字段由对应模块文档维护，避免跨模块越权定义 |
| 客服 `chat_session.user_id` 与 `user_account.user_id` 同名不同义 | 客服访客标识 ≠ 平台账号主键，不建立外键、不自动关联，避免误判 |

### 3.4 报告三张专属表（新增，字段摘要）

- `report_config`（9 字段）：`report_config_id`、`report_code`（唯一）、`report_name`、`report_period`、`cron_expr`、`enabled`、`created_at`、`updated_at`、`row_version`。
- `report_record`（18 字段）：`report_record_id`、`report_config_id`（FK）、`report_code`、`idempotency_key`（唯一）、`start_time`、`end_time`、`timezone`、`data_snapshot_at`、`report_version`、`source_record_count`、`report_content`、`metric_json`、`status`、`fail_reason`、`generated_at`、`created_at`、`updated_at`、`row_version`。
- `report_metric`（10 字段）：`report_metric_id`、`report_record_id`（FK）、`metric_code`、`metric_name`、`metric_value`、`metric_text`、`metric_unit`、`calc_rule`、`period_type`、`created_at`。

完整字段、约束与索引见 `马睿智/操作文档.md` 第九章「智能报告三张专属表」。

---

## 四、功能联动设计与调用流程

### 4.1 三模块职责与联动

```text
                     ┌────────────────────────────┐
  浏览器/前端 ──► │ 公共鉴权（JWT + require_permission）│
                     └──────────┬─────────────────┘
          ┌─────────────────────┼─────────────────────┐
          ▼ 匿名                ▼ 管理员             ▼ 管理员
     客服 Agent            智能报告            其它受保护业务
   （6 个匿名接口）      （5 个管理员接口）      （复用公共鉴权）
          │                    │
          ▼                    ▼
   Dify 客服 Workflow    Dify 智能报告 Workflow
          │                    │
          ▼                    ▼
  course/lecture/faq/    上游源表(只读固定SQL)
  chat_session/message        │
                              ▼
                      report_config/record/metric
```

- **公共模块**：提供 JWT 签发/解析、`get_current_account`、`require_permission`、日志、统一返回、数据库会话、Dify HTTP 传输；只负责「允许/拒绝」与基础设施，不承担业务规则。
- **客服模块**：匿名开放，不接 JWT；对话编排、活动/课程/FAQ 查询、报名落库；Dify 只生成话术与动作，后端以数据库事实为准。
- **报告模块**：管理员专属，接 JWT + `report.*` 权限；作为数据消费末端只读上游、算指标、调 Dify 写分析、落库。

### 4.2 报告生成调用流程（核心联动）

1. 管理员登录取得 JWT，调 `POST /api/v1/report/generate`（`report_code` + 可选时间窗）。
2. 报告路由经公共鉴权校验管理员与 `report.generate`（当前未挂鉴权，为待办）。
3. 幂等判定：同键同口径返回已有记录，同键不同口径返回 409。
4. 建 `report_record`（`status=pending`）立即返回 `report_record_id`，后台任务异步执行：
   - 固定 SQL 从上游源表取数（只读）；
   - 计算指标（固定口径）；
   - 调「智能报告生成」Workflow（`report_code` + `metrics` → `report_text`）；
   - 剥离 `<think>` 推理内容，写正文与指标快照；
   - 置 `success`；任一步失败置 `failed` + `fail_reason`。
5. 管理员轮询 `GET /report/{report_record_id}` 取结果；`GET /report/list` 只看元数据；心理周报默认匿名聚合。

### 4.3 客服咨询到报名的调用流程（既有）

访客对话（匿名）→ 建/复会话并保存消息 → 客服场景客户端（mock/real）返回意图与动作 → 前端按 `show_courses` / `show_events` 请求真实列表 → 报名校验（状态式去重、名额、事务）→ 写 `event_signup` 并更新 `signed_count`。

### 4.4 模块边界（不要重复造）

- 日报「内容级摘要」属企业模块，报告只做数量级指标或复用 `employee_daily_report.ai_summary`。
- 心理「风险识别」属学生模块，报告只读 `mental_health_profile` / `mental_warning` 做聚合。
- NL2SQL 切换为未来待办，当前取数用固定 SQL。

---

## 五、合并步骤

| 步骤 | 动作 | 完成标准 |
| --- | --- | --- |
| 0. 锁定版本 | 记录三方仓库、分支、提交号、工作区改动、数据库版本 | 来源清晰、可回退 |
| 1. 文件盘点 | 按统一目录树逐路径核对，分类为一致 / 双方修改 / 独有 / 缺失 | 形成差异与缺失清单 |
| 2. 合并公共契约 | 核对认证、权限、响应、Dify HTTP、会话、配置 | 公共组件只一套，已有调用不被覆盖 |
| 3. 接入客服与报告 | 挂载 auth/agent/report 路由，合并 ORM、schema、服务 | 服务启动无缺失 import，OpenAPI 含 3+6+5 接口 |
| 4. 数据库准备 | 核对 14 张表定义与目标库差异，报告三表走增量 DDL + 种子 | 无破坏性全量重建 |
| 5. 权限收敛 | `access_control.yaml` 中 `report.*` 仅 admin，移除 employee 的 `report.read` | 报告五接口只认管理员 |
| 6. 配置与运行环境 | 配置真实 JWT 与 Dify Key，报告路由补鉴权依赖 | 仅启用已配置功能 |
| 7. 按变更验证 | 公共认证、客服六接口、报告五接口、模型适配、并发检查 | 待接通项逐项有证据 |
| 8. 条件迁移 | 仅在有结构差异时执行增量迁移；报告三表为纯增量 | 记录数、关系、切换点一致，可回滚 |
| 9. 归档 | 记录合并提交、配置模板、迁移脚本版本与验收结果 | 已实现 / 已验证 / 待办清晰 |

---

## 六、数据迁移方案

| 情况 | 处理 |
| --- | --- |
| 公共账号 + 客服表（已有） | 保留现有数据与约束；目标有数据时用备份 + 差异报告 + 增量迁移，禁止直接执行含 DROP/重建的 all.sql |
| 报告三张专属表（全新） | **纯增量**：补建 `report_config` / `report_record` / `report_metric` + 五条配置种子；无存量数据搬迁，上游源表结构不变、数据不动 |
| 权限收敛 | 属配置变更（`report.*` 仅 admin），与公共鉴权统一发布，不涉及表迁移 |
| 空目标库 | 可用核对后的 all.sql 建表 + 必要种子；有数据的库不得全量重建 |
| 身份/外键映射 | 账号、员工、客户、学生分别按可靠业务标识去重并建立主键映射，不简单加 ID 偏移；客服 `session_id` 碰撞需同步更新消息引用 |
| 回滚 | 切换前失败恢复已验证备份；切换后先停写、记录增量再回退，不回滚已发生的外部通知/CRM 写入 |

---

## 七、向后兼容与注意事项

### 7.1 向后兼容

- 公共三接口（登录 / 公开清单 / 当前权限）路径与返回不变。
- 客服六接口继续匿名开放，不带 JWT 仍可咨询与报名，请求/响应字段与已用前端兼容。
- 报告五接口维持异步生成 + 幂等语义；`report.*` 权限收紧不破坏已生成报告数据，但若已有前端调用需核对鉴权切换。
- 已签发 JWT 兼容性取决于签名密钥、算法与 user_id 映射；若 user_id 变化，旧 Token 的 sub 可能指错账号，需重新登录或受控过渡。

### 7.2 注意事项

1. **授权方向相反**：客服匿名、报告管理员专属，合并时不得让客服获得管理能力，也不得把报告开放给员工。
2. **页面可见性 ≠ 接口授权**：后端五报告路由仍须逐个挂 `require_permission`，不能只靠前端隐藏。
3. **报告只读上游**：报告模块不建上游表 ORM、不回写，只按 `all.sql` 列名用固定 SQL 读，避免跨模块越权定义。
4. **同名文件不覆盖**：`agent`/`report` 前缀文件与各 `README.md` 按完整相对路径区分。
5. **「已实现」不等于已验收**：报告路由鉴权、心理周报取数/脱敏、投诉口径、定时生成、客服 real 链路、报名行锁等状态以核对结果为准，不沿用其它工作副本的「已实现」结论。
6. **真实值不入文档**：数据库口令、JWT 密钥、Dify API Key 只写配置名，不写真实值。
