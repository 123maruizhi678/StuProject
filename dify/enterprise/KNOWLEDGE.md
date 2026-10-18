# 企业知识库接入

## 调用方式

保留现有企业统一 Workflow 的 `knowledge` 分支及 `enterprise-v1` 契约：

1. 后端验证当前登录账号的 `enterprise.knowledge.read` 权限。
2. 从已有 `knowledge_entry` 筛选已发布、已生效、未过期且当前账号可见的来源。
3. 对登记为 Dify 来源的条目，调用知识库 API 进行检索，只保留登记文档内已启用且索引完成的片段。
4. 将片段作为 `candidates` 传给现有问答分支。模型只能引用真实的条目编号和版本。
5. 返回前再次验证账号、条目版本、部门可见范围和 Dify 文档状态。

这里无需让工作流检索整个工作区，也无需新建数据库表。Dify 工作流中原有
`知识问答 · 授权文档片段回答` 节点继续使用后端传入的授权候选。

## 后端配置

在**实际运行后端**的根目录 `.env` 中配置：

```dotenv
ENTERPRISE_DIFY_DATASET_API_BASE=http://192.168.5.12/v1
ENTERPRISE_DIFY_DATASET_API_KEY=由管理员私下配置的知识库服务密钥
```

知识库服务 Key 与现有 `ENTERPRISE_DIFY_API_KEY` 工作流应用 Key 不同。应在
Dify“知识库 → 服务 API”中配置，并尽量只授权本次请假知识库。密钥只留在后端，
不写前端、不发送到聊天或日志中。配置后重启实际后端服务。

## 登记请假来源

当前确认的知识库 ID 为 `a43aba50-4af1-4062-bc56-47c6255e5da4`，文档名为
`学生请假申请与审批流程.docx`。通过管理接口登记到现有 `knowledge_entry`：

```text
python scripts/enterprise/connect_dify_knowledge.py --backend-url http://192.168.5.12:8000 --dataset-id a43aba50-4af1-4062-bc56-47c6255e5da4 --document-name 学生请假申请与审批流程.docx --department-id 实际授权部门编号
```

默认只预览登记计划。核对后加 `--apply` 才新增/复用条目并发布。要向全体员工
开放时，用明确的 `--all-employees` 替代 `--department-id`。脚本要求当前账号具备
知识维护和发布权限，不会创建账号、修改账号权限或改表。

脚本会私下询问系统密码；也可通过进程环境变量 `STUPROJECT_ACCESS_TOKEN` 使用
已有会话。令牌及密码不落盘。Dify 文档 ID 从知识库 API 按完整文档名唯一匹配，
不使用示例或猜测编号。重复执行不会重复登记同一条来源。

也可在已授权的知识管理界面创建“文档”条目，来源填写：

```text
dify://datasets/知识库UUID/documents/真实文档UUID
```

此类条目无需复制全文到关系库；填写访问部门、审核并发布后，运行时实时检索。
原有本地 FAQ 和正文文档保持原检索方式。

## 验证

使用实际账号访问“企业智能助手”，输入“怎么请假”。成功时应显示申请步骤和
`学生请假申请与审批流程.docx` 来源。缺少知识库 Key 时返回明确的配置错误；
无授权资料或无检索结果时仍返回 `no_source`，不根据常识编造制度。

隔离回归位于 `tests/enterprise/test_dify_knowledge.py`，使用内存 SQLite 和模拟
Dify 响应，不写真实业务数据。部署必须发生在前端代理指向的后端上；仅修改
另一台机器的源文件或重启另一套服务不会改变 `192.168.5.12:8000` 的查询结果。
