# 客户研判模块 · Dify 资产

本目录承载客户研判模块在 Dify 中的资产，供团队导入与维护。

## 资产清单

| 资产 | 类型 | 说明 |
|------|------|------|
| `customer-extract.yml` | Workflow（DSL 导出） | 客户字段语义抽取工作流，辅助非结构化文本抽取，可导入 Dify |
| `knowledge/客户画像研判规则.md` | 知识库文档 | 研判规则语义、字段字典、运算符与评分口径（参考资产） |

## 客户字段抽取 Workflow

- **应用名**：客户信息抽取（`mode: workflow`）
- **节点**：start → LLM(deepseek-flash) → code(字段规整) → end
- **输入**：`text`（来源文本）、`field_schema`（字段 schema JSON）、`contract_version`（契约版本）
- **输出**：`fields`（规整后的字段对象）
- **模型**：DeepSeek `deepseek-flash`（`langgenius/deepseek/deepseek`）
- **用途**：仅辅助非结构化文本语义抽取（姓名、学历、专业、行业、城市、收入、意向产品等）。
  **规则裁决不经过该工作流**，由后端确定性规则引擎执行。

### 导入方式

在 Dify 控制台「导入 DSL 文件」中选择 `customer-extract.yml`，导入后：
1. 确认 DeepSeek 模型凭证（API Key 已按团队统一密钥配置）。
2. 发布应用。
3. 复制该应用的 API Key，填入后端 `.env` 的 `CUSTOMER_EXTRACT_DIFY_API_KEY`。

### 后端调用契约

后端 `app/clients/customer/extract_dify.py` 通过 `POST /v1/workflows/run` 调用，
`response_mode=blocking`，读取 `data.outputs.fields`。

## 知识库「客户画像研判规则」

- 索引方式：经济型（economy）。
- 内容：研判规则结构（match_logic / conditions / score_rules）、字段字典、运算符表、
  示例规则（PROD-A 稳健理财、PROD-B 高端养老险）、研判流程与口径约定。
- 该知识库为参考资产；规则裁决由 `app/services/customer/judge_service.py` 确定性执行。
