# 企业管理接口分工与 Dify 单应用配置交付

日期：2026-10-15。依据本项目企业需求、接口方案和 `enterprise_agents/` 实际代码。

## 1. 结论与交付范围

采用一个 Dify Workflow 应用，名称为 **企业智能助手-六任务统一Workflow**，复用一个 LLM 节点承载六项任务。Python 后端按任务传入提示词、授权资料与输出 Schema，同一个应用 Key 即可服务六项能力。这里的“一个智能体”对应一个 Dify 应用；选择 Workflow 是为了匹配现有代码的 `/workflows/run` 调用契约。

按接口方案第 5、6 节的 79 项接口划分：6 项接口包含 LLM 能力，1 项接入独立语音识别服务，72 项由固定后端代码实现。6 项 LLM 接口同样需要固定代码负责权限、取数、输出检查与响应适配，并非整个接口交给模型。

原方案仍标为“待确认、尚未实现”。下列路径是设计清单，不能据此认定线上接口已经存在。此次任务配置 AI 能力，不把完整企业业务后端描述为已交付。

## 2. 需要智能体介入的六项接口

所有本节路径均以前缀 `/api/v1/enterprise` 开始。

| 编号 / 接口 | Dify task / Python 方法 | 模型负责 | 固定代码负责 |
|---|---|---|---|
| AI-01 `POST /chat` | `chat` / `EnterpriseAgents.chat` | 识别查询、办理、知识、普通交流或澄清意图；规范化原始问题 | 绑定账号与历史、限制 `allowed_routes`；路由后调用对应服务，不把意图识别当作查询结果或执行回执 |
| AI-03 `POST /command` | `command` / `EnterpriseAgents.command` | 从注册动作中选动作、抽取参数、引用候选目标、说明缺失项 | 按真实权限给出动作目录与候选；检查类型、枚举、目标唯一性；生成确认预览与短期凭证 |
| DAY-01 `POST /daily-report/prepare` | `daily_prepare` / `EnterpriseAgents.prepare_daily` | 将员工文本整理为日报草案、摘要、进展、风险与计划 | 确定员工、日期和部门；保留原文；只返回预览，员工确认后由正式提交接口落库 |
| DAY-07 `POST /daily-report/summary` | `daily_summary` / `EnterpriseAgents.summarize_daily` | 汇总已提供的正式日报，逐项引用来源 ID | 按部门、日期和状态读取授权日报；检查来源；填充真实版本和数量；正式报告保存仍由报告模块实现 |
| KNO-03 `POST /knowledge/ask` | `knowledge` / `EnterpriseAgents.ask_knowledge` | 根据输入片段回答新人指南、规章和流程问题，返回来源引用 | 检查知识权限、发布状态、有效期与版本；先做 FAQ/向量检索；校验来源，无来源时明确无法确认 |
| AI-02 `POST /nl2sql` | `nl2sql` / `EnterpriseAgents.nl2sql` | 根据允许视图及字段产生参数化 SELECT 候选，或提出澄清 | SQL 语法树和字段白名单校验、真实身份行范围、只读账号、绑定参数、超时和行数限制；执行后返回业务结果 |

现有包不签发确认凭证、不实现业务授权、不连接或执行数据库、不执行审批，不直接做知识检索。这些职责须由调用方完成。`nl2sql` 当前仅检查声明视图与 SELECT 前缀，不是 SQL 安全解析器；不得直接接到旧的 `app/services/nl2sql_service.py` 当作安全查询闭环。

## 3. 固定后端代码实现的功能

表单入口直接调用下列接口；自然语言入口可先使用 `command` 提取字段，再经员工确认调用相同业务服务。无需为每种业务另建一个 Dify 应用。

