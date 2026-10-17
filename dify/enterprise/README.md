# 企业Dify工作流

本机已复用现有Dify 1.11.4，控制台为 http://127.0.0.1 ，业务API为 http://127.0.0.1/v1 。现有Compose位于`D:\dify-1.11.4\dify-1.11.4\docker\docker-compose.yaml`；没有升级镜像、重建数据卷或修改其他模块应用。本机已有Nginx使用80／443端口，因此没有另启18080实例。

| DSL | 应用名 | 服务端配置名 |
| --- | --- | --- |
| enterprise_extract.yml | StuProject-企业-extract | ENTERPRISE_EXTRACT_DIFY_API_KEY |
| enterprise_nl2sql_readonly.yml | StuProject-企业-query | ENTERPRISE_NL2SQL_DIFY_API_KEY |
| enterprise_knowledge.yml | StuProject-企业-knowledge | ENTERPRISE_KNOWLEDGE_DIFY_API_KEY |
| enterprise_daily_summary.yml | StuProject-企业-summary | ENTERPRISE_SUMMARY_DIFY_API_KEY |

四个应用均已发布，输出契约为`enterprise-v1`；查询另含`enterprise-query-v1`。本机复用已安装的`langgenius/deepseek/deepseek`供应商和`deepseek-flash`模型。Dify服务在本地，文本模型使用已有供应商连接；语音在本机faster-whisper推理。更换文本模型前，可用`export_workflows.py --provider ... --model ...`重新生成DSL并实际验证输出。

知识应用是同一Workflow中的条件节点：`mode=qa`走FAQ匹配，否则走RAG文档片段分支，各分支都有JSON类型校验和结构化End。授权和检索在业务后端先完成，Dify没有业务MySQL连接或写入工具。当前以关系库正文为检索源，不建立额外私密向量副本；需要管理员录入并发布真实制度后才能回答本单位具体问题。无来源返回无法核实。

重新导入本次应用（PowerShell；保持本机实例和工作区）：

```powershell
docker cp dify/enterprise/. docker-api-1:/tmp/stuproject-enterprise/
docker cp scripts/enterprise/import_local_dify.py docker-api-1:/tmp/stuproject_import_enterprise.py
docker exec -w /app/api docker-api-1 /app/api/.venv/bin/python /tmp/stuproject_import_enterprise.py
python -X utf8 scripts/enterprise/check_workflows.py
```

导入器只更新同名四个企业应用，要求唯一工作区及合法所有者，不猜多个工作区。它使用本机1.11.4内部服务；升级Dify前应重新核验这些服务的兼容性。应用Key只写入容器`/tmp/stuproject-enterprise.runtime.json`，标准输出不显示Key。首次接入可将该文件复制到项目被忽略的`.env.enterprise-runtime`后运行`configure_local.py`；运行覆盖值写入被忽略的`.env.enterprise.local`。不要把这些文件或`.runtime`提交到Git。已有Key重用；重新发布不另建重复应用。

实际验收命令会调用四个应用，并分别调用知识QA和RAG分支。输入是标注为联调的非个人样例，不把样例保存为正式制度或客户记录。工作流输出解析失败、缺字段或模型不可用时返回503，固定表单服务可以继续使用。
