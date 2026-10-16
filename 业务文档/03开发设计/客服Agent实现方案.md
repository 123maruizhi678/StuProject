# 客服Agent 实现方案

> 前提说明：当前仓库无应用代码、无部署环境。本方案按「**先跑通 FastAPI 后端 + MySQL，Dify 用 mock 占位**」的节奏编写，待 Dify 与知识库就绪后再逐步替换 mock。
> 本文只覆盖客服Agent 一个模块，与《开发设计文档》第三章、《接口设计文档》第三章、《数据库设计文档》第三章对应，并补齐其中缺失的部分。

---

## 一、范围与目标

客服Agent 覆盖 7 大场景，按「是否有副作用」分两类，落地方式不同：

| 场景 | 数据位置 | 是否有写库副作用 | 实现位置 |
|:---|:---|:---:|:---|
| 公司信息咨询 | 知识库 | 无 | 纯 Dify（RAG） |
| 公司业务查询 | 知识库 | 无 | 纯 Dify（RAG） |
| 海外留学政策查询 | 知识库 | 无 | 纯 Dify（RAG） |
| 课程与项目推荐 | MySQL `course_project` | 无 | Dify 生成话术 + FastAPI 查库 |
| 活动与讲座报名 | MySQL `lecture_event` / `event_signup` | **有** | **FastAPI 接口** |
| 常见问题 FAQ | FAQ 库 | 无 | 纯 Dify（问答对） |
| 日常闲聊 | 人设 Prompt | 无 | 纯 Dify |
| （隐式）会话记录 / 留资 | MySQL `chat_session` / `chat_message` | 有 | FastAPI 在对话入口落库 |

**本期落地范围**（先跑通后端）：

1. FastAPI 后端接口：客服对话入口、活动列表、活动详情、活动报名、课程列表、会话记录落库。
2. 数据库：客服相关 6 张业务表建好并初始化测试数据。
3. Dify 侧：先以 `MockDifyClient` 占位，返回写死的「意图 + 回复」，保证后端闭环可自测；后续换成真实 `DifyClient`，后端接口与数据流不变。

**暂不落地**（Dify/外部资料就绪后再做）：知识库构建与 RAG 检索、七类意图识别模型、闲聊人设 Prompt、真实 Dify Chatflow 编排。

---

## 二、架构与数据流

```
访客浏览器
   │  SSE 流式（客服对话窗口）
   ▼
FastAPI（编排 + 执行 + 落库）
   │  chat / events / signup / courses
   ├──────────────► Dify（意图识别 + RAG + 话术生成）   ← 本期用 Mock
   │
   └──────────────► MySQL（课程、活动、报名、会话、消息）
```

**职责边界（沿用平台总原则）**：

- Dify 只做「理解意图 + 检索知识 + 生成话术」，**不直接连业务库**。
- FastAPI 是唯一落库入口，负责报名校验、会话/消息持久化、活动与课程查询。
- MySQL 存结构化业务数据；知识库向量存 Dify 侧。

**一次对话请求的完整链路**（`POST /agent/chat`）：

1. FastAPI 校验用户身份（访客），维护 `session_id`。
2. 将访客消息写入 `chat_message`。
3. 调用 Dify Chatflow（本期 mock），拿到 `intent` + `reply`（含结构化参数，如报名引导）。
4. 将助手回复写入 `chat_message`。
5. 若 `intent` 为 `signup` 等写库类，由前端引导调用对应 REST 接口（报名），不在此对话接口内直接写库。
6. 以 SSE 流式返回给前端（本期先做非流式一次性返回，跑通后再切流式）。

---

## 三、数据放哪的决策

| 数据 | 放 MySQL | 放 Dify 知识库 | 理由 |
|:---|:---:|:---:|:---|
| 课程项目 | ✅ | — | 结构化字段（类别/适用人群/时间/地点），且要精确查询与推荐条件判断 |
| 讲座活动 | ✅ | — | 报名要写库、要校验名额/状态，必须结构化 |
| 报名记录 | ✅ | — | 写操作 + 防重 + 审计，必须落库 |
| 会话 / 消息 | ✅ | — | 留资、回溯、审计 |
| 公司信息 / 业务 / 政策 | — | ✅ | 大段文本，RAG 检索更合适，且有来源可追溯 |
| FAQ | 可选 | ✅ | 建议放 Dify 问答对，走精确/语义匹配；后端 `faq` 表作为兜底查询 |

> 结论：**课程、活动、报名、会话四类数据放 MySQL**，对应后端 4 组接口；公司信息、政策、FAQ、闲聊内容放 Dify，不经过后端。

---

## 四、数据库设计（客服模块）

