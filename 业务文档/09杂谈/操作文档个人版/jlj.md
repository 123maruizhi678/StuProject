# 蒋立建个人操作文档

模块名字：学生智能助手  
负责人：蒋立建  
更新日期：2026-10-16  
系统目录：`D:\AI\StuProject`

本模块通过一个统一学生智能体提供请假、投诉建议、心理辅助关怀、学业提醒、申请进度、生活咨询及升学推荐，并与公共认证、企业老师端、教务、CRM 和通知任务对接。本文依据《学生助手_已提交功能与模块对接说明.md》，参照 mrz.md 的结构整理，不包含实现代码示例。

来源依据的功能提交版本为 0d8111b，后续 3194a27 仅撤回接口导出文档变更；目录比较基线为 7bec441。下文“已提交”“已验证”均转述来源文件，未重新核验远端、代码、数据库或真实外部服务。

## 一、模块功能以及对应的接口和对应的数据库表

一个统一 Workflow 承接七类业务，数据库操作、权限和通知由后端执行。共 21 个学生端业务方法、10 个老师协作方法和 3 个服务同步方法；公共登录不计入学生端方法数量。

### 1. 学生端 HTTP 功能接口

| 功能 | 接口 | 调用用户 / 认证要求 | 对应数据库表或资源 | 功能说明 |
| --- | --- | --- | --- | --- |
| 提交请假 | `POST /api/v1/student/leave` | 已登录学生，仅本人 | student_admin_service；读取 student_profile、student_staff_binding、employee | 提交本人申请；写审计和通知，老师负责审批 |
| 请假列表 | `GET /api/v1/student/leave` | 已登录学生，仅本人 | student_admin_service | 仅本人申请 |
| 请假详情 | `GET /api/v1/student/leave/{apply_id}` | 已登录学生，仅本人 | student_admin_service | 仅本人详情 |
| 撤回请假 | `DELETE /api/v1/student/leave/{apply_id}` | 已登录学生，仅本人 | student_admin_service、operation_log | 校验版本和状态后撤回 |
| 投诉或建议 | `POST /api/v1/student/complaint` | 已登录学生，仅本人 | service_ticket、service_ticket_record | 保存诉求及初始工单记录 |
| 本人工单列表 | `GET /api/v1/student/tickets` | 已登录学生，仅本人 | service_ticket | 仅本人 |
| 本人工单详情 | `GET /api/v1/student/tickets/{ticket_id}` | 已登录学生，仅本人 | service_ticket | 仅本人 |
| 工单沟通记录 | `GET /api/v1/student/tickets/{ticket_id}/records` | 已登录学生，仅本人 | service_ticket_record | 只返回 student_visible 记录 |
| 补充工单信息 | `POST /api/v1/student/tickets/{ticket_id}/reply` | 已登录学生，仅本人 | service_ticket、service_ticket_record | 追加沟通并更新版本 |
| 确认解决或重开 | `POST /api/v1/student/tickets/{ticket_id}/confirm` | 已登录学生，仅本人 | service_ticket、service_ticket_record | 依据 resolved 流转，未解决需说明原因 |
| 工单评价 | `POST /api/v1/student/tickets/{ticket_id}/rating` | 已登录学生，仅本人 | service_ticket、operation_log | 满意度 1—5，记录操作 |
| 心理辅助评估 | `POST /api/v1/student/mental/monitor` | 已登录学生，仅本人 | mental_health_profile、mental_warning | 输入 chat_content，复用唯一 Dify 应用；必要时写预警 |
| 查询学业节点 | `GET /api/v1/student/academic` | 已登录学生，仅本人 | student_academic_event | 展示本人考试及 DDL 镜像 |
| 设置提醒 | `POST /api/v1/student/reminders` | 已登录学生，仅本人 | student_academic_event、student_academic_reminder | 校验本人节点，新增或恢复提醒 |
| 查询提醒 | `GET /api/v1/student/reminders` | 已登录学生，仅本人 | student_academic_reminder | 本人提醒 |
| 取消提醒 | `DELETE /api/v1/student/reminders/{reminder_id}` | 已登录学生，仅本人 | student_academic_reminder | 更新本人提醒状态 |
| 查询申请进度 | `GET /api/v1/student/progress` | 已登录学生，仅本人 | student_application_progress | 按不同申请和阶段展示真实来源状态 |
| 查询通知 | `GET /api/v1/student/notifications` | 已登录学生，仅本人 | business_notification | 仅本人可见通知 |
| 通知已读 | `POST /api/v1/student/notifications/{notification_id}/read` | 已登录学生，仅本人 | business_notification | 标记本人通知已读 |
| 统一智能对话 | `POST /api/v1/student/chat` | 已登录学生，仅本人 | student_assistant_session、student_assistant_turn；按场景查询业务表及知识资料 | 接收 message 和可选 conversation_token；查询返回事实，办理返回预览 |
| 确认 AI 办理 | `POST /api/v1/student/actions/confirm` | 已登录学生，仅本人 | 目标业务表、operation_log | 校验 action_token 后由固定服务执行，不再次调用模型 |

生活支持和升学推荐共用学生对话接口，分别使用 life / upgrade 意图且 action=none，不新增独立智能体或专属写表。生活资料来自已审核文件；升学场景可在具有 course_project.read 权限时只读上架项目，不自动报名、下单或生成线索。

### 2. 老师协作与服务同步接口

#### 老师/员工侧：10 个方法

