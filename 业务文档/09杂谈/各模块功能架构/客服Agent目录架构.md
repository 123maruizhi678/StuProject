# 客服 Agent 目录架构

> **范围**：仅客服 Agent 模块。公共入口（`main.py`、`config.py`、`database.py`、`access_control.yaml`、`core/common`）及其他业务模块（customer / report / enterprise / student）的目录不在此列。
> **依据**：`开发文档/项目目录架构_最终汇总.md` 中 agent 相关节点；接口与功能设计依据 `开发文档/操作文档.md` 第一章。
> **状态口径**：[已落地] 表示文件已在仓库；[缺] 表示架构规划但仓库暂无（原因见文末说明）。整理日期：2026-10-17。

## 一、目录树（客服 Agent）

```text
StuProject/
├── app/
│   ├── api/agent/                        # HTTP 接入层：客服六接口
│   │   ├── __init__.py                   # [已落地] 导出 router；main.py 导入路径不变
│   │   └── agent.py                      # [已落地] chat / events / events/{id} / events/signup / courses / faq
│   ├── schemas/agent/                    # 请求、响应与业务契约
│   │   ├── __init__.py                   # [已落地] 导出全部模型
│   │   └── agent.py                      # [已落地] Chat / Event / Signup / Course / Faq 模型
│   ├── services/agent/                   # 业务编排：对话、报名、课程、FAQ
│   │   ├── __init__.py                   # [已落地] 导出 agent_service 子模块
│   │   └── agent_service.py              # [已落地] 事务顺序：user 消息先提交→事务外调 Dify→兜底→assistant 落库
│   ├── repositories/agent/               # 参数化数据访问（本层不 commit）
│   │   ├── __init__.py                   # [已落地] 导出数据访问函数
│   │   └── agent_repository.py           # [已落地] 六表查询；报名 lock_event 行锁、状态式防重
│   ├── models/agent/                     # ORM / Table 唯一映射
│   │   ├── __init__.py                   # [已落地] 导出六个模型
│   │   └── agent.py                      # [已落地] 客服六表：course_project / lecture_event / event_signup /
│   │                                    #           faq / chat_session / chat_message
│   └── clients/agent/                    # 场景客户端：mock / real 及 Workflow 适配
│       ├── __init__.py                   # [已落地] 导出客户端与 get_dify_client
│       └── dify_client.py                # [已落地] MockDifyClient / RealDifyClient；思维链剥除；intent→action
├── dify/agent/                           # 客服 Dify 资产（应用目标为 Workflow）
│   ├── README.md                         # [已落地] 导入步骤、模型/知识库绑定、字段对齐、版本兼容
│   ├── 客服Agent-Chatflow.yml            # [已落地] DSL（历史文件名；实际为 Workflow，version 0.5.0）
│   └── knowledge/                        # 4 类知识库源资料与 dataset_id 映射
│       ├── README.md                     # [已落地] 各库作用、维护流程、索引技术说明
│       ├── dataset_ids.json              # [已落地] 4 个知识库 dataset_id / document_id 映射
│       ├── FAQ.md                        # [已落地] FAQ 知识库源资料（36 条问答）
│       ├── 公司信息.md                   # [缺] 架构规划文件，仓库暂无（源文档未随本次提交）
│       ├── 公司业务.md                   # [缺] 同上
│       └── 留学政策.md                   # [缺] 同上
├── frontend/                             # 客服页面与资源
│   ├── agent/agent.html                  # [已落地] 客服单页：对话、活动报名弹窗、课程/FAQ 面板
│   ├── css/agent/agent.css               # [已落地] 客服页面样式
│   └── js/agent/agent.js                 # [已落地] 六接口调用、session 维持、意图动作联动
├── scripts/agent/                        # 客服联调与回归脚本
│   ├── build_dify_kb.py                  # [已落地] 一键重建 4 个知识库（创建→上传→轮询索引→输出映射）
│   ├── reupload_dify_kb.py               # [已落地] 按空行分段重新上传知识库文档
│   ├── test_dify_kb.py                   # [已落地] 知识库检索命中验证
│   ├── test_workflow_run.py              # [已落地] 直接调 Dify /workflows/run 验证 7 场景输出
│   └── smoke_agent_api.py                # [已落地] 六接口冒烟：库盘点 + 接口回归 + 落库对账
├── scripts/sql/agent/                    # 客服 SQL：独立建表、种子与测试数据
│   ├── README.md                         # [已落地] 种子/测试数据说明与判重口径
│   ├── agent_schema.sql                  # [已落地] 客服六表独立 DDL（含 fk_signup_event / fk_message_session）
│   ├── agent_seed.sql                    # [已落地] 正式种子：7 课程 / 4 活动 / 8 FAQ
│   └── agent_test_data.sql               # [已落地] 测试数据（课程3/活动2/FAQ3/会话2/报名2/消息4）+ 查看对账语句
└── tests/agent/                          # 客服单元测试（不依赖数据库）
    ├── __init__.py                       # [已落地] 测试包初始化
    ├── test_agent_chat.py                # [已落地] 对话：正常/兜底/空消息/会话复用（mock）
    └── test_agent_signup.py              # [已落地] 报名：校验/锁/防重/部分失败边界（mock）
```

