# 项目合并方案（allm.md）

> **合并双方**
> - **A 方**：马睿智《公共登录与权限入口》模块 —— 项目目录 `D:\AI\StuProject`（该目录当前不在本机，本文以其操作文档 `mrz.md` 的描述为权威依据）
> - **B 方**：客服Agent 模块及所在仓库 —— `c:\Users\Windows\PycharmProjects\StuProject`（以代码实况为权威依据）
>
> **目标**：统一目录层级并妥善处理路径/命名冲突；合并数据库表结构并解决字段与表关联冲突；梳理模块功能并设计功能联动；保留双方核心功能、确保向后兼容；给出数据迁移方案。
> **更新日期**：2026-10-16

---

## 一、合并双方概况

| 维度 | A 方：公共登录与权限入口 | B 方：客服Agent 及仓库 |
|---|---|---|
| 核心职责 | JWT 登录认证、逐接口权限鉴权、日志、统一返回、Dify HTTP 传输、数据库/配置等公共能力 | 7×24 智能客服：对话（后端调 Dify 工作流）、活动/课程查询、活动报名 |
| 对外接口 | 3 个：`POST /api/v1/auth/login`、`GET /api/v1/auth/public-access`、`GET /api/v1/auth/me/access` | 6 个（全部 public 匿名可调）：`/agent/chat`、`/agent/events`、`/agent/events/{id}`、`/agent/events/signup`、`/agent/courses`、`/agent/faq` |
| 数据库表 | `user_account`（身份 + 关联 employee / customer_profile / student_profile） | 31 张表（含 `user_account`、客服 6 张、企业组织 12 张、学生助手 9 张、报告 3 张） |
| Dify 资产 | 无（仅提供传输层 `core/dify.py`） | 客服Agent 工作流 DSL + 4 个知识库；另有学生请假/报告工作流 |
| 关键文件 | `api/auth.py`、`core/{auth,authorization,logger,response,dify}.py`、`services/auth_service.py`、`models/user_account.py`、`schemas/auth.py`、`access_control.yaml` | `api/agent.py`、`services/{agent_service,dify_client}.py`、`models/agent.py`、`dify/客服Agent-Chatflow.yml`、`dify/knowledge/*` |

**分工原则（合并后延续）**：
- A 方公共能力（认证/鉴权/日志/统一返回/Dify 传输层/配置/数据库连接）在全仓库**唯一**，各业务模块复用不重复建设；
- B 方客服 Agent 及其他业务模块只做业务；Dify 只做「理解意图 + 检索 + 生成话术」，不连业务库；**后端是唯一落库入口**。

---

## 二、合并后的目录结构说明

### 2.1 统一后的目录树

以 B 方仓库为基座（表更全、模块更全），A 方公共模块文件按「权威覆盖」原则合入（哪些文件以 A 方为准见 2.2）：