| 方法与路径                                                              | 老师界面应提供的功能    | 核心表（中文用途注释）                      |
| ------------------------------------------------------------------ | ------------- | -------------------------------- |
| GET /api/v1/internal/student/leave                                 | 负责学生的请假列表     | student_admin_service（学生行政事务申请表） |
| GET /api/v1/internal/student/leave/{apply_id}                      | 查看请假详情        | student_admin_service（学生行政事务申请表） |
| POST /api/v1/internal/student/leave/{apply_id}/decision            | 同意/拒绝，提交版本和意见 | 申请表、通知表、操作审计表                    |
| GET /api/v1/internal/student/notifications                         | 老师站内通知列表      | business_notification（业务通知表）     |
| POST /api/v1/internal/student/notifications/{notification_id}/read | 老师标记已读        | business_notification（业务通知表）     |
| GET /api/v1/internal/student/warnings                              | 负责学生的预警列表     | mental_warning（学生心理预警及人工处置表）     |
| GET /api/v1/internal/student/warnings/{warning_id}                 | 授权查看预警依据      | mental_warning（学生心理预警及人工处置表）     |
| POST /api/v1/internal/student/warnings/{warning_id}/ack            | 接手预警          | 预警表、操作审计表                        |
| POST /api/v1/internal/student/warnings/{warning_id}/follow         | 记录跟进说明        | 预警表、操作审计表                        |
| POST /api/v1/internal/student/warnings/{warning_id}/close          | 记录处置结果并关闭     | 预警表、操作审计表                        |

预警动作正文包含 expected_version、note。老师 Token 来自公共登录，接口仍校验负责关系，不能因 URL 有 internal 就认为可以无鉴权调用。

#### 同步服务：3 个方法

| 方法与路径                                          | 调用方                                | 写入目标                                           |
| ---------------------------------------------- | ---------------------------------- | ---------------------------------------------- |
| POST /api/v1/internal/student/sync/academic    | 可信教务适配服务                           | student_academic_event（学生学业截止与考试节点镜像表）及必要的提醒重排 |
| POST /api/v1/internal/student/sync/progress    | 可信 CRM 适配服务                        | student_application_progress（学生留学申请阶段最新进度镜像表）  |
| POST /api/v1/internal/student/sync/{kind}/pull | 可信服务或后台触发，kind 仅 academic/progress | 从已配置外部来源拉取并写入对应镜像表                             |

使用独立 STUDENT_SYNC_TOKEN，不能交给学生页面。推送正文包含内部 student_id、source_system、records；拉取正文包含内部 student_id，由后端查出外部身份。

### 3. 数据表与字段范围

学生个人表共七张：mental_health_profile、mental_warning、student_academic_event、student_academic_reminder、student_application_progress、student_assistant_session、student_assistant_turn。来源说明前五张业务表本地已存在，仅新增两张会话表。完整 73 个字段及公共表关联见第八节。

请假复用 student_admin_service；投诉复用 service_ticket、service_ticket_record；通知使用 business_notification；幂等和操作审计复用 operation_log。来源未提供这些公共表的完整普通字段，本文仅保留已明确的关联，不推测补全。

## 二、用户角色和接口鉴权

### 1. 公共 JWT 认证与业务范围校验

学生与老师使用公共账号登录接口取得 JWT，业务复用公共认证及权限依赖，按服务端真实身份、必要权限、本人归属或有效负责关系校验。internal 路径也必须认证，不能作为匿名内部接口。智能体本身不是额外拥有数据库权限的账号。

| 用户角色 / 调用主体 | 可用功能 | 权限与数据范围 |
| --- | --- | --- |
| 学生 student | 21 个学生端方法 | 仅本人记录及会话；办理先预览、再确认；不能审批或修改他人数据 |
| 老师 / 员工 employee | 10 个老师协作方法 | 需满足公共权限和负责关系；请假校验版本和审批关系；心理原文及风险依据仅授权处理人可读 |
| 可信教务 / CRM 同步服务 | 3 个同步方法 | 使用独立 STUDENT_SYNC_TOKEN，限定 academic / progress；凭据不得交给学生页面 |
| 公共管理员及其他身份 | 来源未明确默认授权 | 不推断具有全部学生、审批或心理数据权限；需按公共策略及业务关系确认 |
| 匿名用户 | 公共登录入口 | 不提供学生个人数据查询或办理授权 |

来源未列出逐接口完整权限标识，不另行编造权限包。course_project.read 为来源明确列出的上架项目读取权限；同步身份按来源使用独立凭据，不将其替换为个人 JWT。

### 2. 确认、版本与幂等

对话请求携带 Idempotency-Key，办理返回 pending_action；确认时提交后端签发的 action_token，由固定服务执行。后续修改通常携带 expected_version；来源特别要求请假撤回、老师审批及预警动作检查版本。确认凭证、会话归属和操作审计共同避免越权和重复写入。

## 三、学生业务操作与日志、审计

### 1. 常用操作流程

| 业务 | 操作顺序 | 闭环结果 |
| --- | --- | --- |
| 请假 | 学生提交 → 老师查询及审批 → 后台通知 → 学生查询 | 同一申请状态改变，保留审批意见、通知和审计 |
| 投诉 | 学生建单 → 企业分派和处理 → 学生查看回应 → 确认或重开 → 评价 | 状态、版本及可见沟通记录一致 |
| 心理预警 | 辅助评估 → 负责老师收到预警 → 接手、跟进、关闭 | 人工处理轨迹明确，通知送达不等于处理完成 |
| 学业提醒 | 教务同步 → 学生设置提醒 → 节点改期 → 后台投递 | 按最新版本及新时间提醒，避免重复投递 |
| 申请进度 | CRM 更新 → 同步镜像 → 学生查询 | 学生、外部申请、阶段和更新时间匹配 |
| 资料问答 | 维护资料 → 学生提问 → 展示来源 → 停用失效资料 | 有依据且来源可追溯，失效资料退出检索 |

### 2. 请求字段与业务记录

请假提交使用 leave_content、leave_type、leave_start_at、leave_end_at，直接表单可传 generate_ai_summary；审批使用 expected_version、decision、comment，拒绝必须给意见。