在《数据库设计文档》第三章基础上补齐字段与约束，新增会话表。以下字段规格与 `scripts/sql/all.sql`、`app/models/agent.py` **完全一致**（三处为同一份定义的三种形态：DDL / ORM / 文档）。

### 4.1 课程项目表 `course_project`

存课程/项目（留学申请、背景提升、语言培训三大类），课程推荐分支的数据源。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| id | BIGINT | 否 | 自增 | 主键 |
| course_name | VARCHAR(128) | 否 | — | 课程名称 |
| category | VARCHAR(32) | 否 | — | 类别：留学申请/背景提升/语言培训 |
| target_audience | VARCHAR(128) | 否 | '' | 适用人群（学历/意向国家等） |
| description | TEXT | 否 | — | 课程简介 |
| location | VARCHAR(128) | 否 | '' | 上课地点 |
| signup_method | VARCHAR(128) | 否 | '' | 报名方式 |
| status | VARCHAR(32) | 否 | '上架' | 状态：上架/下架（仅上架对访客可见） |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间 |
| updated_at | DATETIME(3) | 否 | 当前时间，更新时自动刷新 | 更新时间 |

- 索引：`idx_category_status (category, status)`、`idx_status_time (status, created_at)`——支撑按类别筛选 + 仅取上架的查询。

### 4.2 讲座活动表 `lecture_event`

存近期讲座/分享会/见面会；`quota` 名额上限，`signed_count` 实时已报名人数（报名成功由接口 +1），`status` 控制能否报名。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| id | BIGINT | 否 | 自增 | 主键 |
| event_name | VARCHAR(128) | 否 | — | 活动名称 |
| event_type | VARCHAR(16) | 否 | — | 线上/线下 |
| start_time | DATETIME | 否 | — | 开始时间 |
| location | VARCHAR(128) | 否 | '' | 地点 |
| signup_method | VARCHAR(128) | 否 | '' | 报名方式 |
| quota | INT | 否 | 0 | 名额（0 表示不限） |
| signed_count | INT | 否 | 0 | 已报名人数 |
| status | VARCHAR(32) | 否 | '报名中' | 状态：报名中/已满/已结束 |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间 |
| updated_at | DATETIME(3) | 否 | 当前时间，更新时自动刷新 | 更新时间 |

- 索引：`idx_status_start (status, start_time)`——支撑「报名中 + 按时间排序」的列表查询；`idx_start_time (start_time)`。

### 4.3 活动报名表 `event_signup`

访客在对话中完成报名的落库记录，是「报名闭环」的凭证。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| id | BIGINT | 否 | 自增 | 主键 |
| event_id | BIGINT | 否 | — | 活动ID（外键 → `lecture_event.id`） |
| customer_name | VARCHAR(64) | 否 | — | 客户姓名 |
| customer_phone | VARCHAR(32) | 否 | — | 客户手机号（判重依据） |
| customer_info | JSON | 是 | NULL | 客户扩展信息（意向国家、学历等） |
| signup_time | DATETIME | 否 | 当前时间 | 报名时间 |
| source | VARCHAR(32) | 否 | '客服对话' | 来源渠道 |
| status | VARCHAR(32) | 否 | '有效' | 状态：有效/取消 |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间 |

- 外键：`fk_signup_event (event_id) → lecture_event(id)`。
- 索引：`idx_event_status (event_id, status)`、`idx_signup_time (signup_time)`。
- **去重策略（重要，已变更）**：**不建 `(event_id, customer_phone)` 唯一约束**，改为**状态式去重**——仅当存在 `status=有效` 的报名记录时才拒绝；用户取消报名（`status=取消`）后可重新报名。早期方案用数据库唯一约束，会导致「取消后再报名」撞索引，故废弃。

### 4.4 FAQ 问答对表 `faq`

存申请流程、费用、退费等高频问题标准答案，供 FAQ 兜底查询（知识库未覆盖时兜底）。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| id | BIGINT | 否 | 自增 | 主键 |
| question | TEXT | 否 | — | 问题 |
| answer | TEXT | 否 | — | 答案 |
| category | VARCHAR(32) | 否 | '' | 分类 |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间 |

- 索引：`idx_category (category)`。

### 4.5 客服会话表 `chat_session`

一个访客一次进店咨询 = 一条会话；`session_id`（UUID）是贯穿多轮对话的主线，前端首访不带、之后带回即可续上同一会话。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| id | BIGINT | 否 | 自增 | 主键 |
| session_id | VARCHAR(64) | 否 | — | 会话唯一标识（UUID），**唯一索引 `uk_session_id`** |
| user_id | VARCHAR(64) | 否 | '' | 访客标识（匿名或留资后） |
| channel | VARCHAR(32) | 否 | 'web' | 渠道（web 等） |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间 |
| updated_at | DATETIME(3) | 否 | 当前时间，更新时自动刷新 | 更新时间 |