```text
StuProject/                                # 合并后唯一仓库（B 方路径）
├── .env.example                           # 配置模板（可提交）
├── .env                                   # 本机配置，含双方密钥（gitignore，不提交）
├── .gitignore
├── environment.yml                        # 依赖声明（双方取并集）
│
├── app/
│   ├── main.py                            # 入口：挂载 auth + agent（student_leave/report 按进度挂载）
│   ├── config.py                          # 统一配置：DB/日志/JWT + 各业务 Dify 配置
│   ├── database.py                        # 连接池 / ORM 基类 / 请求级会话
│   ├── access_control.yaml                # 身份→权限映射（以 A 方为权威）
│   ├── README.md
│   │
│   ├── api/                               # HTTP 路由层
│   │   ├── auth.py                        # 【A】登录 / 公开清单 / 当前用户权限（3 接口）
│   │   ├── agent.py                       # 【B】客服 Agent（6 接口，public）
│   │   ├── student_leave.py               # 学生请假（按进度启用）
│   │   └── report.py                      # 智能报告（按进度启用）
│   │
│   ├── core/                              # 公共能力层（A 方权威）
│   │   ├── auth.py                        # JWT 身份认证依赖 get_current_account
│   │   ├── authorization.py               # require_permission / permissions_for / access_for
│   │   ├── logger.py                      # 日志（沿用 B 方已修复版本）
│   │   ├── response.py                    # 统一信封 / 全局异常处理
│   │   └── dify.py                        # DifyHttpClient 同步/异步 JSON 传输层
│   │
│   ├── services/                          # 业务层
│   │   ├── auth_service.py                # 【A】密码哈希 / JWT 签发解析
│   │   ├── agent_service.py               # 【B】客服业务：对话编排 / 报名 / 课程 / FAQ
│   │   ├── dify_client.py                 # 【B】客服 Dify 客户端（mock/real + 思维链清洗 + action 映射）
│   │   ├── student_leave_service.py       # 学生请假业务
│   │   ├── report_service.py              # 报告业务
│   │   └── nl2sql_service.py              # NL2SQL 业务（未接线，规划中）
│   │
│   ├── models/                            # ORM
│   │   ├── user_account.py                # 【A】统一账号表
│   │   ├── agent.py                       # 【B】客服 6 张表
│   │   ├── student_leave.py               # 学生请假表
│   │   └── report.py                      # 报告表
│   │
│   ├── schemas/                           # 各模块请求/响应模型（auth / agent / student_leave / report）
│   ├── clients/                           # 各业务 Dify 适配器，复用 core/dify.py
│   │   ├── student_leave_dify.py
│   │   ├── nl2sql_dify.py
│   │   └── report_dify.py
│   ├── repositories/                      # 数据访问层
│   ├── dify/                              # 辅助脚本（DSL 生成等）
│   ├── tasks/                             # 后台任务包（预留）
│   └── logs/                              # 运行日志（gitignore）
│
├── dify/                                  # Dify 侧资产（按业务分目录，各业务负责人维护）
│   ├── 客服Agent-Chatflow.yml              # 【B】客服工作流 DSL（20 节点）
│   ├── README.md                          # 客服 DSL 导入说明
│   ├── knowledge/                         # 【B】客服 4 个知识库内容 + README + dataset_ids.json
│   ├── student_leave/                     # 学生请假工作流
│   └── report/                            # 报告工作流
│
├── scripts/
│   ├── sql/
│   │   ├── all.sql                        # 统一建表脚本（31 张，合并后唯一 DDL 来源）
│   │   ├── agent_seed.sql                 # 【B】客服种子数据
│   │   └── README.md
│   ├── build_dify_kb.py                   # 【B】客服知识库一键创建上传
│   ├── reupload_dify_kb.py                # 【B】客服知识库重新上传
│   ├── test_dify_kb.py                    # 【B】知识库检索验证
│   ├── test_workflow_run.py               # 【B】客服 7 场景联调
│   └── init_report_tables.py              # 报告表初始化
│
├── frontend/                              # 前端（客服窗口等）
└── 业务文档/                               # 需求/设计/接口/数据库设计/开发文档/日报
```

> A 方原目录 `D:\AI\StuProject` 合并后废弃，全部内容合入上树；A 方独有的文件（如有）按 2.2 的归属表落入对应位置，不新增顶层目录。

### 2.2 同名文件冲突处理（17 个）

双方存在同名相对路径的文件（B 方仓库中已有一份公共模块副本，是早期同步产物，**不代表最新**）。合并时按“模块负责人权威”原则处理，**禁止用 B 方旧副本覆盖 A 方权威件**：

