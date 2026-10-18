# 客服 Agent 后端接入与验证

## 文件结构

依据操作文档第七章的客服文件职责，沿用项目“技术层 → 业务模块”的目录约定，客服代码归入各层的 `agent` 包：

```text
app/
├── api/agent/
│   ├── __init__.py          导出 router，供唯一应用入口挂载
│   └── agent.py             六个匿名 HTTP 接口
├── services/agent/
│   ├── __init__.py
│   ├── agent_service.py     对话、活动、报名、课程及 FAQ 业务
│   └── dify_client.py       客服专属 mock / real Workflow 适配器
├── models/agent/
│   ├── __init__.py          导出六张业务表模型
│   └── agent.py             六张业务表 ORM 映射
└── schemas/agent/
    ├── __init__.py          导出请求与响应模型
    └── agent.py             客服请求/响应字段与校验
```

业务服务从 `app.services.agent` 导入 `agent_service`，Dify 客户端从 `app.services.agent.dify_client` 导入。接口、模型和 Schema 包保留 `app.api.agent`、`app.models.agent`、`app.schemas.agent` 的公开导入入口。公共配置、数据库、日志、响应和 Dify HTTP 工具继续使用原公共模块。

前端已独立放在 `frontend/agent/`、`frontend/js/agent/`、`frontend/css/agent/`，测试位于 `tests/agent/`，SQL 历史资产位于 `scripts/sql/bk/客服Agent/`。操作文档另列的客服 DSL、知识库、种子和联调脚本仍按原交付状态管理，本次目录调整不生成这些业务资产。

## HTTP 接口

客服后端六接口已在唯一 `app/main.py` 挂载，保持允许匿名访问：

| 方法 | 路径 | 功能 |
| --- | --- | --- |
| POST | `/api/v1/agent/chat` | 调用客服 Workflow 并保存会话和消息 |
| GET | `/api/v1/agent/events` | 活动列表 |
| GET | `/api/v1/agent/events/{event_id}` | 活动详情 |
| POST | `/api/v1/agent/events/signup` | 活动报名 |
| GET | `/api/v1/agent/courses` | 课程列表 |
| GET | `/api/v1/agent/faq` | FAQ 查询 |

## Dify 契约

- 复用 `app/core/common/dify.py`，不创建第二套公共 HTTP 工具。
- 从唯一配置入口读取 `DIFY_API_BASE`、`DIFY_API_TIMEOUT_SECONDS`。
- `DIFY_CLIENT=real` 使用独立 `DIFY_AGENT_API_KEY`；只有明确设为 `mock` 才模拟，真实模式失败不会自动降级或重发。
- 调用 `POST /workflows/run`，传入 `inputs.query`、`response_mode=blocking`、`user=visitor-<session_id>`。API 基址包含 `/v1`，不使用管理页面 `/apps`。
- 已实际核验发布应用为 Workflow、query 必填；输出只有执行状态为 succeeded 且 intent/reply 合法时接受。
- intent 使用现有七种受控意图；event_query 生成 show_events，course_recommend 生成 show_courses，其余无动作。模型不能决定任意前端动作或发起业务写入。
- 回复中的完整 think 段在返回前移除；空回复、未闭合思考内容、缺字段或未知意图作为输出错误处理。
- 上游鉴权、HTTP、连接或超时错误返回业务码503；失败状态及非法输出返回502。具体错误信息不回显上游响应或凭据。

成功及业务失败均复用公共 code/message/data。参数校验仍沿用原有 HTTP422；没有为此次挂载改变匿名客服的全局错误协议。

## 事务

取得合法模型回复后，显式先 flush 新会话，再保存用户和助手消息并提交。Dify 或后续数据库写入失败时回滚本次事务，已有会话历史不删除。此顺序与现有 SQL 的 chat_message→chat_session 外键一致，不修改真实表结构。

## 可复现的离线回归

```powershell
python -B -m unittest discover -s tests/agent -p "test_*.py"
python -B -m unittest discover -s tests/common -p "test_*.py"
```

客服18项、公共39项回归通过。客服测试使用 SQLite 内存库，保留现有 SQL 的两个业务外键，仅在测试 DDL 副本中将自增主键调整为 SQLite 所需的 INTEGER；不修改生产 ORM 类型或数据库。

真实联调已通过实际 FastAPI 主入口调用真实客服 Workflow，同时将数据库依赖替换为虚构内存库：对话、活动列表/详情、报名、课程及 FAQ 六接口均成功，新会话和一对消息正确保存。真实业务数据库没有读写测试数据，真实 Dify 只接收明确标注虚构的咨询消息。

本次只接入客服后端和 Dify，未交付客服前端页面；未重新发布或编辑 Dify 工作流。
