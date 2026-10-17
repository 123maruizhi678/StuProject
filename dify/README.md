# Dify 资产总览与导入顺序

本目录按业务模块存放 Dify 应用 DSL 与知识库资产。DSL 是 Dify 应用的导出格式（YAML），在控制台「创建应用 → 导入 DSL」即可还原应用；导入后模型与知识库等环境相关项需按各模块 README 手动核对。

## 目录与模块对应

| 目录 | 模块 | 资产 | 说明 |
| --- | --- | --- | --- |
| `agent/` | 客服 Agent | `客服Agent-Chatflow.yml`（实际为 Workflow）、`knowledge/`（4 类知识库） | 导入与绑定见 `agent/README.md`；知识库维护见 `agent/knowledge/README.md` |
| `customer/` | 客户研判 | `customer-extract.yml`（可选抽取）、`knowledge/`（研判规则） | 规划资产，真实规则须甲方提供 |
| `report/` | 智能报告 | `report.yml` | 已存在，DeepSeek 插件模型 |
| `enterprise/` | 企业智能助手 | 提取 / 只读 SQL / QA-RAG / 日报摘要 DSL | 规划资产，legacy 为历史参考 |
| `student/` | 学生助手 | `student_assistant.yml`（统一应用目标）、`legacy/`（历史最小单元） | 当前只部署统一学生应用 |

## 导入顺序建议

1. 先建知识库（客服 4 类见 `agent/knowledge/README.md`），记录 `dataset_id`；
2. 再导入对应模块 DSL，按各模块 README 绑定模型与知识库；
3. 发布应用后创建 API Key，填入根目录 `.env` 对应配置项（真实值不进 Git）。

## 约束

- DSL 内不写 API Key、数据库密码等真实值；
- 换 Dify 环境导入时，模型与知识库绑定须按新环境重新核对；
- 各模块 README 与主文档《开发文档/操作文档.md》不一致时，以主文档为准。
