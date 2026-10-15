# 数据库建表脚本说明

本目录的 `all.sql` 是根据当前确认的数据模型整理的 MySQL 建表脚本。

## 当前模型选择

- 新增 `user_account`，只保存统一用户名、密码哈希、身份类型，以及关联员工/客户/学生业务记录所需的外键。
- 不向 `employee`、`customer_profile`、`student_profile` 等现有业务表增加字段；用户表通过 `employee_id`、`customer_id` 或 `student_id` 单向引用业务主键。
- `employee`、`customer_profile`、`student_profile` 继续只保存原有业务资料；用户表通过业务主键关联它们。
- 学生主档使用 `student_profile`。
- 学生请假/行政申请使用 `student_admin_service`。
- 投诉与建议工单使用 `service_ticket`，处理过程记录在 `service_ticket_record`。
- 原重复模型 `student_identity`、`student_leave_request`、`after_sales_ticket` 未纳入本脚本。
- `student_profile` 增加了 `crm_student_id` 字段及唯一索引，用于保留 CRM 学生标识。

## 当前身份类型与关联

| 身份/记录 | 对应业务表 | 用户表关联方式 |
|---|---|---|
| 员工 | `employee` | `user_account.employee_id` 外键指向员工主键。 |
| 客户/意向客户 | `customer_profile` | `user_account.customer_id` 外键指向客户主键。 |
| 学生 | `student_profile` | `user_account.student_id` 外键指向学生主键。 |
| 客服访客 | `chat_session.user_id` | 目前是匿名/访客字符串标识，不属于正式账号身份。 |
| 活动报名联系人 | `event_signup` | 只记录活动报名时的姓名和手机号，不自动创建用户账号。 |

一个 `user_account` 记录只对应一种身份，三种业务外键中必须且只能填写一个。员工、客户、学生等现有表保持原样，不新增指向用户表的字段。若同一自然人需要多个身份，当前结构应建立多个账号记录；如果需要一个账号拥有多个身份，需将身份拆成独立的用户身份关联表后再扩展。

`password_hash` 用于保存密码哈希，不能存明文密码；建议应用使用经过审查的密码哈希算法与参数。新用户账号必须绑定一条已存在的员工、客户或学生业务记录。客服匿名访客不需要账号。
## 环境要求

- MySQL 8.0.16 或更高版本（脚本使用 `CHECK` 约束）。
- 运行前先连接到目标数据库。脚本不会创建数据库/schema。
- 执行前备份目标数据库。脚本会先删除下方清单中的 30 张表（若存在），再重新创建 31 张表；这些旧表中的所有数据都会丢失。脚本不包含旧数据迁移。

## 执行方式

在 MySQL 客户端中选定目标数据库后执行脚本。例如：

```sql
USE your_database_name;
SOURCE D:/AI/StuProject/scripts/sql/all.sql;
```

也可以使用 MySQL Workbench、DBeaver 等客户端打开 SQL 文件，在目标数据库连接中执行。

## 表清单（31 张）

### 客服Agent

`course_project`、`lecture_event`、`event_signup`、`faq`、`chat_session`、`chat_message`

### 学生智能助手

`student_profile`、`student_admin_service`、`mental_health_profile`、`mental_warning`、`student_academic_event`、`student_academic_reminder`、`student_application_progress`、`student_notification`、`student_service_action`

### 统一用户账号

`user_account`

### 企业智能助手与组织数据

`org_department`、`employee`、`customer_profile`、`customer_followup`、`employee_daily_report`、`student_staff_binding`、`student_score`、`service_ticket`、`service_ticket_record`、`knowledge_entry`、`business_notification`、`operation_log`

### 智能报告

`report_config`、`report_record`、`report_metric`

## 执行注意事项

1. 这是破坏性重建脚本，不是升级/迁移脚本。它先执行 `DROP TABLE IF EXISTS` 删除 30 张目标表，再创建 31 张表（包括 `user_account`）；重复执行会再次清空这些表中的数据。执行前必须备份并确认数据库选对。
2. 脚本设置字符集为 `utf8mb4`、会话时区为 UTC（`+00:00`），并在建表期间关闭外键检查，末尾重新开启。请完整执行；若中途失败，先检查数据库状态和错误原因，勿直接重跑，以免再次删除数据。
3. `student_profile` 是学生唯一主档。若从旧模型迁移数据，需将旧学生身份标识、请假记录和投诉工单迁入选定表，并更新应用及外部接口引用。本脚本本身不会迁移这些数据。
4. 请先确认 CRM/教务学生编号、责任老师关联、审批字段等业务映射后再导入数据。`crm_student_id` 可以为空，但非空值必须唯一。
5. 其他可选精简项（例如对话记录、报告指标、通知队列等）仍按需求文档保留在脚本中；如项目确定不实现相应功能，应先确认代码和数据依赖，再单独调整 DDL。

## 相关文件

- 建表脚本：`all.sql`
- 表分类及精简建议：`all.sql表分类与精简建议.md`

## 各表用途与字段说明

### `user_account`