投诉 HTTP 提交字段为 content、ticket_type、category_code，智能体内部 ticket.submit 参数为 complaint_content、feedback_type、category_code，不能直接混用。提醒使用 academic_event_id、lead_minutes。

operation_log 保存真实操作者、业务变更与幂等审计；student_assistant_turn 保存聊天响应、请求键摘要和回执；service_ticket_record 保存沟通与流转。运行日志沿用公共能力，不能代替数据库审计。来源未提供独立日志格式或日志管理接口，本文不新增。

心理关怀仅为支持性辅助，不是自动诊断或自动处分依据；人工关闭需接手及处置结果。心理原文和风险依据不用于普通项目推荐、企业报表或公共查询。

## 四、统一返回格式及异常处理

模块复用公共返回及异常能力。来源明确受控查询响应使用 code、data，成功为 code=0；接口整体返回结构遵循公共约定。源文档没有统一列出各接口的完整错误码和 HTTP 状态表，本文不补写未经提供的细节。

| 场景 | 响应内容 / 处理要求 |
| --- | --- |
| 对话查询 | 返回本人真实记录，不由模型编造节点、申请进度或业务事实 |
| 对话办理 | 返回 pending_action 预览及确认凭证，未经确认不写对应单据 |
| 确认执行 | 返回固定业务服务形成的结果，重复请求复用幂等回执 |
| 资料不足或未接来源 | 明确暂无记录或无法核实，不用模型补造 |
| 来源同步 | 以 source_updated_at 防止旧数据覆盖；synced_at 仅表示最近成功同步，失败不刷新 |
| 通知 | 写入后经后台任务成功投递才对相应收件人展示；通知已读不等于事项已处理 |

## 五、调用本地 Dify 大模型：唯一学生 Workflow

学生页面调用统一聊天接口，后端先读取本人记录和已审核资料，再调用唯一 Dify Workflow；模型返回后由后端校验意图、参数和权限。查询返回事实，咨询展示来源，办理形成确认预览。

| 分工 | 公共模块 / 外部依赖 | 学生模块负责 |
| --- | --- | --- |
| 身份与权限 | 公共账号、JWT 和公共权限配置 | 学生归属、老师负责关系、业务状态及确认凭证校验 |
| Dify 连接 | 复用公共基础能力，Dify 平台提供模型及发布应用 | student_assistant_dify 客户端、STUDENT_DIFY_BASE/KEY 配置及输出校验 |
| 模型能力 | 模型供应商需真实可用 | 唯一统一 Workflow、提示词、结构化输出契约 |
| 数据查询 | 本地固定查询，或组长 student-v1 适配服务 | 本人范围与字段白名单，不接受模型生成的可执行 SQL |
| 业务执行 | 共用业务数据库及公共事务能力 | 固定服务落库、审计及通知，确认时不再次调用模型 |
| 知识与项目 | 资料负责人维护真实来源，项目模块维护上架项目 | 检索已审核资料、展示依据；缺资料时明确无法核实 |

只部署 dify/student 下的统一应用。历史请假、投诉最小单元客户端及 DSL 保留兼容参考，不额外部署成学生智能体。来源说明 Workflow 草稿已在本地导入，模型供应商、应用 Key、发布和真实调用尚未完成，不把草稿导入写成真实模型验收。

## 六、复用的公共功能及模块对接

### 1. 公共能力分工

| 通用功能 | 学生模块使用方式 | 说明 |
| --- | --- | --- |
| 公共登录与权限 | 复用 auth、authorization、access_control | 业务身份由公共账号关联，不能凭前端传入 student_id 冒充他人 |
| 配置管理 | student_config.py 及学生配置模板 | 分离本地密钥和交付模板，实际配置不上传 |
| 数据库与数据访问 | 复用公共模型和现有分层 | 最小单元有 repository，其他服务仍存在直接 SQLAlchemy 访问，不宣称全部迁移完成 |
| 参数契约 | schemas 定义学生、老师、同步及模型输出 | 业务参数与智能体动作参数分别校验 |
| 后台任务 | StudentTasks 与 run_student_tasks | 提醒、通知、补分派及失败重试，需持续运行 |
| 幂等、审计和会话隔离 | 固定业务服务及对应持久化表 | 本地已有验证记录不代替跨系统及真实模型验收 |

### 2. 对接对象、职责及当前边界

| 对接对象      | 现有入口或配置                                           | 对方需要提供/实现什么                                   | 对接成功应看到的效果            | 当前边界               |
| --------- | ------------------------------------------------- | --------------------------------------------- | --------------------- | ------------------ |
| 组长公共认证    | /api/v1/auth/login、公共 JWT 依赖及 access_control.yaml | 有效学生/员工账号、身份关联、必要权限和统一签名配置                    | 学生只见本人数据；老师只处理授权记录    | 代码已接公共依赖，本地账号已验证   |
| 组长查询服务    | 默认 STUDENT_QUERY_BACKEND=local；可切 group           | 若切 group，提供 student-v1 受控查询响应，不是任意自然语言 SQL 接口 | 查询结构、身份和字段与本地一致       | group 模式预留，未验证真实远端 |
| 企业/老师请假模块 | 本文 10 个老师协作接口中的请假入口                               | 页面入口、负责老师绑定、审批操作和状态展示                         | 学生提交 → 老师审批 → 学生看到结果  | 本模块已提供接口，未代做全部企业页面 |
| 企业售后工单模块  | 共用 service_ticket、service_ticket_record           | 对齐已有企业工单接口、分派/处理流程、状态值与版本规则                   | 企业回应后学生可查记录，解决后可确认或重开 | 不编造尚未核实的企业 URL     |
| 教务模块      | 同步推送，或 STUDENT_EDUCATION_URL/TOKEN 拉取             | 真实节点、外部学生编号、节点更新时间和时区                         | 学生可见考试/DDL，改期后提醒相应调整  | 正式来源未配置            |
| CRM/申请模块  | 同步推送，或 STUDENT_CRM_URL/TOKEN 拉取                   | 真实申请编号、阶段、状态与更新时间                             | 展示不同申请的真实进度，不覆盖错人     | 正式来源未配置            |
| 资料维护模块    | STUDENT_KNOWLEDGE_FILE                            | 审核过的生活与升学资料、来源、启停状态                           | 回答有依据并展示来源；撤下资料不再使用   | 当前正式知识集合为空         |
| 项目/客服模块   | course_project 固定只读查询                             | 维护上架项目及报名方式；承接进一步咨询                           | 推荐来自真实项目，学生有真实后续联系渠道  | 未实现自动报名/生成线索       |
| 通知模块/运维   | StudentTasks；可选 STUDENT_NOTIFICATION_URL/TOKEN    | 持续运行任务；站内 UI 查询；如接外部渠道再配置接收适配                 | 到点通知可读，失败重试，不重复发      | 当前真实验证为站内；外部渠道未验收  |
| Dify 平台   | STUDENT_DIFY_BASE/KEY + 唯一 Workflow               | 真实可用模型、发布应用、专用 Key、严格 JSON 输出                 | 聊天返回结构化结果并进入受控业务流程    | 草稿已导入，真实调用后置       |