- 索引：`uk_session_id (session_id)` 唯一索引、`idx_user_id (user_id)`、`idx_updated_at (updated_at)`。

### 4.6 客服消息表 `chat_message`

会话内每一条消息，`intent` 记录 Dify 识别的意图，用于审计、意图分布统计与对话追溯。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| id | BIGINT | 否 | 自增 | 主键 |
| session_id | VARCHAR(64) | 否 | — | 关联会话（外键 → `chat_session.session_id`） |
| role | VARCHAR(16) | 否 | — | user / assistant |
| intent | VARCHAR(32) | 否 | '' | 意图标签（由 Dify 返回；兜底时为空） |
| content | TEXT | 否 | — | 消息内容 |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间 |

- 外键：`fk_message_session (session_id) → chat_session(session_id)`。
- 索引：`idx_session_time (session_id, created_at)`——按会话取历史消息；`idx_intent (intent)`——意图统计。
- **实现注意**：ORM 未声明外键关系，插入时必须保证父行（`chat_session`）先落库——`_ensure_session` 新建会话后立即 `flush`，否则同事务内 INSERT 顺序不定会触发外键违例。

> 注：`knowledge_vector` 知识库向量表实际存储在 Dify 侧，后端本期不建；若后续自建 RAG 再补。

---

## 五、后端接口设计

基础路径 `/api/v1`，通用响应 `{code, message, data}`。

| 接口 | 方法 | 说明 | 本期是否必须 |
|:---|:---|:---|:---:|
| `/agent/chat` | POST | 客服对话入口（透传 Dify，落库会话+消息） | ✅ |
| `/agent/events` | GET | 活动列表（按状态/时间筛选） | ✅ |
| `/agent/events/{id}` | GET | 活动详情 | 可选 |
| `/agent/events/signup` | POST | 活动报名（校验+防重） | ✅ |
| `/agent/courses` | GET | 课程/项目列表（按类别筛选） | ✅ |
| `/agent/faq` | GET | FAQ 查询（兜底） | 可选 |

### 5.1 客服对话 `POST /agent/chat`

请求：

```json
{ "session_id": "uuid", "user_id": "anon-001", "message": "你们最近有什么留学讲座？" }
```

响应（本期非流式；后续换 SSE）：

```json
{
  "code": 0, "message": "success",
  "data": {
    "session_id": "uuid",
    "intent": "event_query",
    "reply": "近期有以下讲座…",
    "need_action": true,
    "action": { "type": "show_events", "payload": {} }
  }
}
```

处理要点：入参校验 → 写 user 消息 → 调 Dify（mock）→ 写 assistant 消息 → 返回。`intent` 与结构化 `action` 供前端决定是否引导到报名接口。

### 5.2 活动列表 `GET /agent/events?status=报名中`

响应：返回 `status=报名中` 的活动数组，字段同 `lecture_event`（不含敏感/内部字段）。

### 5.3 活动报名 `POST /agent/events/signup`

请求：

```json
{ "event_id": 1, "customer_name": "张三", "customer_phone": "13800000000" }
```

处理要点（业务规则必须在后端）：

1. 校验活动存在且 `status=报名中`，否则返回 400。
2. 校验是否已满：`signed_count >= quota`（quota>0 时）则拒绝。
3. **行锁串行化**：`SELECT ... FOR UPDATE` 锁住活动行，并发报名串行处理，防止名额超卖与计数丢失。
4. **防重（状态式）**：查 `(event_id, customer_phone)` 且 `status=有效` 的记录，存在则返回「已报名」；已取消的记录不阻挡重新报名（故不建数据库唯一约束，见 4.3）。
5. 事务内插入 `event_signup` 并 `signed_count + 1`，失败一起回滚。
6. 返回 `signup_id` 与 `signup_time`（响应不含手机号明文）。

### 5.4 课程列表 `GET /agent/courses?category=语言培训`

响应：返回 `status=上架` 的课程数组，供推荐分支查询。

### 5.5 FAQ 查询 `GET /agent/faq?question=申请流程`

响应：返回最匹配的一条问答对（后端兜底；主流程走 Dify）。

---

## 六、Dify 侧设计（含 mock 方案）

### 6.1 目标 Chatflow 结构（Dify 就绪后）

问题分类器把意图分为 7 分支：