**功能：** 统一管理系统登录账号，并通过外键关联一条现有员工、客户或学生业务记录。业务身份资料仍保存在对应业务表中。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `user_id` | `BIGINT` | 用户账号主键。 |
| `username` | `VARCHAR(64)` | 唯一登录用户名。 |
| `password_hash` | `VARCHAR(255)` | 密码哈希，禁止存储明文密码。 |
| `identity_type` | `VARCHAR(20)` | 身份类型：employee、customer 或 student。 |
| `employee_id` | `BIGINT` | 员工身份外键；身份为 employee 时必填。 |
| `customer_id` | `BIGINT` | 客户身份外键；身份为 customer 时必填。 |
| `student_id` | `BIGINT` | 学生身份外键；身份为 student 时必填。 |
| `created_at` | `DATETIME(3)` | 用户记录创建时间（UTC）。 |
| `updated_at` | `DATETIME(3)` | 用户记录最近更新时间（UTC）。 |
### `course_project`

**功能：** 保存客服Agent可检索和推荐的课程、留学申请及背景提升项目。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `id` | `BIGINT` | 主键，自增 |
| `course_name` | `VARCHAR(128)` | 课程名称 |
| `category` | `VARCHAR(32)` | 类别：留学申请/背景提升/语言培训 |
| `target_audience` | `VARCHAR(128)` | 适用人群（学历/意向国家等） |
| `description` | `TEXT` | 课程简介 |
| `location` | `VARCHAR(128)` | 上课地点 |
| `signup_method` | `VARCHAR(128)` | 报名方式 |
| `status` | `VARCHAR(16)` | 状态：上架/下架 |
| `created_at` | `DATETIME` | 创建时间 |
| `updated_at` | `DATETIME` | 更新时间 |

### `lecture_event`

**功能：** 保存讲座或分享活动的时间、地点、名额和报名状态。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `id` | `BIGINT` | 主键，自增 |
| `event_name` | `VARCHAR(128)` | 活动名称 |
| `event_type` | `VARCHAR(16)` | 线上/线下 |
| `start_time` | `DATETIME` | 开始时间 |
| `location` | `VARCHAR(128)` | 地点 |
| `signup_method` | `VARCHAR(128)` | 报名方式 |
| `quota` | `INT` | 名额（0 表示不限） |
| `signed_count` | `INT` | 已报名人数 |
| `status` | `VARCHAR(16)` | 状态：报名中/已满/已结束 |
| `created_at` | `DATETIME` | 创建时间 |
| `updated_at` | `DATETIME` | 更新时间 |

### `event_signup`

**功能：** 保存客户报名信息，并通过活动ID关联讲座活动。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `id` | `BIGINT` | 主键，自增 |
| `event_id` | `BIGINT` | 活动ID |
| `customer_name` | `VARCHAR(64)` | 客户姓名 |
| `customer_phone` | `VARCHAR(32)` | 客户手机号 |
| `customer_info` | `JSON` | 客户扩展信息（意向国家、学历等） |
| `signup_time` | `DATETIME` | 报名时间 |
| `source` | `VARCHAR(32)` | 来源渠道 |
| `status` | `VARCHAR(16)` | 状态：有效/取消 |
| `created_at` | `DATETIME` | 创建时间 |

### `faq`

**功能：** 保存客服常见问题及标准答案，供FAQ快速检索。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `id` | `BIGINT` | 主键，自增 |
| `question` | `TEXT` | 问题 |
| `answer` | `TEXT` | 答案 |
| `category` | `VARCHAR(32)` | 分类 |
| `created_at` | `DATETIME` | 创建时间 |

### `chat_session`

**功能：** 保存客服对话会话的标识、访客和渠道信息。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `id` | `BIGINT` | 主键，自增 |
| `session_id` | `VARCHAR(64)` | 会话唯一标识（UUID） |
| `user_id` | `VARCHAR(64)` | 访客标识（匿名或留资后） |
| `channel` | `VARCHAR(32)` | 渠道（web 等） |
| `created_at` | `DATETIME` | 创建时间 |
| `updated_at` | `DATETIME` | 更新时间 |

### `chat_message`

**功能：** 保存会话中的用户/助手消息及意图标签。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `id` | `BIGINT` | 主键，自增 |
| `session_id` | `VARCHAR(64)` | 关联会话（FK → chat_session.session_id） |
| `role` | `VARCHAR(16)` | user / assistant |
| `intent` | `VARCHAR(32)` | 意图标签（由 Dify 返回） |
| `content` | `TEXT` | 消息内容 |
| `created_at` | `DATETIME` | 创建时间 |

### `student_admin_service`

**功能：** 保存学生请假或学业行政申请、审批状态及审批意见。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `id` | `BIGINT` | 主键 |
| `student_id` | `BIGINT` | 统一学生ID |
| `apply_type` | `VARCHAR(20)` | 申请类型 leave/academic |
| `apply_content` | `TEXT` | 申请理由/内容 |
| `approval_status` | `VARCHAR(20)` | 审批状态 pending/approved/rejected/cancelled |
| `edu_related_data` | `JSON` | 考务关联扩展信息 |
| `leave_start_at` | `DATETIME(6)` | 请假开始时间（UTC） |
| `leave_end_at` | `DATETIME(6)` | 请假结束时间（UTC） |
| `reviewer_id` | `BIGINT` | 指定/实际审批老师ID |
| `reviewed_at` | `DATETIME(6)` | 审批发生时间（UTC） |
| `approval_comment` | `TEXT` | 审批意见/驳回原因 |
| `request_key` | `VARCHAR(64)` | 请求幂等键 |
| `request_hash` | `CHAR(64)` | 规范化请求SHA-256 |
| `version` | `INT` | 乐观锁版本 |
| `created_at` | `DATETIME(6)` | 创建时间（UTC） |
| `updated_at` | `DATETIME(6)` | 最后更新时间（UTC） |

