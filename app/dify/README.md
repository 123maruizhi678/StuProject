# 学生查询与成绩：本机联调

本轮仅实现企业接口方案 5.4 的七项业务接口，另加一个学生/成绩自然语言只读查询入口。代码位于 `app/api/enterprise_student.py`、`app/services/enterprise_student.py`、`app/services/enterprise_nl2sql.py`、对应 models/schemas 中。

## 接口

统一前缀 `/api/v1/enterprise`，Bearer Token 使用 `/api/v1/auth/login` 获取。返回 `{code,message,data}`；企业接口沿用 HTTP 200 + 业务码（400 参数、401 认证、403 权限、404 对象不可见、409 并发/唯一键、502 查询执行、503 模型不可用）。

| 方法 | 路径 | 功能 |
|---|---|---|
| GET | `/students` | 授权学生分页；支持 keyword、student_no、department_id、status、is_archived，page_size 最大100 |
| GET | `/students/{student_id}` | 基本资料及本人有效职责关系；不返回心理或联系方式 |
| POST | `/scores` | 创建成绩；写入要求 `Idempotency-Key` |
| GET | `/scores` | 授权课程成绩分页；按 student_id、course_code、term_code、assessment_code、attempt_no、status 筛选 |
| GET | `/scores/{score_id}` | 成绩、最近操作者、时间、版本和已授权操作历史 |
| PATCH | `/scores/{score_id}` | 仅更正得分/满分，要求 change_reason、expected_version 和幂等键 |
| POST | `/scores/{score_id}/void` | 作废但保留记录、组合唯一键及历史；要求原因、版本和幂等键 |
| POST | `/student-scores/nl-query` | `{ "question": "查询学号 EIT-S001 的有效英语成绩" }`，只查询学生或成绩，不暴露 SQL |

返回 ID 为字符串；请求中的 ID 使用内部主键，不能把教务 ID 或 CRM ID 当内部主键。

## 权限与规则

- 当前账号必须是绑定了 active 员工的 employee。员工角色从数据库 `employee.role_codes` 读取，不接受请求自报。
- 学生查询：teacher 的有效 class_teacher/service_advisor 关系，或 academic 的有效 score_editor 关系。日期按 UTC 判断，起始含、截止不含。部门等过滤不会扩大关系范围。
- 成绩查询和写入：academic + active score_editor 关系 + 精确 course_scope_code；空课程范围不授予全部课程。默认 admin 无学生成绩权限。
- 普通员工响应不包含 external_student_id/crm_student_id；仅 `ENTERPRISE_STUDENT_MAINTAINER_IDS` 显式配置且本身已有学生访问关系的员工可见。
- 受控课程目录为 `app/enterprise_courses.yaml`。当前仅含虚构联调课程 EIT-ENGLISH/EIT-MATH；正式教务对接时替换为实际目录，不新增成绩表字段。
- `max_score > 0`，`0 <= score_value <= max_score`，最多两位小数，attempt_no 为正整数。更正不能变更学生、课程、学期、考核、次数。
- 新增受组合唯一键约束；作废记录仍占用该键；未实现恢复入口。更正/作废使用条件更新核对版本，并将旧值、新值、原因和真实员工写入 operation_log，与业务变更同事务提交。
- 写操作要求 ASCII 幂等键（1～64字符，字母数字及 `._:-`）；同员工/动作/键同参数返回原回执，异参数返回409。失败事务回滚。
- 本机测试使用 `ENTERPRISE_SCORE_AUTHORITY=local`。教务为只读权威来源时设置 `external_readonly`，所有本地成绩写入返回403，查询仍可用。

## 本机 Dify 配置

