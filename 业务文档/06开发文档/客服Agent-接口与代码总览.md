# 客服Agent 接口与代码总览（对外开放模块）

> 本文档回答四个问题：6 个接口各有什么功能、Dify 是由哪个接口怎么调起来的、客服Agent 相关代码都写在哪里、这些代码各有什么用处。
> 关联文档：《客服Agent 需求文档》《客服Agent 实现方案》《客服Agent-Dify-Chatflow搭建方案》。

---

## 一、模块概述

客服Agent 是面向访客与潜在客户的 7×24 小时智能客服，覆盖七大场景：公司信息咨询、公司业务查询、海外留学政策查询、课程与项目推荐、活动与讲座报名、常见问题自助解答（FAQ）、日常闲聊互动。

**总体架构（前端 → 后端 → Dify/MySQL）**：

```
访客浏览器（客服对话窗口）
   │  6 个接口，匿名直连，无登录无鉴权
   ▼
FastAPI 后端（编排 + 落库 + 唯一写库入口）
   ├── POST /v1/workflows/run ──► Dify「客服Agent」工作流（意图识别 + 知识检索 + 话术生成）
   │
   └── MySQL：course_project / lecture_event / event_signup / faq / chat_session / chat_message
```

**职责边界**：Dify 只做「理解意图 + 检索知识 + 生成话术」，不连业务库、不写库；FastAPI 是唯一落库入口；课程/活动列表数据不经过 Dify，由前端拿到 `action` 后直接调后端接口获取。

---

## 二、对外开放设计（无用户体系、无权限控制）

### 2.1 设计原则

本模块**完全对外开放**：

- **无用户体系**：不区分访客/员工/学生，不建立账号概念；
- **无权限控制**：6 个接口全部匿名直连，不需要登录、不需要 Token、不做任何身份认证；
- **无访问级别**：不存在 public/visitor/authenticated 之分，一个接口一种行为——谁来都能用。

### 2.2 为什么这样设计

业务目标是 7×24 小时无人值守客服：访客打开网页就能问，任何登录门槛都会直接损失潜在客户。平台虽有统一 JWT 认证机制，但**本模块不接入、不校验**。

### 2.3 安全与防护（运维层，非权限）

不设权限不等于不设防。防护集中在运维层，重点是「限流 + 防刷 + 敏感数据脱敏」：

| 接口 | 防护重点 |
|---|---|
| `POST /agent/chat` | IP 限流（防止刷 LLM 调用成本） |
| `POST /agent/events/signup` | **最严**：IP 强限流 + 状态式防重 + 手机号格式校验（可选验证码）。这是唯一的「写库 + 采集个人信息」接口，且响应只返回 `signup_id`，不回传手机号明文 |
| 其余 4 个读接口 | 公开信息，正常限流即可 |

> 落库数据中的手机号后续可在 DB 侧加密存储（密文 + 检索 token），与客户数据安全要求对齐。

---

## 三、接口功能清单

基础路径 `/api/v1`，统一响应信封 `{"code": 0, "message": "success", "data": ...}`（业务错误 HTTP 200 + `code` 非 0）。

| # | 方法 | 路径 | 功能 | 必需性 |
|---|---|---|---|---|
| 1 | POST | `/agent/chat` | **客服对话主入口**：接收访客消息 → 调 Dify 得到意图与话术 → 按意图推导前端动作 → 会话/消息落库 | 核心 |
| 2 | GET | `/agent/events` | 活动列表（支持 `?status=报名中` 筛选） | 核心 |
| 3 | GET | `/agent/events/{event_id}` | 活动详情 | 可选（列表字段够用时可不用） |
| 4 | POST | `/agent/events/signup` | 活动报名：活动状态/名额校验、状态式防重、行锁防超卖、事务写库 | 核心 |
| 5 | GET | `/agent/courses` | 课程列表（仅上架，支持 `?category=` 筛选），课程推荐分支数据源 | 核心 |
| 6 | GET | `/agent/faq` | FAQ 兜底查询（关键词模糊匹配，无命中返回第一条） | 兜底（主路径由 Dify FAQ 知识库承担） |

**接口 1（chat）的请求/响应**：

```json
// 请求
{"session_id": "可选，复用会话", "user_id": "可选，访客标识", "message": "最近有什么讲座可以报名？"}

// 响应 data
{
  "session_id": "0d3f8bb8...",
  "intent": "event_query",                 // 7 大意图英文 slug
  "reply": "近期有以下留学讲座，您可以直接在下方报名～",
  "need_action": true,
  "action": {"type": "show_events", "payload": {}}   // show_courses / show_events / 无
}
```