### `mental_health_profile`

**功能：** 保存学生每次心理状态评估、情绪分值、风险级别和来源信息。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `id` | `BIGINT` | 主键 |
| `student_id` | `BIGINT` | 统一学生ID |
| `emotion_tag` | `VARCHAR(50)` | 情绪标签 |
| `emotion_score` | `DECIMAL(5` | 情绪分值0～100，越高表示状态越平稳 |
| `history_data` | `JSON` | 旧历史JSON兼容字段 |
| `risk_level` | `VARCHAR(20)` | 本次风险 low/medium/high/critical |
| `observed_at` | `DATETIME(6)` | 被评估消息发生时间（UTC） |
| `source_event_id` | `VARCHAR(128)` | 本次源消息/事件ID |
| `workflow_run_id` | `VARCHAR(128)` | Dify工作流运行ID |
| `analysis_version` | `VARCHAR(64)` | 心理分析配置版本 |
| `created_at` | `DATETIME(6)` | 创建时间（UTC） |

### `mental_warning`

**功能：** 保存高风险心理预警及老师接手、处置和关闭信息。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `id` | `BIGINT` | 主键 |
| `student_id` | `BIGINT` | 统一学生ID |
| `profile_id` | `BIGINT` | 触发预警的评估ID |
| `trigger_reason` | `TEXT` | 必要的预警原因 |
| `risk_level` | `VARCHAR(20)` | 预警风险 high/critical |
| `follower_status` | `VARCHAR(20)` | 人工跟进状态 pending/processing/closed |
| `follower_id` | `BIGINT` | 负责老师统一员工ID |
| `acknowledged_at` | `DATETIME(6)` | 老师确认接手时间（UTC） |
| `closed_at` | `DATETIME(6)` | 人工关闭时间（UTC） |
| `handling_result` | `TEXT` | 人工处置结果 |
| `version` | `INT` | 乐观锁版本 |
| `created_at` | `DATETIME(6)` | 创建时间（UTC） |
| `updated_at` | `DATETIME(6)` | 最后更新时间（UTC） |

### `student_academic_event`

**功能：** 保存从教务系统同步的考试、论文DDL等学业节点。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `id` | `BIGINT` | 主键 |
| `student_id` | `BIGINT` | 统一学生ID |
| `source_system` | `VARCHAR(32)` | 教务来源编码 |
| `external_event_id` | `VARCHAR(128)` | 外部节点ID |
| `event_type` | `VARCHAR(20)` | ddl/exam |
| `title` | `VARCHAR(200)` | 论文/考试标题 |
| `due_at` | `DATETIME(6)` | 节点时间（UTC） |
| `source_timezone` | `VARCHAR(64)` | 来源IANA时区 |
| `event_status` | `VARCHAR(20)` | active/cancelled |
| `event_version` | `INT` | 影响提醒的节点版本 |
| `source_updated_at` | `DATETIME(6)` | 源系统更新时间（UTC） |
| `synced_at` | `DATETIME(6)` | 最后成功同步时间（UTC） |
| `created_at` | `DATETIME(6)` | 创建时间（UTC） |
| `updated_at` | `DATETIME(6)` | 最后更新时间（UTC） |

### `student_academic_reminder`

**功能：** 保存学业节点的提醒时间、提前量及投递状态。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `id` | `BIGINT` | 主键 |
| `student_id` | `BIGINT` | 统一学生ID |
| `academic_event_id` | `BIGINT` | 对应学业节点ID |
| `lead_minutes` | `INT` | 提前分钟数 |
| `notify_at` | `DATETIME(6)` | 计划提醒时点（UTC） |
| `event_version` | `INT` | 对应节点版本 |
| `status` | `VARCHAR(20)` | pending/queued/sent/cancelled |
| `sent_at` | `DATETIME(6)` | 当前版本成功通知时间（UTC） |
| `created_at` | `DATETIME(6)` | 创建时间（UTC） |
| `updated_at` | `DATETIME(6)` | 最后更新时间（UTC） |

### `student_application_progress`

**功能：** 保存CRM/申请系统中的留学申请阶段最新进度。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `id` | `BIGINT` | 主键 |
| `student_id` | `BIGINT` | 统一学生ID |
| `source_system` | `VARCHAR(32)` | CRM/申请系统来源 |
| `external_application_id` | `VARCHAR(128)` | 外部申请单ID |
| `application_name` | `VARCHAR(200)` | 申请院校/项目展示名 |
| `stage_code` | `VARCHAR(32)` | document_review/school_application/visa_process |
| `stage_status` | `VARCHAR(64)` | 源系统映射后的阶段状态 |
| `detail` | `VARCHAR(500)` | 必要进度说明 |
| `source_updated_at` | `DATETIME(6)` | 源系统更新时间（UTC） |
| `synced_at` | `DATETIME(6)` | 最后成功同步时间（UTC） |
| `created_at` | `DATETIME(6)` | 创建时间（UTC） |
| `updated_at` | `DATETIME(6)` | 最后更新时间（UTC） |

### `student_notification`

