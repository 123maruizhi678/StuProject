# 企业智能助手：智能体代码

代码独立放在用户指定目录，未挂载 `app/main.py`，未修改现有认证、学生服务或数据库。这里实现的是此前企业接口方案中的六项 AI 能力；业务接口仍由后端提供。

目标 Dify `http://192.168.5.12/apps` 已通过 Playwright MCP 连接并确认登录。[单应用 DSL 与六任务试运行输入](dify/配置进度与导入说明.md)已填入目标实例现有默认模型 `gpt-4o-mini`，本地结构校验和 37 项离线测试通过；上传被自动审批拦截，等待用户明确授权该文件上传到目标实例。尚未创建、发布或真实试运行。

## 已实现的能力

| 方案接口 | Python 方法 | 返回内容 |
|---|---|---|
| POST `/api/v1/enterprise/chat` | `EnterpriseAgents.chat` | 查询/办理/知识/普通交流/澄清的路由结果 |
| POST `/api/v1/enterprise/command` | `EnterpriseAgents.command` | 已开放动作的参数草案、唯一目标引用或缺失项 |
| POST `/api/v1/enterprise/daily-report/prepare` | `EnterpriseAgents.prepare_daily` | 日报文本、摘要、工作项、产出、风险与计划的预览 |
| POST `/api/v1/enterprise/daily-report/summary` | `EnterpriseAgents.summarize_daily` | 团队摘要，每条关联来源日报 ID，附实际版本 |
| POST `/api/v1/enterprise/knowledge/ask` | `EnterpriseAgents.ask_knowledge` | 基于授权检索片段的答案、条目 ID、当前内容版本及来源 |
| POST `/api/v1/enterprise/nl2sql` | `EnterpriseAgents.nl2sql` | 带命名参数的 SELECT 候选或澄清问题，不含执行结果 |

上表是与拟定业务接口的对应关系，不表示这些 HTTP 路由已经注册。六个方法均为 async，返回 `AgentResult`，含 `data` 和 `workflow_run_id`；可用 `.model_dump(mode="json")` 转成统一响应信封的 data。

## 目录

```text
智能体/企业管理/
  enterprise_agents/
    contracts.py          输入和结构化输出模型
    runtime.py            Dify Workflow HTTP 调用及错误处理
    service.py            六项 AI 能力的调用、输出约束和引用适配
    prompts/              公共规则和六份任务提示词
    __main__.py           独立命令行入口
  schemas/                六份已导出的 JSON Schema
  examples/offline_demo.py 六项能力的离线契约示例
  tests/test_agents.py    离线测试，不调用真实模型或数据库
  export_schemas.py       重新生成 Schema
  export_dify_workflow.py 导出一个应用承载六任务的 DSL 草稿
  dify/                  已填模型的 DSL、试运行输入与配置进度
  .env.example            环境变量名称示例，不含密钥
  requirements.txt
```

## 本地运行

在本目录打开 PowerShell：

```powershell
Set-Location 'D:\pj\StuProject\业务文档\06开发文档\智能体\企业管理'

# 当前解释器已有 httpx 和 pydantic 时无需再次安装
python -m pip install -r requirements.txt

# 六项功能的固定离线示例：不发请求，不表示真实模型推理
python examples/offline_demo.py

# 离线测试：包含 Dify MockTransport、参数与来源检查
python -m unittest discover -s tests -v

# 输入/输出模型改动后重新导出
python export_schemas.py
```

代码适配 Python 3.11+、Pydantic 2.10+、httpx 0.28+。不依赖 `app.config`、SQLAlchemy、MySQL 或项目其他模块；未为该目录自动安装依赖。

## Dify 配置与发布