## 二、分层职责（对齐操作文档）

| 层 | 职责 | 边界 |
|:---|:---|:---|
| `api/agent` | 六接口路由、参数校验、统一信封 | 不写业务逻辑；六接口匿名开放，无 JWT / 幂等键门槛 |
| `schemas/agent` | 请求/响应契约 | 模型只生成话术与动作，列表与名额以数据库为准 |
| `services/agent` | 业务编排与事务控制 | 用户消息先提交；模型调用在事务外；失败兜底不丢留资 |
| `repositories/agent` | 六表数据访问 | 参数化查询；不 commit；报名锁顺序固定为活动父行 |
| `models/agent` | 六表唯一 ORM 映射 | 不重复声明 Base；建表由 scripts/sql 负责 |
| `clients/agent` | Dify 场景适配 | mock/real 可切换；剥除思维链；intent→action 由后端推导 |

## 三、与 Dify 的契约

| 项 | 约定 |
|:---|:---|
| 应用 | `dify/agent/客服Agent-Chatflow.yml`，实际为 Workflow（DSL version 0.5.0） |
| 入口 | 仅 `POST /api/v1/agent/chat` 调模型；其余五接口不调模型 |
| 传输 | 公共 `app/core/dify.py` 的 `DifyHttpClient`，POST `/workflows/run`，blocking |
| 输入 | `inputs.query` = 访客消息；`user` = `visitor-{session_id}` |
| 输出 | `data.outputs.intent` / `data.outputs.reply`；HTTP 200 ≠ 业务成功 |
| 动作 | `course_recommend→show_courses`、`event_query→show_events`，其余无 |
| 配置 | `DIFY_CLIENT`（mock/real）、`DIFY_AGENT_API_KEY`、`DIFY_API_BASE`、`DIFY_API_TIMEOUT_SECONDS` |

## 四、数据与 SQL

| 文件 | 用途 |
|:---|:---|
| `agent_schema.sql` | 客服六表独立建表（测试/独立库用），含两条客服外键 |
| `agent_seed.sql` | 正式种子数据（7 课程 / 4 活动 / 8 FAQ） |
| `agent_test_data.sql` | 面向空表的小量测试数据 + 查看对账语句 |
| `scripts/sql/bk/客服Agent/` | 历史建表脚本，仅参考，不作日常迁移入口 |

判重口径：`event_signup` 采用**状态式判重**（`status='有效'`），不建 `(event_id, customer_phone)` 永久唯一索引；历史 `all.sql` 的 `uk_event_phone` 与目标规范不一致，启用取消/重报前须受控处理索引差异。

## 五、验证状态（2026-10-17）

- 单元测试：`tests/agent/` 11 用例全部通过（mock，不依赖数据库）
- 接口冒烟：`scripts/agent/smoke_agent_api.py` 六接口 + 落库对账通过
- 真实链路：Dify 启动后 chat 端到端验证通过（intent 正确分类、话术正常、思维链剥除、消息落库）
- 容灾：Dify 不可用时 chat 自动走兜底话术且用户消息不丢（已验证）
- 遗留：`dify/agent/knowledge/` 三份源文档（公司信息/公司业务/留学政策）未随本次提交，知识库重建前需补
