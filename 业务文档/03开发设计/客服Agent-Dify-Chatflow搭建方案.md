# 客服Agent Dify 搭建与开发方案

> 关联文档：《客服Agent 需求文档》（七大场景）、《客服Agent 实现方案》（后端/数据库/接口）、《客服Agent接口鉴权方案》。
> 本文是 Dify 侧集成的**统一方案**：既讲「为什么这么选、怎么做、分几步、怎么验收」（工程方案），也含 Dify 控制台的节点配置细节（搭建手册）。

---

## 一、背景与目标

客服Agent 模块当前用 `MockDifyClient`（关键词硬编码 7 大场景）跑通了后端闭环。本方案目标是用**真实的 Dify 工作流**替换 mock：

1. **意图识别**：访客消息 7 选 1（公司信息 / 公司业务 / 留学政策 / 课程推荐 / 活动报名 / FAQ / 闲聊）。
2. **知识库 RAG**：公司信息、业务、政策、FAQ 四类问题严格基于知识库回答，避免幻觉。
3. **话术生成**：7 类场景分别用不同人设/提示词生成自然回复。
4. **平滑替换**：后端接口与数据流不变，仅 `.env` 切 `DIFY_CLIENT=mock → real`。

---

## 二、现状盘点

| 项 | 状态 |
|:---|:---|
| 后端 `MockDifyClient` | ✅ 已实现，覆盖 7 场景关键词 |
| 后端 `RealDifyClient` | ✅ 已实现，走 `/workflows/run` |
| 后端配置项 | ✅ `DIFY_API_BASE` / `DIFY_API_KEY`（NL2SQL）/ `DIFY_AGENT_API_KEY` / `DIFY_CLIENT` |
| Dify 环境 | ✅ 本地 Docker 1.12.1（`dify-api:1.12.1`） |
| DSL 文件 | ✅ `dify/客服Agent-Chatflow.yml`（Workflow 0.5.0，已通过 1.12.1 节点实体校验） |
| 知识库 | ⏳ 待创建 4 个（公司信息/公司业务/留学政策/FAQ） |
| API Key | ⏳ 待导入后申请新 Key |
| 前端客服窗口 | ⏳ 待开发（action 驱动交互） |

> 关键背景：最初方案用 **Chatflow + 变量赋值节点**，但本地 Dify 1.12.1 导入「赋值」节点会前端崩溃（`Application error`），且 Chatflow `/chat-messages` 阻塞响应无 `outputs` 字段。故已改为 **Workflow 模式**。

---

## 三、总体架构与职责边界

```
访客浏览器（客服对话窗口，SSE）
   │  POST /agent/chat
   ▼
FastAPI 后端（编排 + 落库 + 唯一写库入口）
   │  /workflows/run（意图识别 + RAG + 话术生成）
   ├──────────────► Dify 工作流（不连业务库）
   │
   ├── MySQL：course_project / lecture_event / event_signup / faq / chat_session / chat_message
   │
   └── 前端按 action.type 二次调 REST：GET /agent/courses、GET /agent/events、POST /agent/events/signup
```

**职责边界（沿用平台总原则）**：

- **Dify 只做**「理解意图 + 检索知识 + 生成话术」，不连业务库、不写库。
- **FastAPI 是唯一落库入口**：会话/消息持久化、报名校验防重、课程/活动查询。
- **课程/活动列表数据不经过 Dify**：Dify 只生成引导话术，前端拿到 `action` 后直接调后端接口取数并展示。

---

## 四、关键技术决策

| 决策点 | 结论 | 理由 |
|:---|:---|:---|
| 应用类型 | **Workflow（工作流）**，非 Chatflow | `/workflows/run` 返回 `data.outputs`，能拿到 `intent`/`reply`；规避 1.12.1「赋值」节点崩溃 |
| 分支汇流 | **7 个分支各接一个 end 节点** | 去掉「变量赋值」节点，消除崩溃源 |
| intent 取值 | 分类器各类别 `id` 用英文 slug（`company_info` 等），end 输出 `classifier.class_id` | 直接与后端 `ChatResult.intent` 对齐，无需中英映射 |
| action 归属 | **后端按 intent 推导**，Dify 不输出 | 减少 Dify 编排复杂度；课程/活动动作是后端业务概念 |
| 课程/活动数据 | 前端拿 `action` 后调后端 REST | 保持「Dify 不连业务库」边界，写库在后端留痕 |
| 多轮记忆 | 本期不传 `conversation_id`，单轮问答 | 后端 `session_id` 与 Dify `conversation_id` 是两套体系，多轮留待后续落库对接 |

