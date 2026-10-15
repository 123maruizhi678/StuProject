# 学生智能助手 API V3

日期：2026-10-15。精确请求模型、字段限制和接口操作见同目录学生助手_OpenAPI.json，运行后也可访问/docs。

## 身份和响应

通过Authorization: Bearer <签名Token>认证；Swagger右上角Authorize输入Token。学生身份不可由请求体student_id指定。老师仅有当前有效角色和对应班主任关系时访问请假/心理预警协作接口。同步接口要求service身份且含student:sync权限。

沿用小组现状，HTTP 200携带{code,message,data}：0成功，400参数错误，401登录失败，403无权限，404记录不存在，409重复键内容冲突/状态冲突/版本冲突，503依赖未配置或不可用。此约定仅在学生路由适配，不修改其他组员异常处理。

除对话确认外的写入接口要求Idempotency-Key（8至128位可见ASCII）；相同身份、动作和键的相同参数返回原回执，不同参数返回409。confirm:前缀由后端对话确认保留。对话确认使用签名预览jti去重，更换HTTP请求不能重复办理同一预览。

请假审批/撤回、工单补充/确认/评价、预警处置需要expected_version。状态和ID由真实数据库返回，不能猜测。

## 接口清单

| 方法 | 路径 | 操作 |
|---|---|---|
| POST | /api/v1/student/leave | Submit Leave |
| GET | /api/v1/student/leave | List Leave |
| DELETE | /api/v1/student/leave/{apply_id} | Withdraw Leave |
| GET | /api/v1/student/leave/{apply_id} | Get Leave |
| POST | /api/v1/student/complaint | Submit Ticket |
| POST | /api/v1/student/tickets/{ticket_id}/reply | Reply Ticket |
| POST | /api/v1/student/tickets/{ticket_id}/confirm | Confirm Ticket |
| POST | /api/v1/student/tickets/{ticket_id}/rating | Rate Ticket |
| POST | /api/v1/student/mental/monitor | Mental Monitor |
| POST | /api/v1/student/reminders | Set Reminder |
| GET | /api/v1/student/reminders | Get Reminders |
| DELETE | /api/v1/student/reminders/{reminder_id} | Cancel Reminder |
| POST | /api/v1/student/notifications/{notification_id}/read | Read Notification |
| POST | /api/v1/student/chat | Student Chat |
| POST | /api/v1/student/actions/confirm | Confirm Action |
| GET | /api/v1/student/tickets | List Tickets |
| GET | /api/v1/student/tickets/{ticket_id} | Get Ticket |
| GET | /api/v1/student/tickets/{ticket_id}/records | Ticket Records |
| GET | /api/v1/student/academic | Get Academic |
| GET | /api/v1/student/progress | Get Progress |
| GET | /api/v1/student/notifications | Get Notifications |
| GET | /api/v1/internal/student/leave | 当前老师的请假列表 |
| GET | /api/v1/internal/student/leave/{apply_id} | 请假详情 |
| POST | /api/v1/internal/student/leave/{apply_id}/decision | 请假批准/驳回 |
| GET | /api/v1/internal/student/notifications | 本人学生业务站内通知 |
| POST | /api/v1/internal/student/notifications/{notification_id}/read | 本人通知已读 |
| GET | /api/v1/internal/student/warnings | 授权心理预警列表 |
| GET | /api/v1/internal/student/warnings/{warning_id} | Warning Detail |
| POST | /api/v1/internal/student/warnings/{warning_id}/ack | Ack Warning |
| POST | /api/v1/internal/student/warnings/{warning_id}/follow | Follow Warning |
| POST | /api/v1/internal/student/warnings/{warning_id}/close | Close Warning |
| POST | /api/v1/internal/student/sync/academic | Sync Academic |
| POST | /api/v1/internal/student/sync/progress | Sync Progress |
| POST | /api/v1/internal/student/sync/{kind}/pull | Pull Source |

## 组长查询契约 student-v1

默认STUDENT_QUERY_BACKEND=group，配置STUDENT_NL2SQL_URL和独立服务Token。学生模块不生成/执行AI SQL，不回退到只接受question的旧函数。本机开发明确设置local模式，使用固定参数化只读SQL查询真实表，响应带query_backend=local_fixed_sql。

请求示例：
~~~json
{"contract_version":"student-v1","scenario":"academic","subject":{"type":"student","id":123},"filters":{"entity_id":null},"limit":20,"offset":0}
~~~
响应示例（123仅为占位，必须是真实登录学生ID）：
~~~json
{"code":0,"data":{"contract_version":"student-v1","scenario":"academic","subject_id":123,"total":0,"rows":[]}}
~~~

支持场景：leave、tickets、ticket_records、academic、progress、reminders、notifications；字段白名单以student_clients.py的QUERY_FIELDS为准。详情查询的filters.entity_id必须精确匹配申请/工单/提醒/消息ID。ticket_records场景中返回student_id必须是所属工单的学生ID，而不是处理记录作者ID；只返回student_visible记录。通知只返回本人已发送的in_app消息。学业/进度的synced_at必须为带时区ISO时间；后端计算stale。

老师预警详情使用mental_warning场景，subject.type=employee，filters含warning_id和student_id；后端先检查真实老师角色、负责关系和当前预警负责人，再调用组长查询服务。查询服务仍须再次执行权限过滤。

组长服务必须在执行前强制行权限、表/字段白名单、只读、分页和超时；返回后检查归属是第二道防线，不能取代执行前授权。不能靠给问题文本加“仅查询本人”保证隔离。

## 教务/CRM来源接口

教务GET地址接收并回显external_student_id，对应公共student_profile.external_student_id；CRM接收并回显crm_student_id，对应独立CRM身份。Authorization为各自服务Token。响应另含source_system、records。source_system仅ASCII字母/数字及_.:-。

学业记录：external_event_id、event_type(ddl/exam)、title、due_at(带时区)、source_timezone(IANA)、event_status(active/cancelled)、source_updated_at(带时区)。
进度记录：external_application_id、application_name、stage_code(document_review/school_application/visa_process)、stage_status、detail、source_updated_at。

同批次最多500条；数据缺失不推断为取消，来源必须显式传cancelled；旧来源时间不覆盖新记录，相同来源时间内容不同返回冲突。教务与CRM若使用不同学生ID，由真实适配器映射到同一内部学生ID，不按姓名匹配。

## 企业模块协作

[企业侧接口交接](学生助手_企业侧对接.md)包含13个已实现接口、请求示例、权限与状态流转。请假提交、撤回、企业审批共用student_leave_request与同一业务服务，审批结果事务内入队学生通知。企业只接自己的页面，无需重复更新或再发同一审批通知。

心理预警处置与通知查询也由这些受限接口提供。普通学生或通用员工日志接口不能读取心理处置备注。工单的企业分派/处理仍由企业负责人按共享表契约实现，不列虚构HTTP接口。
