# 学生助手 S01 AI辅助请假提交工作流

本目录保留可选的请假摘要工作流。S01默认不调用模型，直接按固定后端规则提交；仅请求generate_ai_summary=true时尝试生成摘要，失败仍保存原文。带模型调用的主要交付改为dify/student_ticket中的投诉摘要。

当前交付状态：代码、DSL及本地协议测试已完成；目标Dify实例导入、发布、模型供应商配置和真实模型联调待完成。本地测试的模型结果来自明确的测试替身，不能视为大模型实际输出。

## 文件和节点

- student_leave_submit.yml：完整应用DSL，包含app、workflow、graph、节点和连线；不是单独的Prompt。
- 开始节点：接收leave_content、leave_type、leave_start_at、leave_end_at四个字符串。
- LLM节点：生成JSON文本，字段为summary和review_points。摘要1至200字符，关注点最多3条，每条1至100字符。
- 结束节点：result映射到LLM节点的text，后端读取data.outputs.result并严格校验。

模型不会产生身份、SQL、审批结果或执行动作；实际审批由老师完成。Python保留学生原始参数，模型结果不覆盖学生ID、老师ID、日期或pending状态。

## 导入和发布

1. 在Dify工作室选择“导入DSL”，上传本目录的student_leave_submit.yml。
2. 文件采用0.3.0格式。目标实例可能提示版本兼容；本轮未在目标实例验证导入，不将结构校验等同于平台导入成功。
3. 打开LLM节点，选择工作区已经配置并可用的模型。文件中的OpenAI gpt-4o-mini只是可替换的示例配置；如果使用其他供应商，改选其实际模型。所需模型插件及模型凭据由Dify工作区配置，文件不携带密钥。
4. 用合成请假资料测试：检查输出为合法JSON，不含审批决定、不编造申请事实；确认结束节点输出变量仍叫result。
5. 发布Workflow，创建该应用专用API Key，填写本机忽略文件.env.student.local。不要使用项目现有的NL2SQL应用Key冒充请假应用Key。

配置名称与示例值：

    STUDENT_DIFY_LEAVE_BASE=http://127.0.0.1/v1
    STUDENT_DIFY_LEAVE_KEY=在本机填写专用应用Key
    STUDENT_DIFY_LEAVE_TIMEOUT=60
    STUDENT_DIFY_LEAVE_VERSION=student-leave-v1

.env和.env.student.local由app/config.py中的StudentLeaveDifySettings读取。未请求AI时ai_status=not_requested；请求AI且缺少Key时ai_status=unavailable、ai_analysis=null，但仍可提交申请。不要把真实Key写进DSL、日报或Git。

## 后端调用契约

app/clients/student_leave_dify.py中的StudentLeaveDifyClient.analyze_leave调用：

    POST {STUDENT_DIFY_LEAVE_BASE}/workflows/run
    Authorization: Bearer <请假应用专用Key>
    response_mode: blocking
    inputs: 四个请假字段
    user: 后端生成的student-<业务学生ID>

只接受data.status=succeeded。result可以是JSON字符串或对象，必须符合DifyLeaveContent；workflow_run_id取顶层值或data.id。后端附加analysis_version，并在edu_related_data.ai_analysis及成功回执中保存。

模型错误、未配置、超时或网络不可用由业务层降级，回执ai_status=unavailable，申请保持pending并保存原文。共享表结构或数据库不可用才阻止提交。正式请求的登录Token不会转发给Dify。

## 最小验证

在项目根目录运行：

    python -m pytest -q --confcutdir=tests/student_leave_s01 tests/student_leave_s01
    python tests/student_leave_s01/run_http_demo.py

第二条启动临时本机HTTP服务，但Dify使用httpx.MockTransport替身，输出会标明real_dify_verified=false；结束后服务和临时SQLite测试库自动清理。

完成实际导入、发布和专用Key配置后，再用组长提供的真实学生登录身份调用POST /api/v1/student/leave并明确传generate_ai_summary=true，核对Dify运行日志、workflow_run_id和MySQL数据，才能记录“真实模型联调通过”。本轮没有执行这项验收。

## 参考协议

- [Dify官方应用导入导出说明](https://docs.dify.ai/en/cloud/use-dify/workspace/app-management)
- [Dify官方Workflow执行入口源码](https://github.com/langgenius/dify/blob/main/api/controllers/service_api/app/workflow.py)
- [Dify官方DSL导入实现](https://github.com/langgenius/dify/blob/main/api/services/app_dsl_service.py)
