# 智能报告生成 Workflow

`report.yml` 是 Dify「智能报告生成」应用的 Workflow DSL，格式版本为 `0.5.0`。该工作流根据调用方提供的报告类型和指标文本，生成结构化的中文报告正文。

## 工作流流程

```text
用户输入 → DeepSeek LLM → 输出
```

LLM 提示词要求只依据输入数据撰写摘要、趋势、归因和建议，不得编造或估算输入中不存在的数字，并使用 Markdown 小标题组织内容。

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