| # | 同名文件 | 处理方式 | 说明 |
|---|---|---|---|
| 1 | `app/main.py` | **双方改动合并** | 以 B 方为底（挂载 agent），恢复 A 方的 auth 挂载；student_leave/report 按进度挂载 |
| 2 | `app/config.py` | **以 B 方为基础合并** | B 方已是超集（含 `AUTH_*`、`ACCESS_CONTROL_FILE`、`DIFY_CLIENT`/`DIFY_AGENT_API_KEY`、企业/学生配置）；合入 A 方新增项（如有） |
| 3 | `app/database.py` | **diff 后保留** | 两侧同源，预计无实质差异；有差异取更完整版本 |
| 4 | `app/access_control.yaml` | **A 方权威覆盖** | 身份→权限映射由 A 方维护；B 方不得改动 |
| 5 | `app/api/auth.py` | **A 方权威覆盖** | 3 个登录/权限接口由 A 方负责 |
| 6 | `app/core/auth.py` | **A 方权威覆盖** | JWT 认证依赖 |
| 7 | `app/core/authorization.py` | **A 方权威覆盖** | 逐接口鉴权组件 |
| 8 | `app/core/logger.py` | **保留 B 方版本** | B 方已删除无用 `Path` 导入（A 方合入时带上此修复即可） |
| 9 | `app/core/response.py` | **A 方权威覆盖** | A 方版本含企业路径 HTTPException 信封处理，更完整 |
| 10 | `app/core/dify.py` | **A 方权威覆盖** | 公共传输层；B 方客服客户端已依赖它，接口不变则无影响 |
| 11 | `app/services/auth_service.py` | **A 方权威覆盖** | 密码哈希/JWT 签发解析 |
| 12 | `app/models/user_account.py` | **A 方权威覆盖** | 覆盖后须与 `all.sql` 中 DDL 逐字段核对（见 3.2） |
| 13 | `app/schemas/auth.py` | **A 方权威覆盖** | 登录请求模型 |
| 14 | `app/clients/nl2sql_dify.py` | **A 方权威覆盖** | 场景适配器归 A 方 |
| 15 | `app/clients/report_dify.py` | **A 方权威覆盖** | 场景适配器归 A 方 |
| 16 | `scripts/sql/all.sql` | **以 B 方为基础合并** | B 方 31 张表为超集；核对 `user_account` 段与 A 方描述一致（见 3.2） |
| 17 | `.env` / `environment.yml` / `.gitignore` | **取并集** | `.env` 双方密钥合并（仅本机，不提交）；依赖声明取并集；`.gitignore` 用 B 方版（已含 `.env` 防泄露） |

**命名冲突的另一面**：`agent.py`、`README.md`、`__init__.py` 等文件名在不同目录下各司其职（如 `api/agent.py` 路由层 vs `models/agent.py` ORM 层），属正常分包，**不冲突、不改名**，合并时按目录整体保留即可。

---

## 三、数据库表结构及关联关系

### 3.1 合并后表清单（31 张，唯一 DDL 来源：`scripts/sql/all.sql`）

| 分组 | 表 | 归属模块 | 用途 |
|---|---|---|---|
| **公共账号（1）** | `user_account` | A 方 | 统一登录账号，`identity_type` 关联三种业务身份 |
| **客服 Agent（6）** | `course_project`、`lecture_event`、`event_signup`、`faq`、`chat_session`、`chat_message` | B 方 | 课程/活动/报名/FAQ/会话/消息 |
| **企业组织（12）** | `org_department`、`employee`、`customer_profile`、`customer_followup`、`employee_daily_report`、`student_staff_binding`、`student_score`、`service_ticket`、`service_ticket_record`、`knowledge_entry`、`business_notification`、`operation_log` | 企业模块 | 组织/客户/工单/知识/通知/审计 |
| **学生助手（9）** | `student_profile`、`student_admin_service`、`mental_health_profile`、`mental_warning`、`student_academic_event`、`student_academic_reminder`、`student_application_progress`、`student_notification`、`student_service_action` | 学生模块 | 学生主档/请假/心理/学业/通知 |
| **智能报告（3）** | `report_config`、`report_record`、`report_metric` | 报告模块 | 报告配置/生成记录/指标 |

> 合并后**不新建表、不删表**：B 方 `all.sql` 已是双方并集的超集，A 方所需的 `user_account`、`employee`、`customer_profile`、`student_profile` 均在册。

### 3.2 `user_account` 字段核对（合并关键冲突点）

A 方描述（mrz.md）与 B 方 `all.sql` 定义逐项核对：

| 字段 | B 方 all.sql | A 方描述 | 结论 |
|---|---|---|---|
| `user_id` | BIGINT 自增主键 | 用户主键 | ✅ 一致 |
| `username` | VARCHAR(64) 唯一 | 登录用户名唯一 | ✅ 一致 |
| `password_hash` | VARCHAR(255) | 密码哈希，禁明文 | ✅ 一致 |
| `identity_type` | VARCHAR(20)，CHECK 限定 admin/employee/customer/student | admin/employee/customer/student 四类 | ✅ 一致 |
| `employee_id` / `customer_id` / `student_id` | BIGINT，可空，分别 FK → `employee` / `customer_profile` / `student_profile` | 同名关联 | ✅ 一致 |
| `created_at` / `updated_at` | DATETIME(3)，UTC | — | ✅ 兼容 |
| 约束 `ck_user_identity_link` | 三种身份外键有且仅有一个非空 | “一个账号一种身份” | ✅ 一致 |