### 3. 查询、同步及通知契约

组长查询默认使用 local，可切 group。group 请求使用 student-v1，包含 contract_version、scenario、subject、filters、limit、offset；响应要求 code=0，data 包含 contract_version、subject_id、scenario、rows、total。每行携带正确 student_id，字段必须在白名单中。现有服务若只接自然语言并返回 SQL，需增加适配层或继续使用本地固定查询，不能直接把任意 NL2SQL Workflow 地址当作完成接入。

student_profile.student_id 是内部主键；external_student_id 为教务外部编号，crm_student_id 为 CRM 外部编号。来源响应必须回传同一外部编号并提供 source_system、records。时间带时区，来源更新时间用于版本保护，不能只改字段名就假定是同一个学生。

通知写 business_notification，后台成功后由页面刷新或轮询读取。可选 webhook 接收 notification_id、employee_id、student_id、title、content、event_code，并要求 accepted=true；仅填写 URL 不会自动切换默认站内渠道，尚不能宣称短信、邮件、企业微信或手机推送已接通。

### 4. 已提交与验证边界

来源说明学生页面与公共登录、请假和投诉、心理评估与人工预警、学业及进度同步、提醒任务、资料检索、幂等审计和会话隔离均有提交。已有本地演示账号、合成数据保存及站内通知验证，自动回归记录为 79 项通过。

真实模型尚未接通，正式教务/CRM 来源未配置，正式知识集合为空，外部通知未验收；企业处理页面及人员流程仍需对接。以上回归记录不能代表真实模型、生产人员流程或跨系统闭环已经验收。

## 七、架构目录（文件名及功能作用）

以下沿用来源中的提交版本目录及文件说明，未读取当前目录另行核验。[新增] 相对组长基线 7bec441，[本地] 代表不上传，不等于本轮创建。只列结构及职责，不包含实现代码。