| 功能组 / 接口编号 | 固定实现范围 | 与智能体的关系 |
|---|---|---|
| 当前员工与通讯录 ORG-01～04 | 身份、组织树、员工列表及工作资料；固定授权查询 | 口语查询可先识别意图；数据以真实通讯录为准 |
| 客户与跟进 CUS-01～10 | 客户创建、列表、详情、资料修改、状态、移交、归档、跟进新增/查询/更正 | 自然语言录入及变更可走 `command`，所有写入由固定服务完成 |
| 正式日报 DAY-02～06 | 提交、查询、详情、修订、作废；归属和版本控制 | 模型仅产出草案或摘要，不决定正式事实 |
| 学生与成绩 STU-01～02、SCO-01～05 | 授权学生查询、成绩录入/查询/更正/作废；课程范围与分数校验 | 自然语言改分只能生成预览，不能自动写成绩 |
| 请假 LEA-01～05 | 列表、详情、审批/驳回、分派、时间线；审批人、状态和版本校验 | `command` 解释“同意请假”；执行仍由审批服务完成 |
| 工单 TIC-01～06 | 列表、详情、分派、回应/备注、解决方案、时间线；可见范围和利益冲突检查 | 可提取跟进内容，不把模型输出当作结案成功 |
| 心理预警 MEN-01～07 | 授权查询、分派、接手、人工跟进、关闭与记录 | 本企业 Workflow 不新增心理评估任务；复用学生模块预警及人工处置服务 |
| 知识读取 KNO-01～02 | 授权列表、详情、正文和内容版本 | 精确 FAQ 可直接返回标准答案；需生成回答时再调用 `knowledge` |
| 待办与通知 TODO-01～02、NOT-01～02 | 固定查询待办、计数、通知列表和本人已读 | 定时扫描、去重、发送、租约及重试也由固定任务实现，不让 LLM 扫库 |
| 确认执行 AI-04 | `POST /command/confirm`：凭证、身份、权限、状态、版本、参数、幂等、事务、真实回执 | 不再次让模型决定是否执行 |
| 审计与回执 LOG-01～02 | 操作历史和执行状态查询；对象重新鉴权 | 不开放审计表给通用 NL2SQL |
| 组织与员工管理 ADM-01～07 | 部门/员工维护、状态、固定角色、责任移交 | 固定规则与权限管理 |
| 学生主档及关系 ADM-08～13 | 主数据、归档、学生员工职责绑定及有效期 | 复用权威同步或明确授权维护，不从模型输出授予关系 |
| 知识维护 ADM-14～19 | 草稿、修改、审核发布、停用、重建索引、受限删除 | 索引可调用 embedding 服务；审核、版本、可见范围与索引生效由固定流程控制 |

### 独立语音能力

AI-05 `POST /audio/transcriptions` 由固定上传接口调用真实 ASR 服务，返回可核对的文字，不属于这六项文本 LLM 任务。公共层已有语音接口时复用，不增建第七个企业智能体。确认后的转写文本再送 `command` 或 `daily_prepare`。

### 一条自然语言办理链

员工输入 → `chat` 路由 → 后端按权限准备动作目录与目标候选 → `command` 草案 → 缺项或重名澄清 → 员工核对 → 后端签发并验证确认凭证 → 固定业务事务执行 → 返回实际操作状态。模型不生成任意 HTTP 地址、数据库写语句或执行成功回执。

## 4. 单应用配置

| 项目 | 配置 |
|---|---|
| 目标 | `http://192.168.5.12`，工作区“群星闪耀”，页面显示版本 1.12.1 |
| 应用 | 新建 Workflow：`企业智能助手-六任务统一Workflow` |
| 模型 | 目标实例现有默认模型 `langgenius/openai/openai` / `gpt-4o-mini`，temperature=0 |
| 图结构 | 六任务统一输入 → 企业助手统一AI处理 → 统一result输出 |
| 输入 | `task`、`system_prompt`、`payload_json`、`schema_json`，四项均必填 |
| task 选项 | `chat`、`command`、`daily_prepare`、`daily_summary`、`knowledge`、`nl2sql` |
| Prompt | 共用规则 + 后端任务提示 + 对应 JSON Schema；用户消息为 `payload_json` |
| 输出 | `result` 映射 LLM 完整文本，内容要求为单个 JSON 对象 |
| 工具 | 此应用不接数据库、业务 HTTP 写入或通用代码执行节点 |
| 知识 | 后端先检索授权资料，片段随 `payload_json` 传入；不连接未知权限的全局知识库 |
| 后端配置 | `ENTERPRISE_AGENT_DIFY_BASE=http://192.168.5.12/v1`；新应用专用 `ENTERPRISE_AGENT_DIFY_KEY` |

四个输入属于可信后端调用契约，不应作为普通员工可随意填写的生产表单。真实业务材料仅在后端过滤后传给模型；本轮试运行材料全部为虚构场景。

不创建六个独立应用，也不修改现有“NL2SQL 工作流”“nb”“学生管理系统智能助手”。新应用专用 API Key 尚未创建或写入项目，凭据接入留待发布后处理。

## 5. 验证与当前状态