前端根据 `action.type` 二次调接口 2 或 5 取数展示；报名由前端调接口 4 完成闭环。**前端从不直连 Dify。**

---

## 四、Dify 调用关系

### 4.1 哪个接口调用 Dify

**只有接口 1 `POST /agent/chat` 调用 Dify**，且是唯一的 AI 入口。其余 5 个接口全部只读/只写 MySQL，与 Dify 无关。

### 4.2 完整调用链（代码路径）

```
POST /api/v1/agent/chat
  │
  ├─ app/api/agent.py                chat()                     路由层：参数校验、调 service、包信封
  │
  ├─ app/services/agent_service.py   run_chat()                 业务编排：
  │     1. 确保会话（_ensure_session，新建即 flush 保证外键父行先插入）
  │     2. user 消息先落库并 commit（Dify 失败也不丢留资）
  │     3. try: get_dify_client().chat(sid, message)
  │        except: 记录日志 + 返回兜底话术 FALLBACK_REPLY
  │     4. assistant 消息落库，返回 intent/reply/need_action/action
  │
  ├─ app/services/dify_client.py     get_dify_client()          按 .env 的 DIFY_CLIENT 选实现：
  │     ├─ "mock" → MockDifyClient（关键词硬编码 7 场景，无外部依赖）
  │     └─ "real" → RealDifyClient（真正调 Dify）
  │           chat():
  │             payload = {"inputs": {"query": 消息}, "response_mode": "blocking",
  │                        "user": "visitor-<session_id>"}
  │             → 读回 data.outputs 的 intent / reply
  │             → _strip_reasoning() 剥掉推理模型的思维链（防止客户看到 AI 内心独白）
  │             → 按 _INTENT_ACTION_MAP 推导 action（course_recommend→show_courses，
  │               event_query→show_events，其余无）
  │
  ├─ app/core/dify.py                DifyHttpClient             通用 HTTP 传输层（Bearer 鉴权/超时/错误）
  │
  └─► POST http://127.0.0.1/v1/workflows/run     （Dify「客服Agent」工作流，Workflow 模式）
        入参 inputs.query = 访客消息
        出参 outputs.intent = 意图 slug，outputs.reply = 话术
```

### 4.3 mock / real 切换

`.env` 中 `DIFY_CLIENT=mock|real` 一键切换，接口签名与数据流完全不变（测试用 mock，联调/生产用 real）。real 模式需配置 `DIFY_AGENT_API_KEY`（Dify 控制台「客服Agent」应用 → API 访问页创建）；未配置时对话走兜底话术，不会崩溃。

---

## 五、代码清单与用处

### 5.1 后端代码（`app/`）

| 文件 | 用处 |
|---|---|
| `app/api/agent.py` | **路由层**：定义 6 个接口（`/agent` 前缀），参数校验，调 service，统一信封返回 |
| `app/services/agent_service.py` | **业务层**：对话编排（会话确保、消息落库、Dify 调用兜底）；活动列表/详情；报名（状态校验 + 状态式防重 + `FOR UPDATE` 行锁防超卖 + 事务）；课程列表（仅上架 + 类别筛选）；FAQ 关键词兜底 |
| `app/services/dify_client.py` | **Dify 客户端**：`MockDifyClient`（mock 模式）、`RealDifyClient`（real 模式，走 `/workflows/run`）、思维链清洗、intent→action 映射、`get_dify_client()` 开关 |
| `app/schemas/agent.py` | **数据契约**：请求/响应 Pydantic 模型（`ChatRequest`/`ChatData`/`EventItem`/`SignupRequest`/`CourseItem`/`FaqData` 等） |
| `app/models/agent.py` | **ORM 模型**：6 张表的 SQLAlchemy 映射（`CourseProject`/`LectureEvent`/`EventSignup`/`Faq`/`ChatSession`/`ChatMessage`） |
| `app/main.py` | **应用入口**：注册 agent 路由到 `/api/v1`（`app.include_router(agent_router, ...)`） |
| `app/config.py` | **配置**：客服 Agent 相关项 `DIFY_CLIENT`、`DIFY_AGENT_API_KEY`、`DIFY_API_BASE`、`DIFY_API_TIMEOUT_SECONDS` |
| `app/core/dify.py` | **通用传输层**：`DifyHttpClient`（所有 Dify 调用共用的 JSON POST + Bearer + 超时） |
| `app/database.py` | **数据库入口**：MySQL 引擎、会话工厂、`get_db` 依赖 |
| `app/core/response.py` | **统一响应**：`success()`/`BusinessException`/信封与全局异常处理 |