**结论：无字段冲突，B 方 DDL 可直接作为合并基准。** 若 A 方实际 DDL 存在差异字段（拿到对方代码后核对），按“增量补充”处理：在 `all.sql` 与 ORM 中同址追加，不改动既有字段含义。

### 3.3 表关联关系（外键全景）

```text
user_account ──┬─ employee_id ──────► employee ──────────► org_department
               ├─ customer_id ─────► customer_profile ───► org_department
               └─ student_id ──────► student_profile ─────► org_department
                                                     └─► customer_profile（customer_id）

【客服 Agent】
lecture_event ◄── event_signup（event_id，FK fk_signup_event）
chat_session ◄── chat_message（session_id，FK fk_message_session）

【学生助手】
student_profile ◄── student_admin_service / mental_health_profile / student_academic_event /
                   student_academic_reminder / student_application_progress /
                   student_notification / student_service_action
student_profile ◄── mental_warning（经 mental_health_profile 间接关联）
employee ◀── student_staff_binding ──▶ student_profile

【企业/审计】
student_profile ◄── student_score / service_ticket
employee / org_department ◄── service_ticket / service_ticket_record / business_notification / operation_log

【报告】
report_config ◄── report_record ◄── report_metric
```

**关联冲突及解决**：

| 冲突点 | 情况 | 解决方案 |
|---|---|---|
| `event_signup` 去重方式 | B 方已废除 `(event_id, customer_phone)` 数据库唯一约束，改**状态式去重**（`status=有效` 判重），支持取消后重新报名 | 以 B 方为准；A 方不涉及该表，无冲突 |
| `chat_message → chat_session` 外键 | ORM 未声明关系，同事务 INSERT 顺序不定会撞外键 | 已在 `_ensure_session` 中 `flush` 父行解决；合入 A 方 `database.py` 后需回归此场景 |
| `user_account` 三身份外键 | 双方 CHECK 约束一致 | 无需处理 |
| 时区 | 全库 UTC（连接设 `time_zone='+00:00'`） | 合并后维持，新增表沿用 |

---

## 四、功能联动设计与调用流程

### 4.1 功能清单与联动点

| 联动点 | 方向 | 状态 | 说明 |
|---|---|---|---|
| 客服对话 → Dify 传输层 | B → A | ✅ **已实现** | `RealDifyClient` 调用 A 方 `core/dify.py` 的 `DifyHttpClient.post_json_sync` 打 `/workflows/run`；合并后为仓内 native 调用 |
| 客服接口 → 统一返回/日志/配置/数据库 | B → A | ✅ **已实现** | `success()/BusinessException`、`get_logger`、`settings`、`get_db` 全部复用公共能力 |
| mock/real 一键切换 | B 自带 | ✅ **已实现** | `.env` 的 `DIFY_CLIENT=mock\|real`，接口签名与数据流不变 |
| 对话接口可选识别 JWT | B ⇄ A | 🔧 **建议实现** | `/agent/chat` 保持 public；若请求带有效 Bearer Token，则将身份记入 `chat_session.user_id`，无效/无 Token 仍按匿名放行。**向后兼容**，不改接口签名 |
| 报名留资联动 | B → 企业模块 | 🔧 **建议实现（需业务确认）** | `signup` 成功后，将姓名/手机号按 `customer_profile.phone_lookup_token` 去重写入客户表（`source_channel='客服对话'`、`source_reference=event_signup.id`），沉淀私域流量 |
| 报名审计联动 | B → 企业模块 | 🔧 **建议实现** | `signup` 写 `operation_log`（操作者、幂等键、前后快照），复用现有审计表 |
| 报名通知联动 | B → 企业模块 | 🔧 **建议实现** | 报名后向负责顾问发 `business_notification` 站内待办 |
| 权限预留 | A → B | 📌 **已预留** | A 方 `access_control.yaml` 的 `customer` 身份已配 `course_project.read`、`event_signup.create` 两个权限标识——正是为客服 Agent 的课程/报名预留；将来 `signup` 如需升级为 visitor 级鉴权，直接 `Depends(require_permission("event_signup.create"))` 即可，无需改权限配置 |

