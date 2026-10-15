# 客服 Agent — 6 张业务表说明文档

> 模块：客服 Agent（7 大业务场景）
> 来源：`业务文档/03开发设计/客服Agent实现方案.md` 第四章
> 数据库：`stu_project`（utf8mb4，东八区，InnoDB）
> 文件夹：`scripts/sql/agent_tables/`

---

## 一、文件清单

| 文件 | 表名 | 类别 | 是否依赖其他文件 |
|:---|:---|:---|:---:|
| `00_init.sql` | （无） | 初始化 + 种子数据 | — |
| `01_course_project.sql` | `course_project` | 课程库 | 否 |
| `02_lecture_event.sql` | `lecture_event` | 活动库 | 否 |
| `03_event_signup.sql` | `event_signup` | 报名记录 | 依赖 02 |
| `04_faq.sql` | `faq` | FAQ 兜底 | 否 |
| `05_chat_session.sql` | `chat_session` | 会话元信息 | 否 |
| `06_chat_message.sql` | `chat_message` | 对话消息流 | 依赖 05 |

---

## 二、执行顺序

```bash
# 1. 建库 + 种子数据（最先执行）
mysql -u root -p stu_project < 00_init.sql

# 2. 建无依赖的 4 张表（顺序无关）
mysql -u root -p stu_project < 01_course_project.sql
mysql -u root -p stu_project < 02_lecture_event.sql
mysql -u root -p stu_project < 04_faq.sql
mysql -u root -p stu_project < 05_chat_session.sql

# 3. 建有外键依赖的 2 张表
mysql -u root -p stu_project < 03_event_signup.sql
mysql -u root -p stu_project < 06_chat_message.sql
```

> 一键全量执行（Linux/macOS）：`cat 0*.sql 1*.sql | mysql -u root -p stu_project`
> 一键全量执行（Windows cmd）：`type 0*.sql 1*.sql | mysql -u root -p stu_project`

---

## 三、每张表的用处

### 1. `course_project` — 课程项目表

**做什么**：存所有"留学申请 / 背景提升 / 语言培训"课程的信息。
**谁会用到**：
- Agent "课程与项目推荐"场景 → 根据客户学历 + 意向国家查推荐课程
- 后台课程管理 → 上架 / 下架 / 编辑课程

**关键字段速记**：
- `category`：决定走哪个推荐分支
- `status='上架'`：列表接口只返回上架课程
- `target_audience`：用于"学历+意向"条件筛选

---

### 2. `lecture_event` — 讲座活动表

**做什么**：存近期线上/线下留学讲座、招生官见面会。
**谁会用到**：
- Agent "活动与讲座报名"场景 → 客户问"最近有什么活动"时返回此表
- 后台活动管理 → 创建 / 修改 / 上下线活动

**关键字段速记**：
- `status`：报名中 / 已满 / 已结束（应用层枚举）
- `quota = 0`：业务约定表示不限名额（待确认）
- `signed_count`：由报名事务自动累加

---

### 3. `event_signup` — 活动报名表

**做什么**：记录每个客户对每个活动的报名流水。
**谁会用到**：
- Agent "活动与讲座报名"场景 → 报名接口写库 + 回查
- 后台 CRM → 私域流量沉淀、报名审核

**关键字段速记**：
- `event_id` + `customer_phone` 组成**唯一约束** → 防重复报名（DB 层兜底）
- `customer_phone` / `customer_name` 是敏感字段 → 对外接口必须脱敏
- `customer_info` 是 JSON → 存扩展信息（意向国家、学历等，待确认）
- `source='客服对话'`：标识来源，便于渠道归因

---

### 4. `faq` — FAQ 问答对表

**做什么**：存高频重复问答的标准答案（申请流程、费用、退费等）。
**谁会用到**：
- Agent "常见问题自助解答"场景的**后端兜底**
- 主流程走 Dify 知识库的问答对匹配；Dify 不可用时降级到本表

**关键字段速记**：
- `category`：按主题分类（费用 / 退费 / 流程 / 课程 / 活动）
- 此表**不是**主路径，主路径在 Dify 知识库

---

### 5. `chat_session` — 客服会话表

**做什么**：记录每个访客进入客服时产生的一次会话元信息。
**谁会用到**：
- Agent 对话入口 → 每次 `POST /agent/chat` 首次创建会话
- 后台对话管理 → 按用户 / 时间查历史会话

**关键字段速记**：
- `session_id`：UUID，作为前端调用 / 消息外键的统一标识
- `user_id`：未留资时为空字符串 `''`，留资后填充
- `updated_at`：用 `idx_updated_at` 索引做"最近活跃会话"排序

---

### 6. `chat_message` — 客服消息表

**做什么**：存每一次对话的 user 消息和 assistant 回复。
**谁会用到**：
- Agent 对话入口 → 每次往返各写一条消息
- 后台对话回放 / 审计 → 按 `session_id` + 时间排序回放
- 运营分析 → 按 `intent` 统计各场景占比

**关键字段速记**：
- `role='user' | 'assistant'`：区分消息方向
- `intent`：Dify 返回的 7 类意图（业务查询 / 政策 / 闲聊 …）
- `content`：消息原文（TEXT，可存富文本）

---

## 四、表之间的关系

```
chat_session (1) ──< chat_message (N)   会话-消息 一对多
lecture_event (1) ──< event_signup (N)  活动-报名 一对多
course_project       独立（课程库）
faq                  独立（FAQ 兜底）
```

```
                    ┌──────────────────┐
                    │  lecture_event   │ ◀── 活动主表
                    └────────┬─────────┘
                             │ 1:N (FK: event_id)
                             ▼
                    ┌──────────────────┐
                    │  event_signup    │ ◀── 报名流水
                    └──────────────────┘

                    ┌──────────────────┐
                    │  chat_session    │ ◀── 会话主表
                    └────────┬─────────┘
                             │ 1:N (FK: session_id)
                             ▼
                    ┌──────────────────┐
                    │  chat_message    │ ◀── 消息流水
                    └──────────────────┘
```

---

## 五、整体在客服 Agent 工作流中的位置

```
访 户 问 "你们最近有什么留学讲座？"
              │
              ▼
   FastAPI: POST /agent/chat
              │ ① 写 chat_session（首次）
              │ ② 写 chat_message（user）
              │ ③ 调 Dify（意图 = event_query）
              │ ④ 查 lecture_event（status=报名中）
              │ ⑤ 写 chat_message（assistant）
              ▼
   返回：{ intent, reply, action: show_events }

客 户 选 中 一 个 活 动 并 留 手 机 号
              │
              ▼
   FastAPI: POST /agent/events/signup
              │ 事务内：
              │ ① 校验 lecture_event 状态
              │ ② INSERT event_signup（唯一约束兜底防重）
              │ ③ UPDATE lecture_event.signed_count + 1
              ▼
   返回：{ signup_id, signup_time }
```

---

## 六、回滚

如需删除全部表（按 FK 反序）：

```bash
mysql -u root -p stu_project -e "
DROP TABLE IF EXISTS chat_message;
DROP TABLE IF EXISTS chat_session;
DROP TABLE IF EXISTS event_signup;
DROP TABLE IF EXISTS lecture_event;
DROP TABLE IF EXISTS course_project;
DROP TABLE IF EXISTS faq;
"
```

---

## 七、相关文档

- 设计依据：`业务文档/03开发设计/客服Agent实现方案.md` 第四章
- 字段详细说明：`业务文档/05数据库设计/客服Agent_表结构文档.md`
- 一体化建表脚本（含种子）：`scripts/sql/01_agent_tables.sql`
