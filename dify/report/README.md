# 智能报告生成 Workflow

`report.yml` 是 Dify「智能报告生成」应用的 Workflow DSL，格式版本为 `0.5.0`。该工作流根据调用方提供的报告类型和指标文本，生成结构化的中文报告正文。

## 工作流流程

```text
用户输入 → DeepSeek LLM → 输出
```

LLM 提示词要求只依据输入数据撰写摘要、趋势、归因和建议；**严禁编造、估算、四舍五入或计算任何新数字**（包括差值、比率、百分比、平均值、合计、环比、同比、人均值和约数），描述数量关系时只使用定性文字，并使用 Markdown 小标题组织内容。该约束由操作文档 044「正文中的数字必须映射到受控指标，新增数字均失败」驱动，详见下方联调记录。

## 输入参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `report_code` | text-input | 是 | 报告类型或报告编码，用于说明报告主题。 |
| `metrics` | text-input | 是 | 指标数据，建议传入 JSON 格式文本。模型只能引用其中提供的数据。 |

`metrics` 是文本变量，调用 API 时应传字符串，例如：

```json
{
  "report_code": "monthly_summary",
  "metrics": "{\"month\":\"2026-09\",\"orders\":120,\"previous_month_orders\":100}"
}
```

## 输出

Workflow 结束节点将 LLM 的 `text` 映射为字符串变量 `report_text`。调用方从 Dify 响应的 `data.outputs.report_text` 读取报告正文。

## 模型与依赖

- 模式：Workflow
- 模型供应商：DeepSeek 插件（`langgenius/deepseek`，DSL 声明版本 `0.0.24`）
- 模型：`deepseek-v4-pro`
- 调用模式：chat
- temperature：`0.7`
- Prompt 上下文：未启用
- DSL 中不包含模型 API Key。请在目标 Dify 工作区安装并配置 DeepSeek 插件及凭据，再在 LLM 节点确认模型可用。

## 导入与发布

1. 在 Dify 工作室导入本目录的 `report.yml`。
2. 如果目标 Dify 版本提示 DSL 兼容问题，按平台提示调整后再导入。
3. 打开 Workflow，检查 DeepSeek 插件和 `deepseek-v4-pro` 模型配置。
4. 用合成的报告类型和指标数据运行测试，检查输出是否只引用输入数据中的数字。
5. 发布应用并创建该应用专用 API Key。密钥应存放在 StuProject 根目录 `.env` 的业务配置项中，不要写入本 DSL 或提交到 Git。

## API 调用示例

Dify Workflow 运行接口为 `POST {DIFY_API_BASE}/workflows/run`。以下示例中的地址、Key 和输入数据需替换为当前环境的实际值：

```bash
curl -X POST "http://127.0.0.1/v1/workflows/run" \
  -H "Authorization: Bearer <智能报告应用的API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "report_code": "monthly_summary",
      "metrics": "{\"month\":\"2026-09\",\"orders\":120,\"previous_month_orders\":100}"
    },
    "response_mode": "blocking",
    "user": "report-demo"
  }'
```

成功响应中检查 `data.status` 是否为 `succeeded`，并读取 `data.outputs.report_text`。本 README 描述的是 DSL 中声明的配置；导入、模型可用性和真实 API 调用仍需在目标 Dify 实例验证。

---

## 本地部署与联调记录（2026-10-17 实测）

### 部署现状

- 本机 Dify：官方 **1.12.1**，compose 位于 `D:\dify-1.12.1\docker\docker-compose.yaml`（项目名 `docker`），2026-09-29 完成初始化；组件含 api / worker / worker_beat / web / nginx / plugin_daemon / sandbox / ssrf_proxy / db_postgres / redis / weaviate。
- 访问地址：控制台 `http://127.0.0.1`，服务 API 前缀 `http://127.0.0.1/v1`（与 StuProject `.env` 的 `DIFY_API_BASE` 一致）。
- 报告应用：`cc3c20c5-606e-4e80-9a20-e22ca85debcd`（workflow · 智能报告生成），持有 API Key `app-zKpfBZfTzmkX4THw8lf1434j`（仅存本机 `.env`，不提交）。旧 Key `app-8KOa…` 实测 **401**（非已发布应用密钥），已在 `.env` 更换并注释说明。
- 模型：DSL 中 `deepseek-v4-pro` 为文档占位名；实际以 Dify 工作区绑定为准（本机 DeepSeek 插件由控制台配置，凭据只入 Dify 运行时，不入库、不入交付物）。