> 图例：✅ 已实现（合并后原生生效）｜🔧 建议实现（本文设计，待确认后排期）｜📌 配置已就绪

### 4.2 调用流程

**流程 1：匿名访客对话（当前态，合并后不变）**

```
访客浏览器
  │ POST /api/v1/agent/chat（无 Token，public）
  ▼
agent_service.run_chat
  ├─ 确保会话（chat_session，新建即 flush）
  ├─ user 消息落库（先 commit，防 Dify 失败丢留资）
  ├─ get_dify_client().chat()                     ← DIFY_CLIENT=real
  │    └─ RealDifyClient → DifyHttpClient.post_json_sync
  │         └─ POST http://127.0.0.1/v1/workflows/run（客服Agent 工作流）
  │              └─ data.outputs → intent / reply（_strip_reasoning 清洗思维链）
  │              异常 → 兜底话术（FALLBACK_REPLY）
  ├─ assistant 消息落库
  └─ 返回 { session_id, intent, reply, need_action, action }
```

**流程 2：登录用户对话（联动增强后）**

```
访客浏览器（已登录，带 Authorization: Bearer <JWT>）
  │ POST /api/v1/agent/chat（仍为 public，Token 可选）
  ▼
agent_service.run_chat
  ├─ 可选解析 JWT（复用 core/auth.py 的 decode 能力）：
  │     有效 → chat_session.user_id 记录身份；无效/无 → 匿名，不报错
  ├─ 其余同流程 1
```

**流程 3：活动报名闭环（现状 + 留资/审计联动）**

```
前端凭 action.type=show_events 调 GET /agent/events 展示列表
  │ 用户填写姓名/手机号
  ▼
POST /agent/events/signup（public）
  ├─ SELECT ... FOR UPDATE 行锁 lecture_event（防超卖）
  ├─ 校验：存在 / 报名中 / 名额未满 / 状态式防重
  ├─ 事务：INSERT event_signup + lecture_event.signed_count + 1
  ├─【联动】写 operation_log 审计
  ├─【联动】按 phone_lookup_token 去重写 customer_profile 留资
  └─【联动】business_notification 通知负责顾问
```

**流程 4：JWT 登录鉴权（A 方模块自身，合并后服务全仓库）**