采用已有项目的 Dify Workflow 调用方式：`POST /workflows/run`，`response_mode=blocking`，读取 `data.outputs.result`。[Dify 官方实现](https://github.com/langgenius/dify/blob/main/api/controllers/service_api/app/workflow.py)要求先发布 Workflow。

可以使用一个通用 Workflow 服务六个任务，也可为任务分别发布工作流。默认配置为单 Workflow：

1. 创建 **Workflow**。输入节点声明四个字符串变量：`task`、`system_prompt`、`payload_json`、`schema_json`。较长内容选择段落输入，长度需足以容纳实际提示词、Schema 和本轮资料。
2. 添加 LLM 节点，选择本地 Dify 已配置的真实模型提供商。System 提示使用输入变量 `system_prompt`，并追加“只输出符合下面 JSON Schema 的对象”及变量 `schema_json`；User 使用变量 `payload_json`。用 Dify 的变量选择器选取实际节点变量，不直接粘贴虚构节点 ID。
3. 不配置数据库、HTTP 业务写入、Python 执行等工具节点。六项任务分别由本包传入相应 Prompt 和输出 Schema。支持结构化输出时，也可分六条分支，在各分支采用 `schemas/` 对应 Schema。
4. 输出节点定义 `result`，映射为 LLM 的 JSON 对象或完整 JSON 文本；不能再包装为 `{answer: ...}`，不能只输出其中一个字符串字段。
5. 测试并发布，从该 Workflow 的“访问 API”页面获取 Key。

设置进程环境变量：

```powershell
$env:ENTERPRISE_AGENT_DIFY_BASE = 'http://127.0.0.1/v1'
$env:ENTERPRISE_AGENT_DIFY_KEY = '<已发布Workflow的Key>'
$env:ENTERPRISE_AGENT_TIMEOUT = '60'
```

`.env.example` 仅列出名称；本包不会自动加载项目 `.env`，也不会复用现有 `DIFY_API_KEY`，防止误调用原来只有一个 SQL 输出的工作流。可由宿主进程显式加载配置或直接构造 `DifyConfig`。

为不同任务单独发布时可设置 `ENTERPRISE_AGENT_CHAT_KEY`、`COMMAND_KEY`、`DAILY_PREPARE_KEY`、`DAILY_SUMMARY_KEY`、`KNOWLEDGE_KEY`、`NL2SQL_KEY`，以上后五项均需同样添加 `ENTERPRISE_AGENT_` 前缀；完整名称见 `.env.example`。对应任务 Key 优先，否则使用通用 Key。未配置 Key 会明确报 `AGENT_NOT_CONFIGURED`，不生成模拟结果冒充真实推理。

这里只提供可执行的 Python 能力代码与 Dify 配置材料，本地 DSL 已选用目标实例现有默认模型，但尚未在用户实例创建/发布应用，也未创建或配置应用 Key。离线示例只用于理解返回结构。各接口的 AI 与固定代码分工见[企业管理接口分工与 Dify 配置交付](企业管理接口分工与Dify配置交付.md)，完整覆盖接口方案中的 79 项设计接口。

## 后端调用与可信输入

以下示例由业务后端调用，不应把整个请求对象直接开放给前端：

```python
from datetime import datetime, timezone
from enterprise_agents import EnterpriseAgents
from enterprise_agents.contracts import ActorContext, DailyPrepareRequest

agents = EnterpriseAgents()  # 从进程环境读取 Dify 配置

# subject、role_codes 必须来自已验证的登录上下文。
context = ActorContext(
    subject="employee:910002",
    role_codes=["employee", "consultant"],
    now=datetime.now(timezone.utc),
)

async def prepare_preview(text, report_date):
    result = await agents.prepare_daily(
        DailyPrepareRequest(text=text, report_date=report_date), context
    )
    return result.model_dump(mode="json")
```

可信输入的含义：

| 能力 | 调用前后端必须准备的内容 |
|---|---|
| chat | 当前账号可用的 `allowed_routes`；历史消息由后端读取并绑定账号，不能直接使用任意外部会话 ID |
| command | 当前角色、本次范围可调用的 `ActionSpec`；后端查出的候选 `Candidate`；动作参数目录由开发者定义 |
| daily_prepare | 本人原始文本和确认过的日报日期；员工 ID、所属部门不交给模型决定 |
| daily_summary | 后端按权限、部门和日期读取的 `submitted` 正式日报；每份附 ID、实际版本 |
| knowledge | 后端授权检索得到的片段；传入前检查发布状态、有效期和当前版本，返回前必要时再次检查 |
| nl2sql | 后端批准的业务视图及最少字段 Schema；不得传整个数据库或完整敏感字段 |

角色支持原方案的六个代码，但 **本包不实现角色鉴权或数据范围判断**。这些代码不会被模型解释成数据库授权。资料与目录必须由现有后端的固定权限代码过滤，不信任前端在请求正文自报的角色、动作目录或知识片段。

### 指令解析的动作目录

`ActionSpec` 使用后端注册的动作名称、说明、可提取字段和目标类型。`ParameterRule` 支持文本、整数、数值、布尔、日期和带时区时间，以及必填、枚举、长度和数值边界。例如：

```python
from enterprise_agents.contracts import (
    ActionSpec, Candidate, CommandRequest, ParameterRule,
)

request = CommandRequest(
    command="同意测试张同学的请假，意见是按时返校",
    actions=[ActionSpec(
        name="approve_leave",
        description="批准当前老师负责的待审批请假",
        entity_type="leave",
        requires_target=True,
        fields={"comment": ParameterRule(description="审批意见", max_length=2000)},
    )],
    candidates=[Candidate(
        ref="leave-910001-v3", entity_type="leave", entity_id="910001",
        display_name="测试张同学 EIT-S001，本次请假", version=3,
    )],
)

# result = await agents.command(request, context)
```

返回 `proposed` 仅表示字段提取完整，**不是审批成功或可直接执行的授权**。后端仍须重新检查真实老师、待审批状态和版本，生成短期签名确认凭证，再交给固定审批服务。

- 候选须为本次动作查出的目标集合；同类候选超过一条时，即使模型选了一个，也返回 `needs_clarification`。员工明确选择后，由后端重新查询并缩小到唯一候选再解析。
- 目标 ID、版本来自后端候选，不从模型自由返回的字段获取。
- 参数不在目录中、类型/范围不符或目标引用越界时，报输出错误；必填缺失则返回缺失项。
- 创建类动作设置 `requires_target=False`，不接受凭空构造的已有对象引用。
- 参数目录为平面字段结构；嵌套业务对象应由后端提供适配，不能让模型提交任意 ORM 字典。动作名称与真实 API 的对应由后端注册，不由模型产生 URL。

### 日报汇总与知识问答

摘要按条目引用真实日报 ID；来源版本和报告数量从调用方输入产生，不由模型填写。空日报返回空汇总，不调用模型。

知识问答是 **检索后、有来源的生成部分**。本包不直接读取关系库，也不在全局 Dify 知识库无条件检索。已有授权检索器应将 FAQ 或文档片段传给 `KnowledgeRequest.chunks`，本包返回实际来源 ID、标题和版本。空召回不调用模型；虚构来源会被拒绝；同一知识条目混用多个版本会被拒绝。

这些约束能检查来源是否存在于输入，不能自动证明每个自然语言结论都被来源支持。真实模型仍需按业务样本评测忠实度、否定词保留、提取准确率和来源匹配。

### NL2SQL 的返回边界

只生成候选或澄清问题。`requires_backend_validation=True` 是固定返回标记。

本包对 SQL 仅检查声明视图来自目录、文本以 SELECT 开头；**这不是 SQL 安全校验**，并未解析 SQL 实际引用、JOIN、UNION、子查询、多语句或函数。后端必须另做语法树分析、实际表/字段白名单、真实身份行范围、参数绑定、只读数据库账号、扫描范围和超时限制；不通过就不能执行。

不要把这里的结果直接送入现有 `app/services/nl2sql_service.py` 执行；该旧入口的 SELECT 前缀判断也不能替代上述校验。此目录没有任何数据库连接、SQL 执行或通用工具运行代码。

## 命令行真实调用

保存 `request.json` 为任务请求，`trusted-context.json` 为后端构造的上下文。例如日报请求：

```json
{"report_date":"2026-10-15","text":"今天跟进三个客户，还没有签约，明天核对申请材料。"}
```

上下文示例（真实调用时应由登录服务构造并更新 now）：

```json
{"subject":"employee:910002","role_codes":["employee","consultant"],"now":"2026-10-15T10:00:00+08:00"}
```

```powershell
python -m enterprise_agents daily_prepare --input request.json --context trusted-context.json
```

任务名：`chat/command/daily_prepare/daily_summary/knowledge/nl2sql`。命令行只是本地开发调用工具，不是允许前端自报可信身份的生产入口。

## 错误、上下文与测试范围

错误统一为 `AgentError`，含 `code` 和脱敏消息，由后端映射到项目 `{code,message,data}` 信封：

- `AGENT_NOT_CONFIGURED`：缺 Key。
- `AGENT_TIMEOUT/AGENT_UNAVAILABLE/AGENT_WORKFLOW_FAILED`：外部依赖失败。
- `AGENT_CONTEXT_TOO_LARGE/AGENT_OUTPUT_TOO_LARGE`：输入/响应超过限制。
- `AGENT_OUTPUT_INVALID`：输出不符合结构、动作目录或引用约束。

默认超时 60 秒，最多输入约 256 KiB、响应 2 MiB，不自动重试，不跟随重定向，不在异常消息中附原始输入、SQL、Key 或依赖响应。超过上下文限制时明确失败，不静默丢弃日报或知识来源；由后端缩小时间窗或显式分批。

离线测试覆盖六项能力、重名澄清、目录外动作/参数、目标版本、来源伪造、无资料降级、Dify 请求契约、失败状态、超时和响应长度等。真实 Dify 模型、发布工作流、真实知识召回与生产接口均尚未联调；测试结果不能当作模型达到业务准确率目标的证明。

## 与其他功能的分工

- `/command/confirm`、登录鉴权、审批、改分、客户 CRUD、事务、幂等、签名、通知投递和同步：仍由固定业务代码负责，本目录没有重复实现。
- `/audio/transcriptions`：属于 ASR 服务及音频上传处理，不是本次六项文本智能体能力，后端先转写再调用日报/指令方法。
- 学生端已有 `student_clients.py`、`student_chat.py` 及 `dify/student/` 的心理评估、投诉摘要和学生对话代码，本次不复制或替换它们。企业只使用这里的六项 AI 能力；老师人工处理预警仍调用学生协作接口。