```text
D:/AI/StuProject/
├─ app/                                  [已有，继续复用]
│  ├─ main.py                            路由注册、学生页面入口
│  ├─ access_control.yaml                公共角色权限，补充学生/负责老师权限
│  ├─ student_config.py                  [新增文件] 学生独立配置
│  ├─ api/                               [已有目录]
│  │  ├─ auth.py                         复用公共登录
│  │  ├─ student_leave.py                原请假最小单元 HTTP 入口
│  │  ├─ student_ticket.py               [新增文件] 投诉最小单元入口
│  │  └─ student.py                      [新增文件] 其余学生、老师、同步接口
│  ├─ core/                              [已有目录]
│  │  ├─ auth.py、authorization.py        复用身份和公共权限
│  │  └─ student_auth.py                 [新增文件] 学生业务权限、确认凭证、同步身份
│  ├─ clients/                           [已有目录]
│  │  ├─ student_assistant_dify.py        [新增文件] 当前唯一应用客户端
│  │  ├─ student_leave_dify.py            历史最小单元兼容代码
│  │  └─ student_ticket_dify.py           历史最小单元兼容代码
│  ├─ models/                            [已有目录]
│  │  ├─ user_account.py                 复用公共账号模型
│  │  ├─ student_leave.py                公共请假及关联表投影
│  │  ├─ student_ticket.py               [新增文件] 共享工单表投影
│  │  ├─ student_shared.py               [新增文件] 复用共享映射
│  │  ├─ student.py                      [新增文件] 五张学生业务表
│  │  ├─ student_conversation.py         [新增文件] 两张会话表
│  │  └─ student_types.py                [新增文件] 类型与时间工具
│  ├─ schemas/                           [已有目录]
│  │  ├─ student_leave.py                请假最小单元契约
│  │  ├─ student_ticket.py               [新增文件] 投诉最小单元契约
│  │  └─ student.py                      [新增文件] 其余业务、同步及模型输出契约
│  ├─ repositories/                      [已有目录]
│  │  ├─ student_leave_repository.py     复用请假数据访问
│  │  ├─ student_ticket_repository.py    [新增文件] 工单数据访问
│  │  └─ student_schema.py               [新增文件] 最小单元表结构检查
│  ├─ services/                          [已有目录]
│  │  ├─ student_leave_service.py        请假最小单元业务
│  │  ├─ student_ticket_service.py       [新增文件] 投诉最小单元业务
│  │  ├─ student_common.py               [新增文件] 最小单元公共逻辑
│  │  ├─ student_service.py              [新增文件] 学生与老师业务服务
│  │  ├─ student_chat.py                 [新增文件] 单智能体编排及确认执行
│  │  ├─ student_clients.py              [新增文件] 查询、教务/CRM 适配契约
│  │  ├─ student_local_query.py          [新增文件] 本人固定 SQL 查询
│  │  ├─ student_sync.py                 [新增文件] 来源同步与版本保护
│  │  └─ student_knowledge.py            [新增文件] 正式知识及上架项目检索
│  └─ tasks/                             [已有目录，无需再建顶层任务目录]
│     └─ student_tasks.py                [新增文件] 提醒、通知、补分派与重试
├─ dify/                                 [已有目录]
│  ├─ student/                           [新增目录，当前唯一应用]
│  │  ├─ student_assistant.yml           可导入的统一 Workflow
│  │  ├─ assistant_prompt.md             统一提示词
│  │  ├─ knowledge.json                  已审核资料集合，当前为空
│  │  └─ README.md                       配置说明
│  ├─ student_leave/                     已有历史请假 DSL，不额外部署
│  └─ student_ticket/                    [新增目录] 历史投诉 DSL，不额外部署
├─ frontend/                             [已有目录]
│  ├─ student-assistant.html             [新增文件] 独立学生界面
│  └─ js/app.js                          修改原学生入口以嵌入页面
├─ scripts/                              [已有目录]
│  ├─ export_student_workflow.py          [新增文件] 生成统一 DSL
│  ├─ export_student_assistant_api.py     [新增文件] 导出实际接口
│  ├─ check_student_shared_schema.py      [新增文件] 检查共享表
│  ├─ init_student_minimal_tables.py      [新增文件] 原最小单元辅助初始化
│  ├─ init_student_assistant.py           [新增文件] 检查并创建缺失学生专属表
│  ├─ run_student_app.py                 [新增文件] 隔离本地配置启动
│  ├─ run_student_tasks.py               [新增文件] 启动学生后台任务/可选同步
│  ├─ student_local_mysql.py             [新增文件] 管理已有本地开发实例
│  ├─ setup_student_demo_login.py        [新增文件] 仅本地演示账号初始化
│  ├─ student_sql_paths.py               [新增文件] SQL 路径辅助
│  └─ sql/                               [已有目录]
│     ├─ all.sql                         公共数据库基线，归公共维护
│     └─ student/                        [新增目录] 学生增量 SQL
│        ├─ 20261015_add_student_admin_service.sql
│        └─ 20261016_assistant_conversations.sql
├─ tests/                                学生模块测试目录
│  ├─ student_leave_s01/                 [新增目录] 请假最小单元回归
│  ├─ student_ticket_s05/                [新增目录] 工单最小单元回归
│  └─ student_assistant/                 [新增目录] 单智能体和完整业务回归
├─ docs/                                 [本地新增，不上传]
│  └─ student-assistant/                  [本地新增]
│     └─ 学生助手_已提交功能与模块对接说明.md  本文
├─ .env.student.example                  已提交的无密钥配置模板
└─ .env.student.local                    [本地] 实际配置与密钥，禁止上传
```

沿用 api、schemas、services、repositories、models、clients 和 tasks 分层；统一应用使用 dify/student，增量 SQL 使用 scripts/sql/student，测试分别保留最小单元与整体回归目录。不另建平行框架目录；真实密钥、运行数据、日志和缓存不作为交付资产。

## 八、数据表完整字段与公共表关联

本节只完整展开个人负责的 **7 张学生专属表（5 张业务表 + 2 张会话表）**。复用的公共表不展开普通字段，只在末尾列出关联外键字段及其指向。来源说明字段按其提交版本代码模型整理，不将历史 SQL 中未映射的兼容列算作本次个人字段。中文注释按模型用途整理，不代表本次修改了数据库 COMMENT。

### 8.1 个人表总览

| 实际表名及中文注释                                     | 字段数 | 对应功能             |
| --------------------------------------------- | --- | ---------------- |
| mental_health_profile（学生心理评估历史表）              | 11  | 每轮辅助情绪评估与高风险判断追溯 |
| mental_warning（学生心理预警及人工处置表）                  | 13  | 高风险预警、老师接手、跟进和关闭 |
| student_academic_event（学生学业截止与考试节点镜像表）        | 14  | 教务同步、节点查询与改期处理   |
| student_academic_reminder（学生学业提醒设置与执行状态表）     | 10  | 设置、取消、重排与投递提醒    |
| student_application_progress（学生留学申请阶段最新进度镜像表） | 12  | CRM同步及本人多申请进度查询  |
| student_assistant_session（学生助手会话表）            | 5   | 会话归属与并发版本控制      |
| student_assistant_turn（学生助手对话轮次与回执表）          | 8   | 历史对话、幂等回执及模型结果追溯 |

### 8.2 mental_health_profile（学生心理评估历史表）

对应功能：每轮辅助情绪评估与高风险判断追溯。