### 5.2 配置与数据库

| 文件 | 用处 |
|---|---|
| `.env` | 环境配置：`DIFY_CLIENT=real`、`DIFY_AGENT_API_KEY=app-xxxx`、`DIFY_API_BASE`、MySQL 连接 |
| `scripts/sql/all.sql` | 建表脚本：含客服 Agent 6 张表（`course_project`/`lecture_event`/`event_signup`/`faq`/`chat_session`/`chat_message`） |
| `scripts/sql/agent_seed.sql` | 种子数据：7 门课程、4 个活动（报名中×2/已满/已结束）、8 条 FAQ |
| `scripts/reupload_dify_kb.py` | 知识库维护：删除旧文档并按「空行分段」重新上传 4 个知识库 |
| `scripts/test_dify_kb.py` | 知识库验证：4 个库检索命中测试 |
| `scripts/test_workflow_run.py` | 联调脚本：7 场景直接打 Dify `/workflows/run` 验证意图/回复 |

### 5.3 Dify 侧资产（`dify/`）

| 文件 | 用处 |
|---|---|
| `dify/客服Agent-Chatflow.yml` | **工作流 DSL**（Workflow 模式，20 节点）：开始 → 意图分类器（7 类）→ 4 个知识检索 + 7 个话术 LLM → 7 个结束节点（输出 intent/reply）。控制台「导入 DSL」使用 |
| `dify/README.md` | DSL 导入说明：导入步骤、导入后需绑定模型、知识库维护流程、字段对齐、版本兼容提示 |
| `dify/knowledge/README.md` | **知识库文档**：4 个知识库各自的作用、内容范围、源文档、维护流程 |
| `dify/knowledge/公司信息.md` | 「公司信息」知识库内容（机构概况/联系方式/业务板块/部门架构） |
| `dify/knowledge/公司业务.md` | 「公司业务」知识库内容（德国双元制、新加坡本硕升学两大项目全量资料） |
| `dify/knowledge/留学政策.md` | 「留学政策」知识库内容（德国/新加坡签证、学费、奖学金、就业移民） |
| `dify/knowledge/FAQ.md` | 「FAQ」知识库内容（36 条标准问答） |
| `dify/knowledge/dataset_ids.json` | 4 个知识库的 dataset_id/document_id 映射（DSL 绑定依据） |

### 5.4 文档（`业务文档/`）

| 文件 | 用处 |
|---|---|
| `01需求拆解/客服Agent.txt` | 原始需求拆解 |
| `02需求文档/客服Agent.md` | 需求文档：七大场景、功能/非功能需求、验收标准 |
| `03开发设计/客服Agent实现方案.md` | 实现方案：目录结构、接口设计、Dify 侧设计（含 mock 方案）、实现步骤 |
| `03开发设计/客服Agent-Dify-Chatflow搭建方案.md` | Dify 搭建方案：工作流节点设计、输入输出契约、后端对接设计、实施步骤 |
| `06开发文档/接口方案/客服Agent/接口方案.md` | 接口清单（历史版本，含已废弃的身份权限目标态描述，以本文档为准） |
| `06开发文档/bk/客服Agent接口鉴权方案.md` | 接口鉴权接入方案（历史备份，本模块最终未接入鉴权） |

---

## 六、数据表清单（6 张）

| 表 | 说明 | 关键字段 |
|---|---|---|
| `course_project` | 课程项目 | 课程名称、类别、适用人群、时间地点、报名方式、状态 |
| `lecture_event` | 讲座活动 | 活动名称、类型、开始时间、地点、名额、已报名人数、状态 |
| `event_signup` | 活动报名 | 活动ID、客户姓名、手机号、扩展信息、报名时间、状态（有效/取消） |
| `faq` | FAQ 问答对 | 问题、答案、分类 |
| `chat_session` | 客服会话 | session_id（UUID）、访客标识、渠道 |
| `chat_message` | 客服消息 | 会话ID、角色（user/assistant）、意图标签、内容 |

> 去重策略：报名为**状态式去重**（`status=有效` 判重），不建 `(event_id, customer_phone)` 数据库唯一约束——保证用户取消报名后可以重新报名。