| 分支 | 处理 | 是否回调 FastAPI |
|:---|:---|:---:|
| 公司信息 / 业务 / 政策 | RAG 检索知识库 | 否 |
| 课程推荐 | 条件判断 → 话术生成 | 查 `/agent/courses`（HTTP 工具节点） |
| 活动查询 / 报名 | 报名引导 | 查 `/agent/events`、调 `/agent/events/signup` |
| FAQ | 问答对匹配 | 否（可兜底 `/agent/faq`） |
| 闲聊 | 年轻化人设 Prompt | 否 |

### 6.2 mock 阶段的抽象

后端通过 `DifyClient` 接口隔离 Dify，避免污染业务代码：

```python
class DifyClient(Protocol):
    async def chat(self, session_id: str, message: str) -> ChatResult: ...

class MockDifyClient:   # 本期使用
    async def chat(self, session_id, message):
        # 按关键词硬编码意图与回复，覆盖 7 大场景的典型问法
        ...

class RealDifyClient:   # Dify 就绪后实现，走 Dify /chat-messages 或 /workflows/run
    ...
```

- `ChatResult` 结构统一：`{intent, reply, action}`，后端逻辑不感知 mock 还是真实。
- 通过 `.env` 的 `DIFY_CLIENT=mock|real` 切换，接口签名不变，实现可平滑替换。

---

## 七、项目目录结构

```
backend/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 配置（MySQL 连接、DIFY_CLIENT 开关）
│   ├── api/                    # 路由
│   │   └── agent.py            # 客服 Agent 相关路由
│   ├── services/
│   │   ├── chat_service.py     # 对话编排
│   │   ├── event_service.py    # 活动/报名业务
│   │   ├── course_service.py   # 课程查询
│   │   └── dify/
│   │       ├── base.py         # DifyClient 抽象 + ChatResult
│   │       ├── mock.py         # MockDifyClient
│   │       └── real.py         # RealDifyClient（后补）
│   ├── models/                 # SQLAlchemy ORM
│   ├── schemas/                # Pydantic 请求/响应
│   └── db.py                   # 数据库会话
├── requirements.txt
└── .env.example
```

---

## 八、实现步骤

### 阶段 0：环境准备
1. 装 Python 虚拟环境，安装 FastAPI、uvicorn、SQLAlchemy、pymysql/aiomysql、pydantic。
2. 装 MySQL，建库 `education_agent`（utf8mb4，东八区）。

### 阶段 1：建表与 ORM
1. 建 6 张表（课程、活动、报名、FAQ、会话、消息），字段注释写中文。
2. 初始化测试数据：几条课程、几个「报名中」活动、几条 FAQ。
3. 写 SQLAlchemy ORM 模型与 Pydantic Schema。

### 阶段 2：接口实现
1. 先做「读」接口：`GET /agent/events`、`GET /agent/courses`、`GET /agent/faq`。
2. 再做「写」接口：`POST /agent/events/signup`（含校验、防重、事务）。
3. 最后做对话入口：`POST /agent/chat`（接 `MockDifyClient`，落库会话+消息）。

### 阶段 3：mock 联调
1. 用 curl / Postman 打通「问活动 → 返回列表 → 报名 → 落库」闭环。
2. 用写死的 mock 意图覆盖 7 大场景，验证 `intent` + `action` 正确。

### 阶段 4：接真实 Dify（后置）
1. Dify 建知识库、Chatflow（7 分支），生成 API Key。
2. 实现 `RealDifyClient`，切换 `.env` 的 `DIFY_CLIENT=real`。
3. 对话接口从非流式切 SSE，前端客服窗口接流式渲染。

---

## 九、测试要点

| 项 | 验证内容 |
|:---|:---|
| 报名校验 | 活动不存在/已结束/已满 → 拒绝；重复手机号（有效记录）→ 去重 |
| 报名幂等 | 相同手机号连点两次不重复入库；取消后可重新报名 |
| 并发报名 | 8 线程抢 quota=1 仅 1 人成功，`signed_count` 不超卖（行锁） |
| 对话落库 | user/assistant 消息各一条，`intent` 正确写入 |
| mock 覆盖 | 7 大场景各至少一条用例，返回意图与回复匹配 |
| 数据隔离 | 接口不返回报名表手机号等敏感字段（对外脱敏） |

---

## 十、待确认项

1. **课程推荐的数据口径**：推荐是按「学历背景 + 意向国家」条件查询，还是先全量列表由 Dify 话术层筛选？建议先做简单条件查询，后续再上 NL2SQL。
2. **留资时机**：报名时收集姓名+手机号，是否还要其它字段（意向国家、学历）？需与业务方确认。
3. **活动名额**：`quota=0` 是否代表不限名额，需业务确认语义。
4. **会话用户标识**：匿名访客与留资后的用户如何关联（同一 `user_id` 归属），需定义规则。
5. **前端是否本期做**：本期聚焦后端，前端客服对话窗口是否并行开发，待定。