**功能：** 保存学生服务相关通知任务、接收人及投递重试状态。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `id` | `BIGINT` | 主键 |
| `student_id` | `BIGINT` | 统一学生ID |
| `business_type` | `VARCHAR(32)` | 关联业务类型 |
| `business_id` | `BIGINT` | 关联业务记录ID |
| `event_key` | `VARCHAR(128)` | 通知事件稳定去重键 |
| `recipient_type` | `VARCHAR(20)` | student/employee |
| `recipient_id` | `BIGINT` | 统一收件人ID |
| `channel` | `VARCHAR(20)` | in_app/enterprise |
| `content` | `VARCHAR(500)` | 最小必要通知内容 |
| `status` | `VARCHAR(20)` | pending/processing/sent/failed/cancelled |
| `attempts` | `INT` | 尝试次数 |
| `next_retry_at` | `DATETIME(6)` | 下次可尝试时间（UTC） |
| `locked_until` | `DATETIME(6)` | 处理租约截止（UTC） |
| `provider_message_id` | `VARCHAR(128)` | 外部渠道回执ID |
| `last_error` | `VARCHAR(500)` | 脱敏失败摘要 |
| `sent_at` | `DATETIME(6)` | 实际投递成功时间（UTC） |
| `read_at` | `DATETIME(6)` | 收件人阅读时间（UTC） |
| `created_at` | `DATETIME(6)` | 创建时间（UTC） |
| `updated_at` | `DATETIME(6)` | 最后更新时间（UTC） |

### `student_service_action`

**功能：** 记录学生行政、心理预警和工单的创建、审批、跟进等动作。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `id` | `BIGINT` | 主键 |
| `student_id` | `BIGINT` | 统一学生ID |
| `business_type` | `VARCHAR(32)` | administration/mental_warning/ticket |
| `business_id` | `BIGINT` | 关联主记录ID |
| `action_type` | `VARCHAR(32)` | 动作 create/approve/reject/cancel/assign/follow/close/rate |
| `from_status` | `VARCHAR(20)` | 动作前状态 |
| `to_status` | `VARCHAR(20)` | 动作后状态 |
| `operator_type` | `VARCHAR(20)` | student/employee/system |
| `operator_id` | `BIGINT` | 统一操作者ID |
| `note` | `TEXT` | 必要操作说明/人工跟进备注 |
| `event_key` | `VARCHAR(128)` | 操作事件幂等键 |
| `trace_id` | `VARCHAR(64)` | 日志链路ID |
| `created_at` | `DATETIME(6)` | 创建时间（UTC） |

### `org_department`