- 本地 DSL 三节点、四输入、输出映射与六任务样例检查通过；37 项现有离线测试通过。
- 已确认 Playwright 可登录、读取应用列表和模型设置；已打开导入对话框。
- 上传 DSL 被自动审批拒绝，要求用户明确批准具体文件上传到具体目标。尚未上传、创建、发布或进行真实模型试运行；不能将本地检查视作远端部署成功。
- 待上传文件：[企业智能助手_单应用_待选模型.yml](dify/企业智能助手_单应用_待选模型.yml)。内容为节点、通用提示词、变量和现有模型标识，不含 API Key、数据库密码或真实业务数据。
- 试运行输入：[六任务试运行输入.json](dify/六任务试运行输入.json)。逐项运行后需用 `OUTPUT_MODELS` 对应 Pydantic 模型检查输出，再核对事实与来源；补测重名、缺字段、无来源及写库请求等边界。
- 六个虚构正常样例不能证明 NL2SQL 达到需求中 ≥90% 的业务准确率。需另用标注业务问句集验收。

## 6. 依据与代码入口

- [企业需求文档](../../../02需求文档/企业智能助手.md)
- [企业接口方案](../../接口方案/企业管理/企业管理模块_接口方案.md)：第 5、6 节接口清单，第 8、9 节跨模块和后台分工。
- [能力实现](enterprise_agents/service.py)：六任务编排与候选检查。
- [输入输出契约](enterprise_agents/contracts.py)：各能力结构模型。
- [Dify 调用](enterprise_agents/runtime.py)：四输入、blocking 调用和 `data.outputs.result` 解析。
- [DSL 生成](export_dify_workflow.py)：单应用图与六任务虚构输入生成。
- [详细配置进度](dify/配置进度与导入说明.md)。

## 7. 完整接口分类索引

基础前缀为 `/api/v1/enterprise`。此表逐项覆盖方案第 5、6 节；均为设计接口，部署状态以实际后端为准。

