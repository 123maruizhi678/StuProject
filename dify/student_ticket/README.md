# 学生助手：投诉摘要与建议工单

负责人：蒋立建；提交分支：Albert。对应需求文档《学生智能助手》2.1第3项、3.3.2智能摘要。

`student_ticket_summary.yml` 是可导入Dify的Workflow应用DSL，包含开始→LLM→结束节点及连线。真实目标实例导入、模型配置、发布和真实模型验收仍待完成；本地协议验证使用明确标记的测试替身。

## 输入输出

开始节点接收content（1—5000字符）、ticket_type（complaint或suggestion）、category_code。分类受控为application、visa、teaching、service、other。

LLM仅返回JSON：

```json
{"summary":"学生描述的问题与诉求，不编造事实。","suggested_category":"teaching"}
```

结束节点变量result引用LLM.text。后端检查data.status=succeeded、result结构、摘要长度1—300、受控分类及workflow_run_id。额外的身份、SQL、状态等字段一律拒收。模型分类作为建议保存到操作回执，不覆盖学生所选category_code，也不决定处理部门、员工、优先级和状态。

## 配置与导入

1. 导入本目录YAML。文件沿用项目既有0.3.0格式；目标实例兼容性须实际验证。
2. 打开LLM节点，选择本机Dify工作区已配置的可用模型。文件内模型是可替换示例；供应商插件和模型凭据由工作区配置。
3. 使用合成投诉测试JSON输出，确认result映射后发布Workflow。
4. 在忽略文件`.env.student.local`填写应用专用配置，勿提交真实Key。

```dotenv
STUDENT_DIFY_TICKET_BASE=http://127.0.0.1/v1
STUDENT_DIFY_TICKET_KEY=在本机填写投诉Workflow专用Key
STUDENT_DIFY_TICKET_TIMEOUT=15
STUDENT_DIFY_TICKET_VERSION=student-ticket-v1
STUDENT_TICKET_RESPONSE_HOURS=24
STUDENT_TICKET_RESOLUTION_HOURS=72
```

受理部门默认使用student_profile.department_id（学生服务归属部门）。需要统一受理部门时，增加STUDENT_TICKET_DEPARTMENT_ID并填写已存在且active的真实部门ID；后端会再次查询核验，不允许凭空写ID。24/72小时是当前可配置默认时限，正式SLA和分类口径需与企业侧确认。

调用协议：`POST {BASE}/workflows/run`，专用Bearer Key，inputs为上述三字段，response_mode=blocking；user由后端生成为student-业务学生ID。登录JWT、数据库口令、员工ID和部门ID不发给Dify。原文会发送给配置的模型服务，真实数据联调应遵循项目的数据使用约定。

## 失败与权限边界

未配置、超时、HTTP失败、工作流失败或非法输出：保存工单原文，ai_summary=NULL，回执ai_status=unavailable、ai_analysis=null。没有伪造摘要、自动重试任务或后台补摘要功能；成功回执的重试保持原结果。需要后续补摘要应另行设计带权限和审计的更新动作。

S05只新建open工单，不代替企业分派和处理。S06—S08只查询本人，不调用Dify或NL2SQL。所有数据库操作都在后端固定代码中完成。

## 本地验证

在项目根目录执行：

```powershell
& 'D:\python\python.exe' -X utf8 -m pytest -q --confcutdir=tests tests/student_leave_s01 tests/student_ticket_s05
& 'D:\python\python.exe' -X utf8 scripts/check_student_shared_schema.py --local-instance
& 'D:\python\python.exe' -X utf8 tests/student_ticket_s05/run_mysql_http_demo.py
```

第二、三条仅适用于本机已有的学生专用MySQL实例（instance.json在项目外的私有目录）。第三条建立随机前缀student_test_的临时数据库，用公共SQL的完整CREATE语句验证真实外键，结束后只清理自己创建的测试库。测试身份由夹具注入，Dify由MockTransport模拟，不表示公共JWT或真实模型已通过。

正式入口使用公共.env的数据库配置，`.env.student.local`这里只补充学生Dify和业务配置，不会自动替换公共数据库配置。完整工程启动仍依赖组长公共鉴权配置和依赖就绪。