---

## 五、应用基本信息

| 项 | 配置 |
|:---|:---|
| 应用类型 | **Workflow（工作流）**，非 Chatflow、非普通 Chat |
| 应用名称 | 客服Agent |
| 图标/描述 | 自定，如「留学机构 7×24 智能客服」 |
| 模型 | 省成本方案：分类器用轻量模型、生成用中等模型（见 6.7） |

---

## 六、Dify 工作流设计

### 6.1 整体节点结构

```
start(query 输入)
   └─► question-classifier（7 类，id=英文 slug，name=中文）
        ├─ company_info ──► knowledge-retrieval[公司信息] ──► llm[公司信息] ──► end(intent, reply)
        ├─ business_query ─► knowledge-retrieval[公司业务] ──► llm[公司业务] ──► end(intent, reply)
        ├─ policy_query ──► knowledge-retrieval[留学政策] ──► llm[留学政策] ──► end(intent, reply)
        ├─ faq ───────────► knowledge-retrieval[FAQ] ──► llm[FAQ] ──► end(intent, reply)
        ├─ course_recommend ► llm[课程推荐] ──► end(intent, reply)
        ├─ event_query ────► llm[活动引导] ──► end(intent, reply)
        └─ chat ───────────► llm[闲聊] ──► end(intent, reply)
```

节点统计：1 start + 1 classifier + 4 knowledge-retrieval + 7 llm + 7 end = **20 节点，19 边**。

### 6.2 输入/输出契约

- **入参**：`inputs.query`（start 节点变量 `query`，承载访客消息）。
- **出参**（每个 end 节点两个变量）：

| 输出变量 | 取值 | 类型 | 说明 |
|:---|:---|:---|:---|
| `intent` | `classifier.class_id` | string | 英文 slug，与后端 `ChatResult.intent` 一致 |
| `reply` | 该分支 `llm.text` | string | 最终话术 |

- 7 个意图 slug 与后端 `MockDifyClient` 完全一致，切换无感：

```
company_info / business_query / policy_query / course_recommend / event_query / faq / chat
```

### 6.3 准备清单

1. **知识库（Knowledge）**：在 Dify 创建 4 个知识库并上传文档——
   | 知识库 | 文档 |
   |:---|:---|
   | 公司信息 | 《公司信息》（品牌背景、发展历程、成功案例、校区分布） |
   | 公司业务 | 《公司业务》（留学申请、背景提升、语言培训） |
   | 留学政策 | 《留学政策》（各国签证、申请门槛、移民就业政策） |
   | FAQ | 历史高频问答对（申请流程、费用、退费政策等） |
   - 切片建议：自动分段 + 向量化即可，检索 Top-K 取 3，召回阈值用默认或 0.5。

2. **课程/活动数据不经过 Dify**：课程列表、活动列表由前端拿到 `action.type=show_courses/show_events` 后直接调后端接口获取并展示，Dify 里**不放 HTTP 节点**（写库/查业务数据都在后端留痕）。

### 6.4 开始节点（Start）

- 输入字段：`query`（文本，必填，作为访客消息）。
- 后续节点引用：`{{#start.query#}}`（Workflow 模式下开始节点变量用自己的节点 id 引用，不是 Chatflow 的 `sys.query`）。

### 6.5 问题分类器（Question Classifier）

- 类型：问题分类器（Question Classifier）
- 输入变量：`start.query`
- **分类列表（classes）**：每类含 `id`（英文 slug）与 `name`（中文名）：

| id | name |
|:---|:---|
| company_info | 公司信息咨询 |
| business_query | 公司业务查询 |
| policy_query | 海外留学政策查询 |
| course_recommend | 课程与项目推荐 |
| event_query | 活动与讲座报名 |
| faq | 常见问题FAQ |
| chat | 日常闲聊 |

- **分类指令（Instruction）** 填：

```
你是留学教育机构的客服助理，负责判断访客消息属于以下哪一类意图。只输出类别，不要输出其他任何内容。

1. company_info —— 询问公司品牌背景、发展历程、成功案例、校区分布等机构信息
2. business_query —— 询问公司业务板块，如留学申请、背景提升、语言培训等服务项目
3. policy_query —— 询问留学政策，如各国签证要求、院校申请门槛、移民就业政策
4. course_recommend —— 询问课程或项目推荐，如雅思/托福培训、背景提升项目、留学方案
5. event_query —— 询问近期讲座、活动、分享会、招生官见面会，或想报名活动
6. faq —— 询问申请流程、服务费用、退费政策等常见问题
7. chat —— 日常闲聊、打招呼、无明确诉求的情感维系
```