| 编号 | 方法 | 路径 | 实现类别 |
|---|---|---|---|
| ORG-01 | GET | `/me` | 固定后端代码 |
| ORG-02 | GET | `/departments` | 固定后端代码 |
| ORG-03 | GET | `/employees` | 固定后端代码 |
| ORG-04 | GET | `/employees/{employee_id}` | 固定后端代码 |
| CUS-01 | POST | `/customer` | 固定后端代码 |
| CUS-02 | GET | `/customer` | 固定后端代码 |
| CUS-03 | GET | `/customer/{customer_id}` | 固定后端代码 |
| CUS-04 | PATCH | `/customer/{customer_id}` | 固定后端代码 |
| CUS-05 | PUT | `/customer/{customer_id}/status` | 固定后端代码 |
| CUS-06 | POST | `/customer/{customer_id}/transfer` | 固定后端代码 |
| CUS-07 | POST | `/customer/{customer_id}/archive` | 固定后端代码 |
| CUS-08 | POST | `/customer/{customer_id}/followups` | 固定后端代码 |
| CUS-09 | GET | `/customer/{customer_id}/followups` | 固定后端代码 |
| CUS-10 | PATCH | `/customer/{customer_id}/followups/{followup_id}` | 固定后端代码 |
| DAY-01 | POST | `/daily-report/prepare` | LLM + 固定后端 |
| DAY-02 | POST | `/daily-report` | 固定后端代码 |
| DAY-03 | GET | `/daily-report` | 固定后端代码 |
| DAY-04 | GET | `/daily-report/{daily_report_id}` | 固定后端代码 |
| DAY-05 | PATCH | `/daily-report/{daily_report_id}` | 固定后端代码 |
| DAY-06 | POST | `/daily-report/{daily_report_id}/void` | 固定后端代码 |
| DAY-07 | POST | `/daily-report/summary` | LLM + 固定后端 |
| STU-01 | GET | `/students` | 固定后端代码 |
| STU-02 | GET | `/students/{student_id}` | 固定后端代码 |
| SCO-01 | POST | `/scores` | 固定后端代码 |
| SCO-02 | GET | `/scores` | 固定后端代码 |
| SCO-03 | GET | `/scores/{score_id}` | 固定后端代码 |
| SCO-04 | PATCH | `/scores/{score_id}` | 固定后端代码 |
| SCO-05 | POST | `/scores/{score_id}/void` | 固定后端代码 |
| LEA-01 | GET | `/leave` | 固定后端代码 |
| LEA-02 | GET | `/leave/{apply_id}` | 固定后端代码 |
| LEA-03 | POST | `/leave/{apply_id}/decision` | 固定后端代码 |
| LEA-04 | POST | `/leave/{apply_id}/assign` | 固定后端代码 |
| LEA-05 | GET | `/leave/{apply_id}/records` | 固定后端代码 |
| TIC-01 | GET | `/tickets` | 固定后端代码 |
| TIC-02 | GET | `/tickets/{ticket_id}` | 固定后端代码 |
| TIC-03 | POST | `/tickets/{ticket_id}/assign` | 固定后端代码 |
| TIC-04 | POST | `/tickets/{ticket_id}/follow` | 固定后端代码 |
| TIC-05 | POST | `/tickets/{ticket_id}/resolve` | 固定后端代码 |
| TIC-06 | GET | `/tickets/{ticket_id}/records` | 固定后端代码 |
| MEN-01 | GET | `/mental/warnings` | 固定后端代码 |
| MEN-02 | GET | `/mental/warnings/{warning_id}` | 固定后端代码 |
| MEN-03 | POST | `/mental/warnings/{warning_id}/assign` | 固定后端代码 |
| MEN-04 | POST | `/mental/warnings/{warning_id}/ack` | 固定后端代码 |
| MEN-05 | POST | `/mental/warnings/{warning_id}/follow` | 固定后端代码 |
| MEN-06 | POST | `/mental/warnings/{warning_id}/close` | 固定后端代码 |
| MEN-07 | GET | `/mental/warnings/{warning_id}/records` | 固定后端代码 |
| KNO-01 | GET | `/knowledge` | 固定后端代码 |
| KNO-02 | GET | `/knowledge/{knowledge_id}` | 固定后端代码 |
| KNO-03 | POST | `/knowledge/ask` | LLM + 固定后端 |
| TODO-01 | GET | `/todos` | 固定后端代码 |
| TODO-02 | GET | `/todos/summary` | 固定后端代码 |
| NOT-01 | GET | `/notifications` | 固定后端代码 |
| NOT-02 | POST | `/notifications/{source}/{notification_id}/read` | 固定后端代码 |
| AI-01 | POST | `/chat` | LLM + 固定后端 |
| AI-02 | POST | `/nl2sql` | LLM + 固定后端 |
| AI-03 | POST | `/command` | LLM + 固定后端 |
| AI-04 | POST | `/command/confirm` | 固定后端代码 |
| AI-05 | POST | `/audio/transcriptions` | 固定上传/调用 ASR 服务 |
| LOG-01 | GET | `/operation-logs` | 固定后端代码 |
| LOG-02 | GET | `/operations/{operation_id}` | 固定后端代码 |
| ADM-01 | POST | `/departments` | 固定后端代码 |
| ADM-02 | PATCH | `/departments/{department_id}` | 固定后端代码 |
| ADM-03 | POST | `/departments/{department_id}/status` | 固定后端代码 |
| ADM-04 | POST | `/employees` | 固定后端代码 |
| ADM-05 | PATCH | `/employees/{employee_id}` | 固定后端代码 |
| ADM-06 | POST | `/employees/{employee_id}/status` | 固定后端代码 |
| ADM-07 | PUT | `/employees/{employee_id}/roles` | 固定后端代码 |
| ADM-08 | POST | `/students` | 固定后端代码 |
| ADM-09 | PATCH | `/students/{student_id}` | 固定后端代码 |
| ADM-10 | POST | `/students/{student_id}/archive` | 固定后端代码 |
| ADM-11 | GET | `/students/{student_id}/staff-bindings` | 固定后端代码 |
| ADM-12 | POST | `/students/{student_id}/staff-bindings` | 固定后端代码 |
| ADM-13 | PATCH | `/students/{student_id}/staff-bindings/{binding_id}` | 固定后端代码 |
| ADM-14 | POST | `/knowledge` | 固定后端代码 |
| ADM-15 | PATCH | `/knowledge/{knowledge_id}` | 固定后端代码 |
| ADM-16 | POST | `/knowledge/{knowledge_id}/publish` | 固定后端代码 |
| ADM-17 | POST | `/knowledge/{knowledge_id}/disable` | 固定后端代码 |
| ADM-18 | POST | `/knowledge/{knowledge_id}/reindex` | 固定后端代码 |
| ADM-19 | DELETE | `/knowledge/{knowledge_id}` | 固定后端代码 |