**功能：** 保存部门层级、职责、主管及部门状态。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `department_id` | `BIGINT` | 部门记录主键 ID，供员工、客户、学生及部门层级引用。 主键（PK）。 |
| `department_code` | `VARCHAR(32)` | 部门唯一业务编码。 |
| `department_name` | `VARCHAR(100)` | 部门名称。 |
| `parent_department_id` | `BIGINT` | 上级部门 ID，关联本表；顶级部门为空。 外键（FK）关联 org_department.department_id。 |
| `function_description` | `TEXT` | 部门职能与职责说明。 |
| `employee_id` | `BIGINT` | 部门主管员工 ID，关联 employee。 外键（FK）关联 employee.employee_id。 |
| `status` | `VARCHAR(20)` | 部门状态：active 启用、disabled 停用。 |
| `created_at` | `DATETIME(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | `DATETIME(3)` | 记录最近更新时间，UTC |
| `row_version` | `INT` | 并发版本号；每次业务修改由硬编码后端递增 |

### `employee`

**功能：** 保存员工身份、任职、部门和账号状态等主数据。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `employee_id` | `BIGINT` | 员工主键 ID，是所有员工业务关联的内部标识，不使用工号代替。 主键（PK）。 |
| `employee_no` | `VARCHAR(32)` | 员工唯一工号。 |
| `full_name` | `VARCHAR(100)` | 员工姓名，允许重名。 |
| `department_id` | `BIGINT` | 当前主部门 ID，关联 org_department。 外键（FK）关联 org_department.department_id。 |
| `position_title` | `VARCHAR(100)` | 员工岗位或职务名称。 |
| `login_provider` | `VARCHAR(32)` | 登录来源，如企业统一登录。 |
| `login_subject` | `VARCHAR(128)` | 登录来源提供的不可变账号标识。 |
| `role_codes` | `JSON` | 受控角色代码数组；权限由后端固定配置解释。 |
| `work_phone_ciphertext` | `VARBINARY(512)` | 加密保存的工作联系电话。 |
| `work_email` | `VARCHAR(254)` | 工作邮箱。 |
| `status` | `VARCHAR(20)` | 员工状态：active 启用、disabled 停用、left 离职。 |
| `joined_date` | `DATE` | 入职日期。 |
| `left_date` | `DATE` | 离职日期，未离职时为空。 |
| `external_employee_id` | `VARCHAR(128)` | 权威通讯录中的员工 ID。 |
| `created_at` | `DATETIME(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | `DATETIME(3)` | 记录最近更新时间，UTC |
| `row_version` | `INT` | 并发版本号；每次业务修改由硬编码后端递增 |

### `customer_profile`

**功能：** 保存意向客户主档、画像、来源、销售状态及归属信息。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `customer_id` | `BIGINT` | 客户主键 ID，是跟进记录及关联学生使用的内部标识。 主键（PK）。 |
| `customer_no` | `VARCHAR(32)` | 客户唯一业务编号。 |
| `full_name` | `VARCHAR(100)` | 客户姓名，不作为唯一身份依据。 |
| `phone_ciphertext` | `VARBINARY(512)` | 加密保存的客户手机号。 |
| `phone_lookup_token` | `CHAR(64)` | 标准化手机号的带密钥匹配标记，用于提示重复候选。 |
| `education_level` | `VARCHAR(32)` | 客户学历层次。 |
| `target_country_code` | `VARCHAR(8)` | 意向留学国家编码。 |
| `source_channel` | `VARCHAR(32)` | 客户来源，如人工、客服留资或 CRM。 |
| `source_reference` | `VARCHAR(128)` | 来源留资或研判任务引用。 |
| `employee_id` | `BIGINT` | 当前顾问员工 ID，未分派时为空。 外键（FK）关联 employee.employee_id。 |
| `department_id` | `BIGINT` | 当前客户管理部门 ID。 外键（FK）关联 org_department.department_id。 |
| `status` | `VARCHAR(20)` | 客户状态：new、contacting、qualified、signed、lost。 |
| `status_changed_at` | `DATETIME(3)` | 当前客户状态开始生效的时间。 |
| `lost_reason` | `TEXT` | 流失原因，状态变为 lost 时必须填写。 |
| `last_followup_at` | `DATETIME(3)` | 最近一次有效跟进时间，由业务服务维护。 |
| `authority_source` | `VARCHAR(20)` | 数据权威来源：local 本平台、crm 外部 CRM。 |
| `external_customer_id` | `VARCHAR(128)` | CRM 中的客户 ID。 |
| `external_updated_at` | `DATETIME(3)` | 最近确认的外部客户更新时间。 |
| `is_archived` | `BOOLEAN` | 是否已归档，默认 false；保留销售状态和历史，归档后不进入默认客户列表。 |
| `created_at` | `DATETIME(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | `DATETIME(3)` | 记录最近更新时间，UTC |
| `row_version` | `INT` | 并发版本号；每次业务修改由硬编码后端递增 |

### `customer_followup`

**功能：** 保存客户每次沟通跟进、结果及后续跟进计划。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `followup_id` | `BIGINT` | 客户跟进记录主键 ID。 主键（PK）。 |
| `customer_id` | `BIGINT` | 本记录所属客户 ID。 外键（FK）关联 customer_profile.customer_id。 |
| `employee_id` | `BIGINT` | 实际执行跟进的员工 ID。 外键（FK）关联 employee.employee_id。 |
| `followup_at` | `DATETIME(3)` | 客户沟通实际发生时间。 |
| `channel` | `VARCHAR(32)` | 跟进方式，如电话、面谈或线上沟通。 |
| `content` | `TEXT` | 完整跟进内容。 |
| `summary` | `TEXT` | 经员工确认的跟进摘要。 |
| `next_followup_at` | `DATETIME(3)` | 计划下一次跟进的时间。 |
| `followup_status` | `VARCHAR(20)` | 下一次跟进安排状态：none 未安排、pending 待跟进、done 已完成、cancelled 已取消。 |
| `created_at` | `DATETIME(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | `DATETIME(3)` | 记录最近更新时间，UTC |
| `row_version` | `INT` | 并发版本号；每次业务修改由硬编码后端递增 |

### `employee_daily_report`

**功能：** 保存员工按工作日提交的日报内容及修订/提交信息。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `daily_report_id` | `BIGINT` | 员工日报记录主键 ID。 主键（PK）。 |
| `employee_id` | `BIGINT` | 日报所属员工 ID。 外键（FK）关联 employee.employee_id。 |
| `report_date` | `DATE` | 日报对应机构工作日日期。 |
| `department_id_at_submit` | `BIGINT` | 最近提交时的部门快照。 外键（FK）关联 org_department.department_id。 |
| `submitted_content` | `TEXT` | 最近一次员工确认提交的正式内容，必须填写。 |
| `ai_summary` | `TEXT` | 与最近提交内容对应的辅助摘要。 |
| `status` | `VARCHAR(20)` | 日报状态：submitted 已提交、void 已作废。 |
| `submitted_at` | `DATETIME(3)` | 最近正式提交时间。 |
| `created_at` | `DATETIME(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | `DATETIME(3)` | 记录最近更新时间，UTC |
| `row_version` | `INT` | 并发版本号；每次业务修改由硬编码后端递增 |

### `student_profile`

**功能：** 学生唯一主档，关联客户、部门、登录身份及教务/CRM标识。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `student_id` | `BIGINT` | 学生主键 ID，是成绩、请假、投诉及学生员工关系使用的内部标识。 主键（PK）。 |
| `student_no` | `VARCHAR(32)` | 学生唯一业务编号。 |
| `full_name` | `VARCHAR(100)` | 学生姓名，允许重名。 |
| `customer_id` | `BIGINT` | 关联客户 ID，不自动授予客户账号访问学生数据的权限。 外键（FK）关联 customer_profile.customer_id。 |
| `department_id` | `BIGINT` | 学生教务或服务归属部门 ID。 外键（FK）关联 org_department.department_id。 |
| `login_provider` | `VARCHAR(32)` | 学生登录来源，尚未开通账号时为空。 |
| `login_subject` | `VARCHAR(128)` | 学生登录身份键，与登录来源同时填写。 |
| `status` | `VARCHAR(20)` | 学生服务或在读状态。 |
| `external_student_id` | `VARCHAR(128)` | 教务系统中的学生 ID。 |
| `is_archived` | `BOOLEAN` | 是否已归档，默认 false；归档不删除已有成绩、请假和投诉关联。 |
| `created_at` | `DATETIME(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | `DATETIME(3)` | 记录最近更新时间，UTC |
| `row_version` | `INT` | 并发版本号；每次业务修改由硬编码后端递增 |

### `student_staff_binding`

**功能：** 维护学生与班主任、成绩人员、服务顾问等员工关系及有效期。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `binding_id` | `BIGINT` | 学生员工关系记录主键 ID。 主键（PK）。 |
| `student_id` | `BIGINT` | 被服务或管理的学生 ID。 外键（FK）关联 student_profile.student_id。 |
| `employee_id` | `BIGINT` | 承担对应职责的员工 ID。 外键（FK）关联 employee.employee_id。 |
| `relation_type` | `VARCHAR(32)` | 关系类型：class_teacher 班主任、score_editor 成绩人员、service_advisor 服务顾问。 |
| `course_scope_code` | `VARCHAR(64)` | 成绩权限限定的课程编码，空值需角色允许相应课程范围。 |
| `is_primary` | `BOOLEAN` | 是否为此业务关系的主要负责人。 |
| `valid_from` | `DATETIME(3)` | 关系开始生效时间。 |
| `valid_to` | `DATETIME(3)` | 关系失效时间，临时代理需要截止时间。 |
| `status` | `VARCHAR(20)` | 关系状态：active 有效、disabled 停用。 |
| `created_at` | `DATETIME(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | `DATETIME(3)` | 记录最近更新时间，UTC |
| `row_version` | `INT` | 并发版本号；每次业务修改由硬编码后端递增 |

### `student_score`

**功能：** 保存学生课程、学期、考核项目及成绩记录。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `score_id` | `BIGINT` | 学生成绩记录主键 ID。 主键（PK）。 |
| `student_id` | `BIGINT` | 成绩所属学生 ID。 外键（FK）关联 student_profile.student_id。 |
| `course_code` | `VARCHAR(64)` | 受控课程编码。 |
| `term_code` | `VARCHAR(32)` | 学期编码。 |
| `assessment_code` | `VARCHAR(64)` | 考试、作业或其他考核项目编码。 |
| `attempt_no` | `INT` | 考核尝试次数，首次为 1，补考递增。 |
| `score_value` | `DECIMAL(8` | 学生实际得分，统一采用数值制，必须填写。 |
| `max_score` | `DECIMAL(8` | 本次考核满分，必须填写且大于零。 |
| `employee_id` | `BIGINT` | 最近录入或更正成绩的员工 ID。 外键（FK）关联 employee.employee_id。 |
| `status` | `VARCHAR(20)` | 成绩状态：valid 有效、void 作废。 |
| `created_at` | `DATETIME(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | `DATETIME(3)` | 记录最近更新时间，UTC |
| `row_version` | `INT` | 并发版本号；每次业务修改由硬编码后端递增 |

### `service_ticket`

**功能：** 保存投诉或建议工单主信息、分类、负责人、时限、状态和解决结果。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `ticket_id` | `BIGINT` | 投诉反馈工单主键 ID，供处理记录引用。 主键（PK）。 |
| `ticket_no` | `VARCHAR(32)` | 统一工单业务编号。 |
| `student_id` | `BIGINT` | 投诉或反馈对应学生 ID。 外键（FK）关联 student_profile.student_id。 |
| `ticket_type` | `VARCHAR(20)` | complaint 投诉或 suggestion 建议。 |
| `category_code` | `VARCHAR(32)` | 申请、签证、教学等受控分类编码。 |
| `content` | `TEXT` | 学生提交的原始内容。 |
| `ai_summary` | `TEXT` | 辅助摘要，不覆盖学生原文。 |
| `priority` | `VARCHAR(20)` | 处理优先级。 |
| `employee_id` | `BIGINT` | 当前处理员工 ID，未分派时为空。 外键（FK）关联 employee.employee_id。 |
| `handling_department_id` | `BIGINT` | 当前处理部门 ID。 外键（FK）关联 org_department.department_id。 |
| `status` | `VARCHAR(32)` | 工单状态：open 待分派、assigned 已分派、processing 处理中、awaiting_student 待学生确认、closed 已关闭、reopened 已重开。 |
| `first_response_at` | `DATETIME(3)` | 首次有效人工回应时间，自动回执不计入。 |
| `response_due_at` | `DATETIME(3)` | 首次回应截止时间。 |
| `resolution_due_at` | `DATETIME(3)` | 当前轮次解决截止时间。 |
| `solution` | `TEXT` | 当前解决方案，进入待学生确认状态时必填。 |
| `resolved_at` | `DATETIME(3)` | 最近给出解决方案的时间。 |
| `closed_at` | `DATETIME(3)` | 当前有效关闭时间。 |
| `reopen_count` | `INT` | 重新打开次数，默认 0。 |
| `satisfaction_score` | `TINYINT` | 学生实际评价分数，建议 1—5。 |
| `created_at` | `DATETIME(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | `DATETIME(3)` | 记录最近更新时间，UTC |
| `row_version` | `INT` | 并发版本号；每次业务修改由硬编码后端递增 |

### `service_ticket_record`

**功能：** 保存工单的分派、沟通、处理、确认、重开等历史记录。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `ticket_record_id` | `BIGINT` | 投诉处理记录主键 ID。 主键（PK）。 |
| `ticket_id` | `BIGINT` | 本条业务记录所属工单 ID。 外键（FK）关联 service_ticket.ticket_id。 |
| `record_type` | `VARCHAR(32)` | 记录类型：分派、人工回应、备注、解决、确认、重开或升级。 |
| `employee_id` | `BIGINT` | 操作员工 ID，外键关联 employee.employee_id；员工操作时填写。 |
| `student_id` | `BIGINT` | 操作学生 ID，外键关联 student_profile.student_id；学生反馈时填写。 |
| `service_code` | `VARCHAR(64)` | 自动处理的受控服务编码；系统操作时填写，不作为员工或学生 ID。 |
| `content` | `TEXT` | 本次沟通、反馈或处理说明。 |
| `visibility` | `VARCHAR(20)` | internal 内部可见或 student_visible 学生可见。 |
| `to_status` | `VARCHAR(32)` | 本次处理后工单状态。 |
| `cycle_no` | `INT` | 当前处理轮次，初次为 1，重开后递增。 |
| `record_key` | `VARCHAR(160)` | 唯一业务记录去重键。 |
| `created_at` | `DATETIME(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |

### `knowledge_entry`

**功能：** 管理员工新人指南、FAQ及制度文档内容、审核发布和外部索引状态。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `knowledge_id` | `BIGINT` | 知识条目主键 ID。 主键（PK）。 |
| `entry_code` | `VARCHAR(64)` | 知识条目唯一编码。 |
| `title` | `VARCHAR(200)` | 知识标题。 |
| `entry_type` | `VARCHAR(20)` | faq 标准问答或 document 制度文档。 |
| `category_code` | `VARCHAR(32)` | 入职、制度或业务流程等分类编码。 |
| `question` | `TEXT` | FAQ 标准问题，faq 时必填。 |
| `answer` | `TEXT` | FAQ 标准答案，faq 时必填。 |
| `content_text` | `LONGTEXT` | 文档正文，document 时应有正文或受控来源。 |
| `source_reference` | `VARCHAR(512)` | 原文件、章节或受控资料来源定位。 |
| `employee_id` | `BIGINT` | 知识维护员工 ID。 外键（FK）关联 employee.employee_id。 |
| `access_department_id` | `BIGINT` | 限定访问部门；为空表示全体员工可见。 外键（FK）关联 org_department.department_id。 |
| `version_no` | `INT` | 当前内容版本号，内容变更时递增。 |
| `status` | `VARCHAR(20)` | draft 草稿、published 已发布、disabled 停用。 |
| `reviewer_employee_id` | `BIGINT` | 审核该版本的员工 ID。 外键（FK）关联 employee.employee_id。 |
| `reviewed_at` | `DATETIME(3)` | 审核完成时间。 |
| `effective_from` | `DATETIME(3)` | 已发布知识开始生效的时间。 |
| `expires_at` | `DATETIME(3)` | 知识失效时间。 |
| `index_status` | `VARCHAR(20)` | 索引状态：pending 待更新、ready 可检索、failed 失败。 |
| `external_document_id` | `VARCHAR(128)` | Dify 或外部索引中的文档 ID。 |
| `created_at` | `DATETIME(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | `DATETIME(3)` | 记录最近更新时间，UTC |
| `row_version` | `INT` | 并发版本号；每次业务修改由硬编码后端递增 |

### `business_notification`

**功能：** 保存员工/学生业务通知、去重、投递、重试及已读状态。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `notification_id` | `BIGINT` | 业务通知记录主键 ID。 主键（PK）。 |
| `entity_type` | `VARCHAR(32)` | 关联业务实体类型，如请假、投诉或跟进。 |
| `entity_id` | `BIGINT` | 关联业务记录 ID，由业务服务按实体类型校验。 |
| `event_code` | `VARCHAR(64)` | 业务通知原因，如待审批、审批结果或投诉解决。 |
| `employee_id` | `BIGINT` | 员工接收人 ID，与学生接收人二选一。 外键（FK）关联 employee.employee_id。 |
| `student_id` | `BIGINT` | 学生接收人 ID，与员工接收人二选一。 外键（FK）关联 student_profile.student_id。 |
| `channel` | `VARCHAR(20)` | 投递渠道，如站内或企业消息。 |
| `title` | `VARCHAR(200)` | 通知标题，只包含必要信息。 |
| `content` | `TEXT` | 通知内容，不包含敏感业务原文。 |
| `dedupe_key` | `VARCHAR(160)` | 包含业务事件、轮次、接收人及渠道的唯一通知键。 |
| `delivery_status` | `VARCHAR(20)` | pending 待发送、sending 发送中、sent 已发送、failed 失败、dead_letter 终止重试。 |
| `attempt_count` | `INT` | 已尝试发送次数，初值 0。 |
| `next_retry_at` | `DATETIME(3)` | 下一次允许重试时间。 |
| `lease_until` | `DATETIME(3)` | 发送任务租约截止时间，用于恢复中断任务。 |
| `sent_at` | `DATETIME(3)` | 对应渠道确认接收消息的时间。 |
| `read_at` | `DATETIME(3)` | 真实已读时间，不支持回执时为空。 |
| `last_error_code` | `VARCHAR(64)` | 最近一次发送失败的脱敏错误码。 |
| `created_at` | `DATETIME(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | `DATETIME(3)` | 记录最近更新时间，UTC |
| `row_version` | `INT` | 并发版本号；每次业务修改由硬编码后端递增 |

### `operation_log`

**功能：** 记录受控业务操作的操作者、请求幂等信息、前后快照和执行结果。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `operation_log_id` | `BIGINT` | 业务操作记录主键 ID。 主键（PK）。 |
| `operation_key` | `CHAR(64)` | 操作唯一键，由真实操作者、动作和请求幂等键确定，与新建对象 ID 无关。 |
| `employee_id` | `BIGINT` | 真实操作员工 ID，外键关联 employee.employee_id。 |
| `student_id` | `BIGINT` | 真实操作学生 ID，外键关联 student_profile.student_id。 |
| `service_code` | `VARCHAR(64)` | 执行自动操作的受控服务编码，不伪装成员工或学生身份。 |
| `action_code` | `VARCHAR(64)` | 预先定义的业务动作编码。 |
| `entity_type` | `VARCHAR(32)` | 被操作业务实体类型。 |
| `entity_id` | `BIGINT` | 关联对象 ID，新建未完成或失败时可为空。 |
| `request_key` | `VARCHAR(128)` | 逻辑业务请求幂等键，同一提交重试保持不变。 |
| `parameters_hash` | `CHAR(64)` | 规范化业务参数摘要，用于识别相同幂等键下的参数冲突。 |
| `before_data` | `JSON` | 变更前必要业务快照，敏感字段按规则保护。 |
| `after_data` | `JSON` | 变更后必要业务快照，保留审批及修订结果。 |
| `change_reason` | `TEXT` | 人工更正、移交、驳回、删除等业务原因。 |
| `operation_status` | `VARCHAR(32)` | 操作状态：processing 处理中、succeeded 成功、failed 失败、pending_external 等待外部结果、unknown_external 外部结果待核实。 |
| `result_reference` | `JSON` | 受控操作回执和对象标识，用于重复请求返回原结果。 |
| `external_request_id` | `VARCHAR(128)` | 外部系统请求标识，用于查询写回结果和对账。 |
| `error_code` | `VARCHAR(64)` | 操作失败、冲突或待核实的脱敏错误码。 |
| `finished_at` | `DATETIME(3)` | 操作形成明确成功或失败结果的时间。 |
| `created_at` | `DATETIME(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | `DATETIME(3)` | 记录最近更新时间，UTC |
| `row_version` | `INT` | 并发版本号；每次业务修改由硬编码后端递增 |

### `report_config`

**功能：** 配置报告类型、周期、定时计划和启停状态。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `id` | `BIGINT` | 主键 |
| `report_code` | `VARCHAR(64)` | 报告代码：customer_overview/daily_report/weekly_report/mental_weekly/complaint_weekly |
| `report_name` | `VARCHAR(128)` | 报告名称 |
| `report_period` | `VARCHAR(16)` | 报告周期：day/week/month |
| `cron_expr` | `VARCHAR(64)` | 定时表达式（cron，按东八区） |
| `enabled` | `TINYINT(1)` | 是否启用：1启用 0停用 |
| `created_at` | `DATETIME` | 创建时间 |
| `updated_at` | `DATETIME` | 更新时间 |

### `report_record`

**功能：** 保存报告生成任务、统计时间窗、报告正文、数据快照及运行状态。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `id` | `BIGINT` | 主键 |
| `report_config_id` | `BIGINT` | 报告配置ID |
| `report_code` | `VARCHAR(64)` | 报告代码 |
| `idempotency_key` | `VARCHAR(128)` | 幂等键：report_code+时间窗+版本 |
| `start_time` | `DATETIME` | 统计起始时间（UTC） |
| `end_time` | `DATETIME` | 统计截止时间（UTC） |
| `timezone` | `VARCHAR(32)` | 统计时区 |
| `data_snapshot_at` | `DATETIME` | 数据快照时间 |
| `version` | `VARCHAR(32)` | 生成版本 |
| `source_record_count` | `INT` | 来源记录数 |
| `report_content` | `LONGTEXT` | 报告正文（结构化文本） |
| `metric_json` | `JSON` | 可复算指标快照（JSON） |
| `status` | `VARCHAR(16)` | 状态：pending/running/success/failed |
| `fail_reason` | `TEXT` | 失败原因 |
| `generated_at` | `DATETIME` | 生成完成时间 |
| `created_at` | `DATETIME` | 创建时间 |

### `report_metric`

**功能：** 保存报告中的结构化指标数值、文本、单位和计算口径。

| 字段名 | 类型 | 说明 |
|---|---|---|
| `id` | `BIGINT` | 主键 |
| `report_record_id` | `BIGINT` | 报告记录ID |
| `metric_code` | `VARCHAR(64)` | 指标代码 |
| `metric_name` | `VARCHAR(128)` | 指标名称 |
| `metric_value` | `DECIMAL(20` | 指标数值（数值型） |
| `metric_text` | `TEXT` | 指标文本值（非数值型） |
| `metric_unit` | `VARCHAR(32)` | 单位 |
| `calc_rule` | `TEXT` | 计算口径/规则说明 |
| `period_type` | `VARCHAR(16)` | 周期类型：day/week/month |
| `created_at` | `DATETIME` | 创建时间 |