### 提示词强化（044 对账驱动）

首次真实联调发现：旧提示词只禁「编造/估算」，模型仍会做派生计算（如 18÷16≈1.1、18−16=2），被操作文档 044 对账拦截（正文新增数字即失败）。已将仓库 `report.yml` 的 LLM 提示词强化为「只能原样引用指标 JSON 中的数字，严禁任何派生计算，关系描述只用定性文字」，并同步发布到线上应用（版本 `v1.1-044`）。

仓库 DSL 是唯一事实来源。提示词变更后用以下脚本同步（只替换 LLM 节点 system 提示词，不动模型绑定与节点结构）：

```bash
# 凭据仅通过环境变量提供，不写入文件
# Dify 1.12 登录接口要求 password 提交 Base64 编码值；控制台 API 还需 X-CSRF-Token 头
$env:DIFY_CONSOLE_EMAIL="<控制台邮箱>"
$env:DIFY_CONSOLE_PASSWORD="<控制台密码>"
python scripts/report/sync_report_workflow.py --app-id cc3c20c5-606e-4e80-9a20-e22ca85debcd --dry-run
python scripts/report/sync_report_workflow.py --app-id cc3c20c5-606e-4e80-9a20-e22ca85debcd --publish --marked-name "v1.x"
```

### 联调验证

```bash
# 使用 .env 中的 REPORT_DIFY_API_KEY；也可用 --api-key 临时验证别的 Key
python scripts/report/verify_report_dify.py
```

验收标准（操作文档 041/044，不以 HTTP 200 为成功）：`data.status=succeeded`、`report_text` 非空、`<think>` 推理已剥离、正文数字全部可映射到输入指标（复用服务同款对账逻辑）。

五种报告类型（`REPORT_CODES` 全集）均复用同一 Dify 应用，仅以 `report_code` 输入区分。2026-10-17 逐类实测（内置样本指标，非真实取数）：

| report_code | 样本指标数 | 耗时 | 正文字符数 | 对账 |
|---|---:|---:|---:|:---:|
| customer_overview | 10 | 29.45s | 470 | 通过 |
| daily_report | 3 | 11.17s | 382 | 通过 |
| weekly_report | 3 | 13.67s | 273 | 通过 |
| mental_weekly | 9 | 20.50s | 435 | 通过 |
| complaint_weekly | 19 | 41.30s | 910 | 通过 |

```bash
# 逐类验证（脚本内置五类样本；退出码 0 为通过）
python scripts/report/verify_report_dify.py --report-code <report_code>
```

验证中发现并修复一处对账实现缺陷：整数值指标的浮点书写（指标 JSON 中 `75.0`）原先只放行整数形式 `75`，导致模型原样引用被判「新增数字」；已修正为整数值同时放行整数与 1/2 位小数书写，并补充回归测试。

### 已知问题与未决项

- **超时（需关注）**：`DIFY_API_TIMEOUT_SECONDS=60`。五类实测 11.17s–41.30s，complaint_weekly（19 项指标）已达上限的 69%；真实指标因状态/类别动态展开可能更多，逼近或超过 60s 会触发 `ReportModelOutcomeUnknown` 导致报告失败。建议尽快调大该值（如 120s）并在此记录依据。
- **DSL 模型占位名**：`deepseek-v4-pro` / `deepseek-v4-flash` 是文档占位值，Dify 日志曾出现 `Base model deepseek-v4-flash not found`；实际可用模型以工作区为准，导入后需在 LLM 节点确认。
- **控制台 API 约定**（脚本化操作时注意）：登录 `password` 需 Base64；会话凭据为 `access_token`/`csrf_token` Cookie，请求头带 `X-CSRF-Token`；发布接口 `marked_name` 上限 20 字符。
- **报告三表未在真实 MySQL 建表**：本机 MySQL 连接不可用（pymysql 认证失败），DDL 位于 `scripts/sql/report/`，落库级端到端验证待可用环境执行。
- 报告应用旁存在一个名为「智能报告」的 advanced-chat 应用（`bb6f0e29…`，无 API Key），与本 workflow 应用是历史并存关系；报告模块只使用 workflow 应用。