| 英文字段名            | 字段中文名      | 类型                                                 | 中文注释                              | 对应功能/用途                                        |
| ---------------- | ---------- | -------------------------------------------------- | --------------------------------- | ---------------------------------------------- |
| id               | 记录主键       | BIGINT                                             | 评估主键ID                            | 本表记录唯一标识                                       |
| student_id       | 所属学生编号     | BIGINT                                             | 学生ID，关联student_profile.student_id | 关联学生，限定本人数据和跨表归属                               |
| emotion_tag      | 情绪标签       | VARCHAR(50)                                        | 本次情绪标签                            | 每轮辅助情绪评估与高风险判断追溯：本次情绪标签                        |
| emotion_score    | 情绪平稳评分     | NUMERIC(5, 2)                                      | 分值0至100，越高表示情绪越平稳；不代表医学诊断         | 每轮辅助情绪评估与高风险判断追溯：分值0至100，越高表示情绪越平稳；不代表医学诊断     |
| history_data     | 历史数据（兼容字段） | JSON                                               | 旧历史JSON兼容字段；新记录保持NULL             | 旧历史 JSON 兼容列；当前实现新记录保持空值，不作为新历史存储              |
| risk_level       | 风险等级       | VARCHAR(20)                                        | 评估风险：low/medium/high/critical     | 每轮辅助情绪评估与高风险判断追溯：评估风险：low/medium/high/critical |
| observed_at      | 消息评估时间     | DATETIME(6)                                        | 源消息发生时间，UTC；区别于入库时间               | 每轮辅助情绪评估与高风险判断追溯：源消息发生时间，UTC；区别于入库时间           |
| source_event_id  | 源消息事件编号    | VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin | 可信入口生成的源事件ID，重试时复用                | 每轮辅助情绪评估与高风险判断追溯：可信入口生成的源事件ID，重试时复用            |
| workflow_run_id  | 智能体运行编号    | VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin | Dify工作流运行ID，仅用于追溯                 | 每轮辅助情绪评估与高风险判断追溯：Dify工作流运行ID，仅用于追溯             |
| analysis_version | 评估配置版本     | VARCHAR(64)                                        | 心理分析配置版本，明确分值和风险口径                | 每轮辅助情绪评估与高风险判断追溯：心理分析配置版本，明确分值和风险口径            |
| created_at       | 创建时间       | DATETIME(6)                                        | 创建时间，UTC                          | 记录创建时点，用于排序与追溯                                 |

### 8.3 mental_warning（学生心理预警及人工处置表）

对应功能：高风险预警、老师接手、跟进和关闭。

| 英文字段名           | 字段中文名    | 类型          | 中文注释                                | 对应功能/用途                                              |
| --------------- | -------- | ----------- | ----------------------------------- | ---------------------------------------------------- |
| id              | 记录主键     | BIGINT      | 预警主键ID                              | 本表记录唯一标识                                             |
| student_id      | 所属学生编号   | BIGINT      | 学生ID，关联student_profile.student_id   | 关联学生，限定本人数据和跨表归属                                     |
| profile_id      | 关联评估记录编号 | BIGINT      | 触发评估ID，与student_id组成画像外键            | 高风险预警、老师接手、跟进和关闭：触发评估ID，与student_id组成画像外键            |
| trigger_reason  | 预警触发依据   | TEXT        | 必要的触发依据，仅授权处理人可见                    | 授权老师查看的风险触发依据，不向普通学生查询开放                             |
| risk_level      | 风险等级     | VARCHAR(20) | 预警等级：high/critical                  | 高风险预警、老师接手、跟进和关闭：预警等级：high/critical                  |
| follower_status | 人工处理状态   | VARCHAR(20) | 人工处理状态：pending/processing/closed    | 高风险预警、老师接手、跟进和关闭：人工处理状态：pending/processing/closed    |
| follower_id     | 负责处理老师编号 | BIGINT      | 处理员工ID，关联employee.employee_id；未分派可空 | 高风险预警、老师接手、跟进和关闭：处理员工ID，关联employee.employee_id；未分派可空 |
| acknowledged_at | 人工接手时间   | DATETIME(6) | 真实人工接手时间，UTC                        | 高风险预警、老师接手、跟进和关闭：真实人工接手时间，UTC                        |
| closed_at       | 人工关闭时间   | DATETIME(6) | 人工关闭时间，UTC                          | 高风险预警、老师接手、跟进和关闭：人工关闭时间，UTC                          |
| handling_result | 人工处置结果   | TEXT        | 最终人工处置结果；关闭时不能为空                    | 人工处置结果；关闭预警需有实际处理记录                                  |
| version         | 并发版本号    | INTEGER     | 并发版本，业务更新时条件校验并递增                   | 会话或业务并发版本，防止并发覆盖                                     |
| updated_at      | 最近修改时间   | DATETIME(6) | 最近修改时间，UTC                          | 记录最近修改时点，用于新鲜度与追溯                                    |
| created_at      | 创建时间     | DATETIME(6) | 创建时间，UTC                            | 记录创建时点，用于排序与追溯                                       |


### 8.4 student_academic_event（学生学业截止与考试节点镜像表）

对应功能：教务同步、节点查询与改期处理。

| 英文字段名             | 字段中文名    | 类型                                                | 中文注释                              | 对应功能/用途                                |
| ----------------- | -------- | ------------------------------------------------- | --------------------------------- | -------------------------------------- |
| id                | 记录主键     | BIGINT                                            | 学业节点主键ID                          | 本表记录唯一标识                               |
| student_id        | 所属学生编号   | BIGINT                                            | 学生ID，关联student_profile.student_id | 关联学生，限定本人数据和跨表归属                       |
| source_system     | 来源系统编码   | VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin | 教务来源编码，如education                 | 教务同步、节点查询与改期处理：教务来源编码，如education       |
| external_event_id | 外部学业节点编号 | VARCHAR(128) COLLATE utf8mb4_bin                  | 源系统节点ID，与学生和来源组成同步唯一键             | 教务同步、节点查询与改期处理：源系统节点ID，与学生和来源组成同步唯一键   |
| event_type        | 学业节点类型   | VARCHAR(20)                                       | 节点类型：ddl截止日期/exam考试               | 教务同步、节点查询与改期处理：节点类型：ddl截止日期/exam考试     |
| title             | 学业节点标题   | VARCHAR(200)                                      | 论文或考试标题                           | 教务同步、节点查询与改期处理：论文或考试标题                 |
| due_at            | 截止或考试时间  | DATETIME(6)                                       | 准确截止或考试时点，UTC                     | 教务同步、节点查询与改期处理：准确截止或考试时点，UTC           |
| source_timezone   | 来源时区     | VARCHAR(64)                                       | 来源IANA时区，如Asia/Shanghai           | 教务同步、节点查询与改期处理：来源IANA时区，如Asia/Shanghai |
| event_status      | 学业节点状态   | VARCHAR(20)                                       | 节点状态：active/cancelled             | 教务同步、节点查询与改期处理：节点状态：active/cancelled   |
| event_version     | 学业节点版本   | INTEGER                                           | 节点时间或有效状态改变时递增的提醒版本               | 教务同步、节点查询与改期处理：节点时间或有效状态改变时递增的提醒版本     |
| source_updated_at | 源系统更新时间  | DATETIME(6)                                       | 源系统更新时间，UTC；防止旧消息覆盖新节点            | 拒绝源系统旧版本覆盖新节点                          |
| synced_at         | 最近成功同步时间 | DATETIME(6)                                       | 最后成功同步时间，UTC；用于展示数据新鲜度            | 展示最近成功同步时间，并据此判断过期                     |
| updated_at        | 最近修改时间   | DATETIME(6)                                       | 最近修改时间，UTC                        | 记录最近修改时点，用于新鲜度与追溯                      |
| created_at        | 创建时间     | DATETIME(6)                                       | 创建时间，UTC                          | 记录创建时点，用于排序与追溯                         |