---

## 七、相关文档索引

- 需求侧：`业务文档/01需求拆解/客服Agent.txt`、`业务文档/02需求文档/客服Agent.md`
- 设计侧：`业务文档/03开发设计/客服Agent实现方案.md`、`业务文档/03开发设计/客服Agent-Dify-Chatflow搭建方案.md`
- 知识库：`dify/knowledge/README.md`

---

## 八、代码目录结构总览

客服Agent 全部相关文件的一棵树（只列本模块资产，其他模块文件以 `…` 省略）：

```
StuProject/
├── app/                                  # FastAPI 后端应用
│   ├── main.py                           # 应用入口：注册 agent 路由到 /api/v1
│   ├── config.py                         # 配置：DIFY_CLIENT / DIFY_AGENT_API_KEY / DIFY_API_BASE 等
│   ├── database.py                       # MySQL 引擎、会话工厂、get_db 依赖
│   ├── api/
│   │   ├── agent.py                      # 【客服】路由层：6 个接口定义与参数校验
│   │   └── …                             # 其他模块路由（auth / student_leave / report）
│   ├── services/
│   │   ├── agent_service.py              # 【客服】业务层：对话编排/活动/报名/课程/FAQ
│   │   ├── dify_client.py                # 【客服】Dify 客户端：mock/real、思维链清洗、action 映射
│   │   └── …                             # 其他业务服务
│   ├── schemas/
│   │   └── agent.py                      # 【客服】请求/响应 Pydantic 模型
│   ├── models/
│   │   └── agent.py                      # 【客服】ORM 模型：6 张表映射
│   ├── core/
│   │   ├── dify.py                       # DifyHttpClient：所有 Dify 调用共用的 HTTP 传输层
│   │   ├── response.py                   # 统一响应信封 success()/BusinessException
│   │   └── …                             # 日志/鉴权等其他基础组件
│   └── …
│
├── .env                                  # 环境配置：DIFY_CLIENT=real、DIFY_AGENT_API_KEY、MySQL 连接
│
├── dify/                                 # Dify 侧资产
│   ├── 客服Agent-Chatflow.yml            # 工作流 DSL（20 节点，控制台「导入 DSL」用）
│   ├── README.md                         # DSL 导入说明与知识库维护流程
│   └── knowledge/
│       ├── README.md                     # 知识库文档：4 个库的作用与维护方式
│       ├── dataset_ids.json              # 4 个知识库的 dataset_id 映射（DSL 绑定依据）
│       ├── 公司信息.md                   # 「公司信息」知识库内容
│       ├── 公司业务.md                   # 「公司业务」知识库内容
│       ├── 留学政策.md                   # 「留学政策」知识库内容
│       └── FAQ.md                        # 「FAQ」知识库内容（36 条问答）
│
├── scripts/                              # 运维与联调脚本
│   ├── sql/
│   │   ├── all.sql                       # 建表脚本（含客服 6 张表）
│   │   └── agent_seed.sql                # 客服种子数据：课程/活动/FAQ
│   ├── reupload_dify_kb.py               # 知识库一键重新上传（改 knowledge/*.md 后执行）
│   ├── test_dify_kb.py                   # 知识库检索命中验证
│   └── test_workflow_run.py              # 7 场景直连 Dify 联调脚本
│
└── 业务文档/                             # 项目文档
    ├── 01需求拆解/
    │   └── 客服Agent.txt                 # 原始需求拆解
    ├── 02需求文档/
    │   └── 客服Agent.md                  # 需求文档：七大场景与验收标准
    ├── 03开发设计/
    │   ├── 客服Agent实现方案.md          # 实现方案：结构/接口/mock 方案
    │   └── 客服Agent-Dify-Chatflow搭建方案.md  # Dify 搭建与后端对接方案
    └── 06开发文档/
        ├── 客服Agent-接口与代码总览.md   # 本文档
        ├── 接口方案/
        │   └── 客服Agent/
        │       └── 接口方案.md           # 接口清单（历史版，含已废弃的权限描述）
        └── bk/
            └── 客服Agent接口鉴权方案.md   # 鉴权接入方案（历史备份，最终未接入）
```

> 阅读顺序建议：先看 `业务文档/03开发设计/` 两份设计文档理解背景 → 本文档第五节的代码清单逐项对照 → 用 `scripts/` 下脚本做运维与联调。