- 实例：`http://localhost`，工作区 `msj's Workspace`。
- 应用：[企业学生与成绩-NL2SQL联调](http://localhost/app/516a21f8-2658-4475-b297-83fc523b4ee4/workflow)。
- 一个 Workflow、一个已有 DeepSeek `deepseek-flash` 模型节点：输入 `question` → 生成 SQL 候选 → 输出 `sql`。
- 模型参数：temperature=0、thinking=false、max_tokens=1024，`reasoning_format=separated`。真实 HTTP 联调发现默认推理内容会混入 text；启用分离后 sql 仅包含最终候选，不放宽后端 SQL 校验。
- DSL：[student_scores_nl2sql.yml](student_scores_nl2sql.yml)，由 `python -m app.dify.export_student_scores` 生成，不含业务记录或密钥。
- 复用 `app/core/dify.py` 的 `POST /workflows/run`、blocking、`inputs.question`、输出 sql 契约。原有 `DIFY_API_KEY` 不被替换；新入口使用专用 `STUDENT_SCORE_DIFY_BASE` / `STUDENT_SCORE_DIFY_KEY`。
- 后端传入的问题包包含允许的虚拟表结构，不把真实数据库结构、密码、学生档案整表交给模型。`authorized_students` / `authorized_scores` 是后端生成的授权派生数据集，不要求在 MySQL 新建全局视图。
- 返回 SQL 通过 [SQLGlot AST](https://sqlglot.com/) 校验：单 SELECT、单授权表、字段白名单、禁止 SELECT *、连接、子查询、任意函数、注释、锁和写入；强制 LIMIT<=200。用户字面量转绑定参数；表引用由后端替换为真实员工范围的派生表，`OR 1=1` 也不能扩权。
- MySQL 查询使用只读事务和 MAX_EXECUTION_TIME(3000)；当前沿用项目数据库账号。正式部署应提供独立只读账号并完成压测；不把本轮样例验证当作生产安全或语义准确率验收。

当前 Dify 已按用户明确授权发布；专用 API Key 已创建并仅写入本机 `.env` 的 `STUDENT_SCORE_DIFY_KEY`，`STUDENT_SCORE_DIFY_BASE=http://localhost/v1`。完整 HTTP → 本机 Dify `/workflows/run` → SQL AST 校验 → education_agent 授权查询链路已通过，未复用旧应用 Key。

## 本机启动和凭据

在项目根目录，使用现有 SST 环境：

```powershell
& 'C:\Users\Windows\anaconda3\envs\SST\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

文档：`http://127.0.0.1:8000/docs`。

`.env` 使用用户指定的本机 `education_agent`。用户要求已将 DB_PASSWORD 改为可连接的值。脚本另生成 AUTH_SECRET_KEY 和虚构教务登录信息 `ENTERPRISE_TEST_USERNAME` / `ENTERPRISE_TEST_PASSWORD`；敏感值仅保存于本机 `.env`，不放进本说明、DSL 或测试结果。

初始化：`python -m app.dify.prepare_local_test`。只允许本机 education_agent；补充原库缺少的 nullable `student_profile.crm_student_id` 及唯一索引，按仓库 DDL 新建缺少的 user_account。仅为已有虚构 EIT-E005 教务员工创建 `eit-academic` 账号；不运行总删表脚本、不重置现有账号。

登录后调用示例（用实际 Token 替换）：

```http
POST /api/v1/enterprise/scores
Authorization: Bearer <access_token>
Idempotency-Key: <本次逻辑请求唯一键>
Content-Type: application/json

{"student_id":910001,"course_code":"EIT-ENGLISH","term_code":"EIT-2026-AUTUMN","assessment_code":"LOCAL-DEMO-001","attempt_no":1,"score_value":"85.50","max_score":"100.00"}
```

重试保持同键同参数；测试更正/作废请使用返回的 score_id 和 version。

## 验证结果与重跑

- 37 项隔离测试通过：真实 JWT 登录链、员工状态、关系日期、课程范围、缺权限、数值范围、幂等、组合键、作废、旧值/新值审计、版本冲突、只读权威模式、SQL 越权/注入形状、Dify HTTP 输入输出及失败处理。
- 真实 education_agent 七项接口与登录全部通过。创建虚构测试成绩910007，更正后作废，保留3条审计；详见 [local_smoke_results.json](local_smoke_results.json)。
- 本机 Dify 真实模型草稿测试：学生查询 SQL、有效英语成绩查询 SQL 均生成成功；要求写成绩时返回 `UNSUPPORTED`。
- 完整真实模型 HTTP 链路验证通过：学生精确查询、有效英语成绩查询、授权范围内有效英语成绩计数，分别与固定接口结果核对一致。
- 自然语言要求写成绩时返回业务码400；请求前后固定接口返回的成绩值、版本及对象集合完全一致。本轮完整链路验证未新增或更改业务记录。
- 端到端结果：[nl2sql_e2e_results.json](nl2sql_e2e_results.json)。此前 [local_smoke_results.json](local_smoke_results.json) 记录的是发布前的七项接口测试，因此其中专用 Dify API 项仍为当时的503；当前状态以新的端到端记录为准。

```powershell
# 隔离测试，不改真实业务记录
python -m pytest app/tests/test_enterprise_student.py -q -p no:cacheprovider
# 真实接口联调；仅为 EIT-S001 新增一条唯一考核编号的虚构成绩，再更正并作废，保留审计
python -m app.dify.smoke_local
# 真实模型端到端联调，仅查询，不写业务记录；要求 API 已启动并加载专用Key
python -m app.dify.smoke_nl2sql
```

本轮只验证功能可运行，未做生产并发压测、真实业务语义准确率评测或外部教务系统联调。未恢复此前暂存删除的学生模块，也未执行 Git 提交。