### 8.5 student_academic_reminder（学生学业提醒设置与执行状态表）

对应功能：设置、取消、重排与投递提醒。

| 英文字段名             | 字段中文名    | 类型          | 中文注释                                      | 对应功能/用途                                         |
| ----------------- | -------- | ----------- | ----------------------------------------- | ----------------------------------------------- |
| id                | 记录主键     | BIGINT      | 提醒主键ID                                    | 本表记录唯一标识                                        |
| student_id        | 所属学生编号   | BIGINT      | 节点所属学生，通过组合外键关联同一学生                       | 关联学生，限定本人数据和跨表归属                                |
| academic_event_id | 关联学业节点编号 | BIGINT      | 学业节点ID，组合关联student_academic_event         | 设置、取消、重排与投递提醒：学业节点ID，组合关联student_academic_event |
| lead_minutes      | 提前提醒分钟数  | INTEGER     | 提前分钟数；1440为一天，0为到点提醒                      | 设置、取消、重排与投递提醒：提前分钟数；1440为一天，0为到点提醒              |
| notify_at         | 计划提醒时间   | DATETIME(6) | 计划提醒时点，UTC；由节点时间减提前量计算                    | 设置、取消、重排与投递提醒：计划提醒时点，UTC；由节点时间减提前量计算            |
| event_version     | 学业节点版本   | INTEGER     | 对应节点版本，发送前须检查仍一致                          | 投递前复核节点版本，避免改期后发送旧提醒                            |
| status            | 提醒执行状态   | VARCHAR(20) | pending待执行/queued已入队/sent已投递/cancelled已取消 | 参与有效性或业务状态判断                                    |
| sent_at           | 成功投递时间   | DATETIME(6) | 当前版本实际成功发送时间，UTC                          | 设置、取消、重排与投递提醒：当前版本实际成功发送时间，UTC                  |
| updated_at        | 最近修改时间   | DATETIME(6) | 最近修改时间，UTC                                | 记录最近修改时点，用于新鲜度与追溯                               |
| created_at        | 创建时间     | DATETIME(6) | 创建时间，UTC                                  | 记录创建时点，用于排序与追溯                                  |

### 8.6 student_application_progress（学生留学申请阶段最新进度镜像表）

对应功能：CRM同步及本人多申请进度查询。

| 英文字段名                   | 字段中文名    | 类型                                                | 中文注释                                                  | 对应功能/用途                                                               |
| ----------------------- | -------- | ------------------------------------------------- | ----------------------------------------------------- | --------------------------------------------------------------------- |
| id                      | 记录主键     | BIGINT                                            | 阶段进度主键ID                                              | 本表记录唯一标识                                                              |
| student_id              | 所属学生编号   | BIGINT                                            | 学生ID，关联student_profile.student_id                     | 关联学生，限定本人数据和跨表归属                                                      |
| source_system           | 来源系统编码   | VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin | CRM或申请系统来源编码                                          | CRM同步及本人多申请进度查询：CRM或申请系统来源编码                                          |
| external_application_id | 外部申请编号   | VARCHAR(128) COLLATE utf8mb4_bin                  | 源系统申请ID，用于区分不同院校和项目                                   | CRM同步及本人多申请进度查询：源系统申请ID，用于区分不同院校和项目                                   |
| application_name        | 申请项目名称   | VARCHAR(200)                                      | 院校或申请项目展示名称                                           | CRM同步及本人多申请进度查询：院校或申请项目展示名称                                           |
| stage_code              | 申请阶段编码   | VARCHAR(32)                                       | document_review文书/school_application院校/visa_process签证 | CRM同步及本人多申请进度查询：document_review文书/school_application院校/visa_process签证 |
| stage_status            | 申请阶段状态   | VARCHAR(64)                                       | 外部契约映射的阶段状态，不由AI臆造                                    | CRM同步及本人多申请进度查询：外部契约映射的阶段状态，不由AI臆造                                    |
| detail                  | 申请进度说明   | VARCHAR(500)                                      | 必要进度说明，如需补充材料                                         | CRM同步及本人多申请进度查询：必要进度说明，如需补充材料                                         |
| source_updated_at       | 源系统更新时间  | DATETIME(6)                                       | 源系统更新时间，UTC                                           | 防止旧 CRM 记录覆盖更新进度                                                      |
| synced_at               | 最近成功同步时间 | DATETIME(6)                                       | 最后成功同步时间，UTC；失败不刷新                                    | 展示来源同步新鲜度；同步失败不刷新                                                     |
| updated_at              | 最近修改时间   | DATETIME(6)                                       | 最近修改时间，UTC                                            | 记录最近修改时点，用于新鲜度与追溯                                                     |
| created_at              | 创建时间     | DATETIME(6)                                       | 创建时间，UTC                                              | 记录创建时点，用于排序与追溯                                                        |