### 6.6 各分支 LLM 配置

| 分支 | 知识检索 | LLM 系统提示词（要点） |
|:---|:---:|:---|
| 公司信息 | 绑定「公司信息」 | 根据资料准确简洁回答公司信息，无答案则建议联系人工客服 |
| 公司业务 | 绑定「公司业务」 | 根据资料介绍业务与服务范围，清晰有条理 |
| 留学政策 | 绑定「留学政策」 | 根据资料准确回答政策问题，不编造 |
| FAQ | 绑定「FAQ」 | 复用 FAQ 标准答案，无匹配则引导人工 |
| 课程推荐 | 无 | 结合背景与意向推荐课程，引导查看下方课程列表 |
| 活动报名 | 无 | 热情介绍讲座活动，引导在下方报名 |
| 日常闲聊 | 无 | 友好闲聊，适时引导到留学/课程/活动话题 |

- 带知识检索的分支，LLM 用户消息引用检索结果：

```
用户问题：{{#start.query#}}

参考资料：
{{#kr_xxx.result#}}
```

- 不带知识检索的分支，LLM 用户消息：`{{#start.query#}}`。
- 课程/活动分支说明：真正的列表由前端拿到 `action` 后调后端接口展示，Dify 只生成引导话术；报名写库由前端调 `POST /agent/events/signup` 完成。

### 6.7 模型选择（省成本方案）

| 节点 | 建议模型 | 理由 |
|:---|:---|:---|
| 问题分类器 | 轻量模型（gpt-4o-mini / claude-haiku 等） | 7 选 1 分类，轻量足够 |
| 7 个生成话术 LLM | 中等模型 | 话术质量要求中等 |

---

## 七、结束节点（7 个，替代原「变量赋值」方案）

每个分支各一个结束节点，输出两个变量：

| 输出变量 | 取值（value_selector） | 类型 |
|:---|:---|:---|
| `intent` | `classifier.class_id` | string |
| `reply` | 该分支 LLM 的 `text` | string |

> 不再使用「变量赋值」节点、不再使用「会话变量」——这是 1.12.1 导入崩溃修复的关键。

---

## 八、后端对接设计

### 8.1 调用实现

`app/services/dify_client.py` 的 `RealDifyClient`（已实现）：

```python
_INTENT_ACTION_MAP = {
    "course_recommend": {"type": "show_courses", "payload": {}},
    "event_query":       {"type": "show_events",  "payload": {}},
}

class RealDifyClient:
    def chat(self, session_id: str, message: str) -> ChatResult:
        payload = {
            "inputs": {"query": message},   # 对应工作流 start 节点 query
            "response_mode": "blocking",
            "user": f"visitor-{session_id}",
        }
        headers = {"Authorization": f"Bearer {self.key}",
                   "Content-Type": "application/json"}
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(f"{self.base}/workflows/run", json=payload, headers=headers)
            resp.raise_for_status()
            outputs = (resp.json().get("data") or {}).get("outputs") or {}
        intent = outputs.get("intent") or "chat"
        return ChatResult(
            intent=intent,
            reply=outputs.get("reply") or "",
            action=_INTENT_ACTION_MAP.get(intent),
        )
```

### 8.2 action 推导规则

| intent | 后端下发的 action |
|:---|:---|
| course_recommend | `{"type":"show_courses","payload":{}}` |
| event_query | `{"type":"show_events","payload":{}}` |
| 其它 | 无 |

后端 `/agent/chat` 响应据此产出 `need_action` 与 `action`。`action` 由后端按 `intent` 推导，**不依赖 Dify 输出**。

### 8.3 与 NL2SQL 工作流的隔离

客服工作流与 NL2SQL 是**两个独立 Dify 应用**，各自独立 Key：

| 配置项 | 用途 |
|:---|:---|
| `DIFY_API_KEY` | NL2SQL 工作流（`/workflows/run`，输出 `sql`） |
| `DIFY_AGENT_API_KEY` | 客服工作流（`/workflows/run`，输出 `intent`/`reply`） |

---

## 九、前端交互设计

前端客服窗口根据 `/agent/chat` 响应的 `action.type` 决定后续交互：

| action.type | 前端行为 |
|:---|:---|
| `show_courses` | 调 `GET /agent/courses`，在对话下方渲染课程列表 |
| `show_events` | 调 `GET /agent/events?status=报名中`，渲染活动列表 + 报名表单 |
| （无） | 仅展示 `reply` 文本 |

报名提交：前端调 `POST /agent/events/signup`（后端负责校验、防重、落库）。

---

## 十、实施步骤