```
POST /api/v1/auth/login（账号密码）
  ├─ auth_service.authenticate：查 user_account + verify_password（argon2）
  ├─ create_access_token：HS256 签发（AUTH_SECRET_KEY，有效期 AUTH_TOKEN_EXPIRE_MINUTES）
  └─ 返回 access_token / token_type / expires_in

受保护接口（如未来的 visitor 级 signup）：
  Depends(require_permission("event_signup.create"))
  ├─ get_current_account 校验 JWT → user_id → 查 user_account 得 identity_type
  ├─ permissions_for(identity_type) 对照 access_control.yaml
  └─ 无 Token 401 / 无权限 403；业务条件由业务服务再校验

---

## 五、合并步骤（有序 Checklist）

| 步骤 | 动作 | 完成标准 |
|---|---|---|
| 0 | 基线确认：以 B 方仓库为合并基座；向 A 方索取 `D:\AI\StuProject` 最新代码（或确认 B 方副本为最新） | 双方代码版本对齐，本文冲突表可执行 |
| 1 | 按 2.2 表合入 17 个同名文件（A 权威 10 个覆盖、B 保留 2 个、合并 3 个、并集 2 个） | 无遗漏、无反向覆盖 |
| 2 | 核对 `user_account`：A 方 ORM/DDL 与 B 方 `all.sql` 逐字段 diff | 与 3.2 结论一致，有差异按增量补充 |
| 3 | 合并 `app/main.py`：挂载 auth + agent 路由（student_leave/report 按进度） | 启动无 Import 错误，OpenAPI 见全部预期路径 |
| 4 | 合并 `.env` / `environment.yml`：配置与依赖取并集；`.gitignore` 确认忽略 `.env` | 应用本机启动通过 |
| 5 | 功能回归：① A 方登录/权限接口联调（登录→拿 Token→访问受保护接口→401/403 边界）② B 方客服 29 项接口回归 + Dify 7 场景联调 | 两侧测试全绿 |
| 6 | 执行数据迁移（见第六章，如双方有独立数据库） | 迁移校验通过 |
| 7 | 按需实施 4.1 中的 🔧 建议联动点（每项独立提测） | 联动功能测试通过 |
| 8 | 归档：本文档随合并提交；更新《客服Agent-接口与代码总览》接口清单 | 文档与代码一致 |

## 六、数据迁移方案

**场景判定**：若 A 方仅有代码、未落独立库（当前了解大概率如此），**跳过数据迁移，只做结构合并**；若 A 方已有运行数据，按下列流程：

1. **迁移前备份**：A、B 两个库各自全量备份（`mysqldump`），确认可还原；
2. **建目标库**：用合并后的 `scripts/sql/all.sql` 在目标库建表（31 张，含 `user_account`）；
3. **盘点导出**：导出 A 方 `user_account` 等独有数据（`mysqldump --no-create-info`）；
4. **ID 冲突处理**：
   - 目标库为空 → 直接导入；
   - 目标库已有账号 → 建立 **user_id 偏移映射表**，同步调整 `employee_id/customer_id/student_id` 等关联外键，保持 `ck_user_identity_link` 约束成立；
5. **凭据兼容**：确认 argon2 哈希参数一致（密码哈希可直接沿用）；**统一 `AUTH_SECRET_KEY`**——否则 A 方已签发的 JWT 全部失效，需引导用户重新登录；
6. **校验**：行数比对、外键检查（`CHECK_CONSTRAINTS`）、抽样登录验证、受保护接口鉴权验证；
7. **双跑对比**：迁移期间双方服务只读跑通，确认无回归后切流；
8. **回滚预案**：任一步失败，恢复第 1 步备份，保留旧库只读。

## 七、向后兼容保障

| 承诺 | 说明 |
|---|---|
| 客服 6 接口签名不变 | 请求/响应结构、public 匿名访问策略不变；新增能力（如 JWT 识别）只做可选增强 |
| A 方 3 接口不变 | 登录/公开清单/我的权限行为不变 |
| 已签发 JWT 保持有效 | 合并后用同一 `AUTH_SECRET_KEY` 与有效期配置 |
| mock/real 开关不变 | `DIFY_CLIENT` 语义不变，测试链路不中断 |
| 其他模块按进度启用 | student_leave/report 等文件保留，main.py 中按进度挂载，不影响已启用功能 |
| Dify 资产不变 | 客服 DSL、知识库、dataset_ids 绑定关系不变 |

## 八、注意事项与待确认项

**注意事项**：

1. **覆盖方向**：合入 A 方文件时，切勿用 B 方早期副本反向覆盖 A 方权威件（2.2 表是唯一依据）；
2. **`.env` 安全**：含双方真实密钥，只留本机；提交前确认 `.gitignore` 已忽略（B 方已修复），如历史已提交过需 `git rm --cached .env`；
3. **`user_account` 核对**：A 方实际代码到手后必须重做 3.2 的字段核对，本文结论基于 mrz.md 描述；
4. **每步回归**：每合入一组文件跑一次测试（A 方登录联调 + B 方 29 项回归），避免最后算总账；
5. **`enterprise_student` 模块未创建**：main.py 中保留 TODO 注释，模块就绪后取消注释；
6. **异常出口未完全统一**（mrz.md 已记录）：HTTPException/参数校验异常的全路径信封化以 A 方 `response.py` 为准继续完善，不在本次合并扩大范围；
7. **`employee` 的 `report.read` 权限**与报告方案“仅管理层”要求存在差异（mrz.md 提出），由 A 方与报告负责人对齐后调整 `access_control.yaml`。

**待确认项**：

| # | 事项 | 影响 |
|---|---|---|
| 1 | 报名留资联动（写 `customer_profile`）是否本期实施 | 影响私域流量沉淀节奏；不做则客服数据仅存 `event_signup` |
| 2 | `signup` 是否升级为 visitor 级鉴权 | 影响前端流程（需先登录/留资）；权限标识已预留，升级成本低 |
| 3 | A 方是否存在真实账号数据需要迁移 | 决定第六章是否执行 |
| 4 | A 方代码最新版本获取方式（推送 git / 打包发送） | 决定合并步骤 0 的工期 |
```