### 8.7 student_assistant_session（学生助手会话表）

对应功能：会话归属与并发版本控制。

| 英文字段名      | 字段中文名  | 类型          | 中文注释        | 对应功能/用途                 |
| ---------- | ------ | ----------- | ----------- | ----------------------- |
| session_id | 会话编号   | VARCHAR(64) | 会话唯一标识      | 学生会话唯一标识，不等同于公共登录 Token |
| student_id | 所属学生编号 | BIGINT      | 所属学生内部主键    | 关联学生，限定本人数据和跨表归属        |
| version    | 并发版本号  | INTEGER     | 会话并发版本号     | 会话或业务并发版本，防止并发覆盖        |
| created_at | 创建时间   | DATETIME    | 创建时间（UTC）   | 记录创建时点，用于排序与追溯          |
| updated_at | 最近修改时间 | DATETIME    | 最近更新时间（UTC） | 记录最近修改时点，用于新鲜度与追溯       |

### 8.8 student_assistant_turn（学生助手对话轮次与回执表）

对应功能：历史对话、幂等回执及模型结果追溯。

| 英文字段名           | 字段中文名   | 类型           | 中文注释              | 对应功能/用途                       |
| --------------- | ------- | ------------ | ----------------- | ----------------------------- |
| id              | 记录主键    | BIGINT       | 对话轮次主键            | 本表记录唯一标识                      |
| session_id      | 会话编号    | VARCHAR(64)  | 会话唯一标识            | 关联会话，限制历史只在本人会话内读取            |
| student_id      | 所属学生编号  | BIGINT       | 所属学生内部主键          | 关联学生，限定本人数据和跨表归属              |
| request_key     | 请求幂等键摘要 | VARCHAR(128) | 本次请求幂等键摘要         | 当前聊天代码保存原始幂等键的摘要，配合学生 ID 唯一约束 |
| parameters_hash | 请求参数摘要  | VARCHAR(64)  | 规范化请求正文摘要         | 识别相同请求键下的正文冲突                 |
| message         | 学生消息正文  | TEXT         | 学生本轮消息文本          | 作为有界会话历史输入；不应向无关模块公开          |
| result          | 本轮响应与回执 | JSON         | 本轮响应及业务预览回执（JSON） | 保存聊天响应、会话凭证和办理预览等回执，重复请求返回原结果 |
| created_at      | 创建时间    | DATETIME     | 创建时间（UTC）         | 记录创建时点，用于排序与追溯                |

### 8.9 公共表：仅列关联外键字段

#### 个人表指向公共表

| 个人表外键字段                                 | 公共表被关联字段（通常是主键）                   | 中文说明/对应功能     |
| --------------------------------------- | --------------------------------- | ------------- |
| mental_health_profile.student_id        | student_profile.student_id（学生档案表） | 评估属于哪名学生      |
| mental_warning.student_id               | student_profile.student_id（学生档案表） | 预警属于哪名学生      |
| mental_warning.follower_id              | employee.employee_id（员工/老师表）      | 哪位老师负责处理预警    |
| student_academic_event.student_id       | student_profile.student_id（学生档案表） | 考试或截止节点属于哪名学生 |
| student_application_progress.student_id | student_profile.student_id（学生档案表） | 申请进度属于哪名学生    |
| student_assistant_session.student_id    | student_profile.student_id（学生档案表） | 会话归属与隔离       |
| student_assistant_turn.student_id       | student_profile.student_id（学生档案表） | 本轮消息及回执归属     |

student_academic_reminder 不另建直连公共学生表的外键；通过 (academic_event_id, student_id) → student_academic_event.(id, student_id) 组合外键保证节点与学生一致。预警的 (profile_id, student_id) → mental_health_profile.(id, student_id)、对话轮次的 session_id → student_assistant_session.session_id 都属于个人表之间的关联。

#### 复用业务所涉及的公共表关联字段

| 公共表（中文注释）                         | 关联外键字段 → 对应表字段                                                                                                                   | 对应功能                        |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| user_account（统一登录账号表）             | student_id → student_profile.student_id；employee_id → employee.employee_id                                                       | 登录身份关联                      |
| student_profile（学生档案表）            | department_id → org_department.department_id                                                                                     | 学生组织归属                      |
| student_staff_binding（学生与服务老师绑定表） | student_id → student_profile.student_id；employee_id → employee.employee_id                                                       | 定位负责老师                      |
| student_admin_service（学生行政事务申请表）  | student_id → student_profile.student_id                                                                                          | 请假归属；reviewer_id 另见下方逻辑关联说明 |
| service_ticket（服务工单表）             | student_id → student_profile.student_id；employee_id → employee.employee_id；handling_department_id → org_department.department_id | 投诉所属学生、处理人和部门               |
| service_ticket_record（工单沟通与流转记录表） | ticket_id → service_ticket.ticket_id；student_id → student_profile.student_id；employee_id → employee.employee_id                  | 沟通对应的工单与操作者                 |
| business_notification（业务通知表）      | student_id → student_profile.student_id；employee_id → employee.employee_id                                                       | 学生/老师通知接收关系                 |
| operation_log（业务操作与幂等审计表）         | student_id → student_profile.student_id；employee_id → employee.employee_id                                                       | 真实操作者归属与审计                  |

逻辑关联说明：student_admin_service.reviewer_id 对应 employee.employee_id，但当前共享模型未声明该字段的数据库外键，因此不把它写成已建外键。course_project（机构课程与升学项目目录表）当前仅按固定字段只读检索，没有与个人表建立外键，本节不展开其字段。org_department（组织部门表）和 employee（员工/老师表）在上述关系中作为被关联表，不再展开各自普通字段。

本节合计：个人表 7 张、个人字段 73 个；公共表仅列关联字段，不计入个人建表数量。
