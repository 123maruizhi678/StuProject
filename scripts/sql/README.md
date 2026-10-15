# 数据库建表脚本说明

本目录的 `all.sql按当前方案建表.sql` 是根据总需求、原始 `all.sql` 和已确认的重复模型处理方案整理的 MySQL 建表脚本。

## 当前模型选择

- 学生主档使用 `student_profile`。
- 学生请假/行政申请使用 `student_admin_service`。
- 投诉与建议工单使用 `service_ticket`，处理过程记录在 `service_ticket_record`。
- 原重复模型 `student_identity`、`student_leave_request`、`after_sales_ticket` 未纳入本脚本。
- `student_profile` 增加了 `crm_student_id` 字段及唯一索引，用于保留 CRM 学生标识。

## 环境要求

- MySQL 8.0.16 或更高版本（脚本使用 `CHECK` 约束）。
- 运行前先连接到目标数据库。脚本不会创建数据库/schema。
- 建议在空数据库中执行。脚本不包含旧数据迁移，也不删除已有表。

## 执行方式

在 MySQL 客户端中选定目标数据库后执行脚本。例如：

```sql
USE your_database_name;
SOURCE D:/path/to/all.sql按当前方案建表.sql;
```

也可以使用 MySQL Workbench、DBeaver 等客户端打开 SQL 文件，在目标数据库连接中执行。

## 表清单（30 张）

### 客服Agent

`course_project`、`lecture_event`、`event_signup`、`faq`、`chat_session`、`chat_message`

### 学生智能助手

`student_profile`、`student_admin_service`、`mental_health_profile`、`mental_warning`、`student_academic_event`、`student_academic_reminder`、`student_application_progress`、`student_notification`、`student_service_action`

### 企业智能助手与组织数据

`org_department`、`employee`、`customer_profile`、`customer_followup`、`employee_daily_report`、`student_staff_binding`、`student_score`、`service_ticket`、`service_ticket_record`、`knowledge_entry`、`business_notification`、`operation_log`

### 智能报告

`report_config`、`report_record`、`report_metric`

## 执行注意事项

1. 这是新建表脚本，不是升级/迁移脚本。由于使用普通 `CREATE TABLE` 和一次 `ALTER TABLE`，重复执行会因表或字段已存在而报错。
2. 脚本会在当前连接中暂时关闭外键检查，以处理表之间的依赖顺序，并在末尾重新开启。请完整执行；若中途失败，重新连接后再处理失败原因并重跑。
3. `student_profile` 是学生唯一主档。若从旧模型迁移数据，需将旧学生身份标识、请假记录和投诉工单迁入选定表，并更新应用及外部接口引用。本脚本本身不会迁移这些数据。
4. 请先确认 CRM/教务学生编号、责任老师关联、审批字段等业务映射后再导入数据。`crm_student_id` 可以为空，但非空值必须唯一。
5. 其他可选精简项（例如对话记录、报告指标、通知队列等）仍按需求文档保留在脚本中；如项目确定不实现相应功能，应先确认代码和数据依赖，再单独调整 DDL。

## 相关文件

- 建表脚本：`all.sql按当前方案建表.sql`
- 表分类及精简建议：`all.sql表分类与精简建议.md`
