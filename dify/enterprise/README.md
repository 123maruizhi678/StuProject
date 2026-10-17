# 企业统一 Dify Workflow

当前只使用一个已发布应用：**StuProject-企业-统一工作流**，DSL 为 [enterprise.yml](enterprise.yml)。本机 Dify 1.11.4；应用 ID `66906358-488a-4116-86c3-05068185bf63`。

原 extract 应用在原 ID 下更新为统一工作流，保留历史版本；原 query、knowledge、summary 三个应用已标记“已合并归档”，停用 API 和站点入口，保留历史记录。没有删除应用历史或修改其他 Dify 应用。

## 分支与接口

统一入口只接收 `scene` 和 `payload`（JSON 字符串）。`payload` 中保留原场景输入及 `contract_version=enterprise-v1`；解包节点先校验对应字段类型，再按场景进入原有分支。原模型、提示词、结构化结果校验和知识 QA/RAG 子分支均保留，每次调用仅执行一个模型分支。

| scene | payload 中的业务字段 | result |
| --- | --- | --- |
| extract | text、action_catalog、field_schema、context | action、target、fields、missing_fields、needs_clarification |
| query | question、schema_context、dialect、query_constraints、bound_filters、schema_version | sql_template、params、referenced_tables、referenced_columns、schema_version |
| knowledge | question、mode（qa/rag）、candidates | answer、citations、mode |
| summary | content、report_date | summary |

所有成功路径的 End 均输出 `{scene, result}`。后端 `EnterpriseDifyClient.run(scene, inputs, user_id)` 仍返回原业务 `result`；查询场景在统一应用中也使用 `result`，不再读取 `query_result`。HTTP 路径、请求体和业务返回结构均保持原样，**前端代码没有修改**。

业务授权、知识检索、SQL 只读校验、命令预览和人工确认仍由后端负责；工作流不直接读写业务数据库。

## 配置

只使用根目录 `.env`：

```dotenv
ENTERPRISE_DIFY_API_BASE=http://127.0.0.1/v1
ENTERPRISE_DIFY_API_KEY=app-你的统一应用Key
ENTERPRISE_DIFY_CONTRACT_VERSION=enterprise-v1
```

企业专用地址为空时才回退 `DIFY_API_BASE`。本机已显式配置企业地址，其他模块的公共地址保持原值。四个原独立场景 Key 已从配置模型和模板移除，不再使用 `.env.enterprise.local`。

本次已通过后端真实调用验证 extract、query、knowledge.qa、knowledge.rag、summary 五条路径，均命中同一发布版本 `56a77975-47d2-469b-8426-73a1e450a6d1`。样例不含个人业务数据，没有写入业务记录。结果保存在 Git 忽略的 `.runtime/enterprise-unified/verification.json`。

## 维护

```powershell
# 从 legacy 原图重新生成唯一 DSL；也可通过 --source-dir 使用实际导出的四份已发布图。
python -X utf8 scripts/enterprise/export_workflows.py
python -X utf8 -m unittest tests.enterprise.test_unified_workflow -v
python -X utf8 scripts/enterprise/check_workflows.py
```

`legacy/` 的四份 DSL 是合并前参考，不作为当前部署入口。原始已发布版本、草稿和应用状态已备份在 `.runtime/enterprise-unified/dify-before/`；根环境配置备份在 `.runtime/enterprise-unified/env.before`。这些目录可能含运行配置，不应提交到 Git。

容器导入脚本为 `scripts/enterprise/import_local_dify.py`，要求 `--snapshot-dir` 指定本次工作区快照。它只更新原 extract 应用；`--archive-legacy --verified-workflow-id <已验证版本>` 用于核验发布后可逆停用其他三个入口。重新导入后，将 `/tmp/stuproject-enterprise-unified.runtime.json` 复制到 `.runtime/enterprise-unified/deployment.json`，运行 `apply_workflow_config.py` 安全写入根 `.env`，然后重启使用旧配置的后端进程。
