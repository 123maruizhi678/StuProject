# 客户信息抽取（客户研判模块）

已在本地 Dify 发布独立 Workflow：客户信息抽取。

- 应用 ID：8658ad46-1bea-4a41-89d3-6312fc578dd8
- 管理地址：http://127.0.0.1/app/8658ad46-1bea-4a41-89d3-6312fc578dd8/workflow
- 模型：本地工作区已配置的 deepseek-flash，temperature=0。
- 节点：开始 → 输入契约校验 → 字段抽取 → 输出严格校验 → 结束。
- 输入：text、field_schema（后端固定 JSON Schema）、contract_version=v1。
- 输出：fields 对象、contract_version=v1。只接受 data.status=succeeded。
- 支持13项字段：姓名、性别、年龄、学历、专业、工龄、行业、职位、城市、收入、意向产品编码、电话、邮箱。
- 模型仅抽取明确事实，不生成身份、部门、权限、审批、评分或产品命中结论。最终判定调用后端版本化规则引擎。

后端配置位于项目根目录 .env（真实值不写入本说明）：

```dotenv
CUSTOMER_EXTRACT_DIFY_API_BASE=http://127.0.0.1/v1
CUSTOMER_EXTRACT_DIFY_APP_ID=8658ad46-1bea-4a41-89d3-6312fc578dd8
CUSTOMER_EXTRACT_DIFY_API_KEY=
CUSTOMER_EXTRACT_DIFY_TIMEOUT_SECONDS=60
```

调用：`ExtractorService().extract(text)`；模型密钥未配置、网络/HTTP错误、工作流失败、版本不匹配或输出不符合严格 Schema 时，保留电话、邮箱、年龄的确定性抽取，不自动重试。整数拒绝 bool、浮点数和字符串；Excel 确定性列映射允许安全规整数字字符串。单段多客户资料不能合并成一个客户，请使用 Excel/CSV 逐行导入或拆分来源。

## 后端部署与复测

在项目根目录、SST Python 环境运行：

```powershell
python scripts/customer/build_workflow.py
# 普通登录需要进程环境变量 DIFY_CONSOLE_EMAIL / DIFY_CONSOLE_PASSWORD。
python scripts/customer/deploy_workflow.py --publish --configure-env .env
python -m pytest tests/customer -q
python scripts/customer/verify_dify.py
```

`deploy_workflow.py` 先保存该应用的旧草稿与发布图到 backups，再更新并发布，保留工作区现有模型绑定。API Key 只写后端 .env，不输出。`--local-container docker-api-1` 仅用于已获用户明确授权的本机管理员临时会话签发；脚本不会保存该会话，不修改账号密码或其他应用。

`verification.json` 保存合成样本的逐项结果、工作流执行ID与延迟，不写业务数据库。测试覆盖完整/叙述/稀疏资料、未知信息、提示注入、号码清理、零值、多客户、产品编码不推断、邮箱不推断姓名及非法版本/Schema。样本通过率不代表真实业务准确率；正式规则和真实验收样本仍需业务方确认。

## 本次范围

完成模型工作流、后端抽取适配和规则函数联调。没有修改前端，没有建表或向业务表写入测试数据。原项目 main.py 的客户业务路由仍未挂载，完整来源入库/权限范围/批量事务验收属于后续模块接入；不能把本次模型联调当作完整业务 API 已上线。

如需回滚，使用 backups 中首次部署前保存的 graph/features 通过草稿接口恢复并重新发布；后端代码的原始备份位于本次交付的代码备份目录。当前模型抽取已启用，删除该模块专用 API Key 配置可停用语义抽取并保留确定性路径。