### 阶段 0：环境准备（已完成）
- Dify 1.12.1 本地跑通，已有 NL2SQL 工作流与 Key。

### 阶段 1：导入 DSL 并配置（当前）
1. Dify 控制台 → 创建应用 → 导入 DSL → 上传 `dify/客服Agent-Chatflow.yml`。
2. 逐个节点绑定模型（1 个分类器 + 7 个 LLM）。
3. 4 个知识检索节点分别绑定知识库（公司信息/公司业务/留学政策/FAQ）。
4. 应用「API 访问」页创建 API 密钥，填入 `.env` 的 `DIFY_AGENT_API_KEY`。

### 阶段 2：后端切 real 联调
1. `.env` 设 `DIFY_CLIENT=real`。
2. 用 curl/Postman 打 `POST /agent/chat`，验证 7 场景返回 `intent`/`reply`/`action` 正确。
3. 核对 `data.outputs` 的 `intent` 为英文 slug、`reply` 非空。

### 阶段 3：知识库构建与调优
1. 上传 4 个知识库文档，自动分段 + 向量化。
2. 验证 RAG：问知识库内/外问题，检查「无幻觉」表现。
3. 调 Top-K、召回阈值、分类指令，提升意图准确率至 ≥90%。

### 阶段 4：前端接入
1. 客服窗口接 `POST /agent/chat`，展示 `reply`。
2. 按 `action.type` 渲染课程/活动列表，接通报名表单。
3. （可选）对话切 SSE 流式。

### 阶段 5：优化项（后置）
- 多轮上下文：`chat_session` 表落 Dify `conversation_id`，实现多轮记忆。
- 意图再细分：课程推荐下拆「语言培训/背景提升/留学申请」子类。

---

## 十一、测试与验收

| 验收项 | 验证方式 | 标准 |
|:---|:---|:---|
| DSL 可导入 | Dify 控制台导入无报错、20 节点完整渲染 | 不崩溃 |
| 意图识别准确率 | 7 类各 10+ 条典型问法 | ≥ 90% |
| RAG 无幻觉 | 问知识库外问题 | 坦诚「暂无确切信息」，不编造 |
| 输出契约 | 抓 `data.outputs` | `intent` 为英文 slug，`reply` 非空 |
| 课程推荐 | 「本科 + 意向英国」 | 引导话术 + `action.type=show_courses` |
| 活动引导 | 「最近有什么讲座」 | 引导话术 + `action.type=show_events` |
| 报名闭环 | 前端按 action 调 signup | 后端落库、防重、返回 signup_id |
| mock/real 切换 | 改 `DIFY_CLIENT` 重启 | 后端接口签名不变，数据流一致 |

---

## 十二、风险与应对

| 风险 | 影响 | 应对 |
|:---|:---|:---|
| Dify 版本差异导致 DSL 格式不兼容 | 导入失败/崩溃 | DSL 已按 1.12.1 实体校验；版本不同则按目标版本重生成 |
| 本地 Dify 未配 openai 模型 | 节点「模型未找到」 | 导入后手工换模型；不影响导入 |
| 知识库内容不足 | RAG 回答空泛/幻觉 | 完善文档 + 调召回阈值 + 提示词强约束 |
| 意图识别误判 | 错误分支/错误 action | 分类指令细化 + 校准样例 + 必要时拆子类 |
| 多轮上下文缺失 | 追问答非所问 | 阶段 5 落 Dify conversation_id，先单轮跑通 |

---

## 十三、待确认项

1. ~~模型选择~~ 已确认：省成本方案（见 6.7）。
2. ~~Dify 应用与 Key~~ 已确认：单独新建工作流应用并申请新 Key（见 8.3）。
3. ~~变量赋值节点崩溃~~ 已解决：改用 Workflow 多结束节点，去除赋值节点。
4. **课程推荐是否按条件筛选**：当前由前端直接拉全量课程展示；若课程量大，可让前端按条件筛选（与 Dify 无关）。
5. **报名方式**：当前「活动引导」只引导用户留资，由前端调 `signup` 接口；是否要在 Dify 里用 HTTP 节点直接调 `signup`（不推荐，写库应在后端留痕），需与业务方确认。

---

## 十四、交付物清单

| 交付物 | 位置 |
|:---|:---|
| Dify 工作流 DSL | `dify/客服Agent-Chatflow.yml` |
| 导入说明 | `dify/README.md` |
| 后端客户端 | `app/services/dify_client.py` |
| 配置项 | `app/config.py` / `.env` |
| 本方案 | `业务文档/03开发设计/客服Agent-Dify-Chatflow搭建方案.md` |
