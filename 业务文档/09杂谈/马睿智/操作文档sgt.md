# 马睿智操作文档：公共基础能力与客服、客户研判、报告、企业、学生六模块联动版

主模块：公共登录与权限入口（公共基础能力）  
已合并模块：客服 Agent（对外开放模块）  
已合并模块：客户信息研判（规划中的受保护内部模块）  
已合并模块：智能报告（平台管理员、部门主管可访问；配置仅平台管理员）  
本轮新增模块：企业管理、学生智能助手（开发目标，未联合验收）  
公共模块负责人：马睿智；客服模块负责人：何至朗；智能报告负责人：陈宇林；学生模块负责人：蒋立建；企业模块负责人：莫世杰  
整理日期：2026-10-17  
系统目录：`D:\AI\StuProject`

本文件以 mrz.md 为主体，逐章合并 hzl.md 的功能、接口、字段、约束、文件清单及交付状态，补充公共能力与客服的联动流程。两份源文件保留不变。本次交付为文档，不修改代码、建表或部署；不含实现代码示例。

主要来源为“业务文档/09杂谈/操作文档个人版/”下的 mrz.md、hzl.md。公共账号及关联表的完整字段另据当前 scripts/sql/all.sql 整理，并核对账号 ORM；客服六表字段保留 hzl.md 的设计口径，不能把不同来源的规格直接视为已验证一致。源文档中的运行状态说明作为原有核对记录保留，不代表本次完成全部功能验收。

本次补充参考 allm.md 的实施安排，按当前主文档的职责、完整字段和匿名客服规则校正；不同工作副本的“已实现”状态未直接转为本目录事实。

## 阅读与联动口径

当前本地教务/CRM、faster-whisper及个人页站内通知方案见第八章；配置与运行待办统一见末章。此前静态核对记录不代表已完成服务、数据库或真实Dify联调；配置内容只列变量名与状态，不写真实密钥。

本轮权限修订以用户确认和“业务文档/06开发文档/个人开发文档/”九份文件为新增依据。当前目标集中见第二章权限矩阵，来源见第十一章，剩余权限问题见末章。历史来源中的“报告仅admin”不再作为当前授权目标；公共/客服等实现状态仍须独立核验。

第一至第七章保持 mrz.md 的主体结构，每章先写公共模块，再纳入客服对应内容。第八章说明调用、权限、事务和前后端联动；第九章补齐公共账号及其外键依赖表；第十章列出文件、接口和字段完整性核对及待接通项。第十一至第十五章补充基线核对、文件冲突处理、实施验收、条件迁移/回滚及兼容性要求，供后续真实代码合并使用。

客服六个现有接口继续匿名开放，不因合并公共鉴权而新增登录门槛。JWT 与逐接口权限依赖用于明确受保护的接口；公共账号权限不赋予访客客服管理能力。未来若增加客服管理接口，须另定 URL 和权限，本文件不虚构这些接口。


### 上一轮客户研判内容的合并口径（历史范围）

本次以本文件原内容为主体，补充 `业务文档/09杂谈/操作文档个人版/sgtallm.md` 中的客户研判方案。原第一至十五章结构、公共及客服完整字段、文件清单、实现差异和可选联动限制保留；新增研判内容按功能、权限、Dify、目录、联动、字段、实施与回滚归入对应章节，文件末章统一列出剩余冲突与待办。

当前来源记录的公共/客服接口共 9 个；新增规划研判接口 8 个，规划合计 17 个。原 11 张相关表加规划研判 5 表合计 16 张相关表。两个合计都不是已实现、已挂载或已建表的证明。旧来源未列研判负责人姓名；用户现明确研判业务负责人为客户顾问，按对应客户的有效顾问关联定位，不虚构开发人员姓名。

新增文档中的“解决方式”仍需核对可执行性：尤其员工角色权限无法仅靠业务校验跨过现有公共权限依赖，当前公共依赖不展开通配权限；涉及这些问题的新增内容均为提案，以第十八章未决项为约束。

### 上一轮智能报告内容的合并口径（历史范围）

本轮以包含客户研判的现有主文档为主体，合并 `业务文档/09杂谈/操作文档个人版/cyl合并后.md`。原第一至十五章业务内容保留，报告内容归入对应功能、权限、目录、联动、字段、实施和迁移章节；历次问题在文件末章去重归并，已确认事项移出问题清单。

四模块规划包括公共3、客服6、研判8、报告5，共22个预期接口操作；直接相关表范围为原16加报告3，共19张。报告另消费六张只读上游，部分尚未落地；不把这些范围数字当成当前已注册接口或已建表数量。报告三表只有37个字段名称，类型与约束缺失，不能沿用来源“完整字段已在主文档”的循环引用。

历史报告来源曾提出“仅admin”；用户现已确认报告只允许平台管理员和部门主管访问，以第二章当前权限清单为准。普通员工不因employee身份取得报告权限；部门主管仅查看本部门报告，平台管理员可查看/生成全公司及所有部门报告并管理报告配置，精确权限接入和研判上游适配的剩余事项见末章。原有客服匿名及研判受保护边界继续保留。本轮只修改文档，不实施代码、授权、数据库或调度变更。

### 企业管理与学生智能助手（本轮累计合并）

本轮以含公共、客服、客户研判、智能报告的现有主体，合并msj_jlj_原文无损合并.md中的企业和学生两部分。企业／学生与此前各模块的剩余问题在文件末章按主题去重并连续编号。

企业12节正文、15表字段字典及旧请假结构参考、学生8章正文及七表73字段全部按主题纳入原章节。两份相同联合协作契约V1去重后完整保留于第十六章；原章号在标注E（企业）/S（学生）的段内指来源自身章节，不误指本主文档。

六模块按表名去重的直接相关规划范围为36张；联合22表/43条物理FK是企业学生子范围，报告customer_judgement等额外缺失依赖继续保留。学生21+老师10+服务同步3为34方法，企业复述的请假/老师方法不重复计数；企业组合接口须按真实方法路径拆分，不宣称全系统已注册总数。

共同目标为公共人员JWT、单请假事实表及唯一固定服务、写动作模型提取与确认、企业NL2SQL只读、学生固定查询、报告只读上游。同步服务凭据是人员认证之外的明确分支；目标权限、物理外键、统一HTTP200及通知代次均未实施，本轮不修改代码/配置/SQL/数据库或启动任务。

### 本轮补充：各模块大模型调用

按操作文档个人版目录中除cyl合并后.md、msj_jlj_原文无损合并.md之外的8份文件补充第五章，集中列业务触发入口、服务/适配器、Dify路径、输入输出、模型/应用Key、DSL与失败处理。模型调用差异与此前问题统一在文件末章归并，不再叠加历史问题数量。新查明企业个人原文负责人为莫世杰。

本轮排除的两份文件只是不作为新增取材，不删除其既有合并内容或原文件。读取源文档不代表复核真实代码/配置/模型，详细来源和未决信息见第五章新总览。

## 一、模块功能以及对应的接口和对应的数据库表

### 公共模块（主体）

本模块提供三个对外 HTTP 接口，以及供每个业务接口复用的 JWT 认证、鉴权中间件、日志、统一返回和本地 Dify HTTP 请求工具。身份认证采用 JWT；每个受保护的业务接口分别声明所需权限并接入公共鉴权中间件，通过后才能执行具体业务。

#### 1. 对外 HTTP 功能接口

| 功能 | 接口 | 调用用户 / 认证要求 | 对应数据库表或资源 | 功能说明 |
| --- | --- | --- | --- | --- |
| JWT 登录 | `POST /api/v1/auth/login` | 允许未登录用户提交账号密码 | `user_account` | 校验用户名及密码哈希，签发有有效期的 JWT；返回 `access_token`、`token_type`、`expires_in` |
| 公开访问清单 | `GET /api/v1/auth/public-access` | 无需 JWT | `app/access_control.yaml` | 返回允许匿名访问的页面和模块信息 |
| 当前用户权限清单 | `GET /api/v1/auth/me/access` | 必须携带有效 Bearer JWT | `user_account`、`app/access_control.yaml` | 通过 JWT 确认当前账号，读取用户表身份并映射权限，返回本人的身份、权限、可访问页面和模块；不代替各业务接口的权限校验 |

#### 2. 供各业务接口调用的公共功能

| 功能 | 公共接口 / 接入方式 | 调用方 | 对应数据库表或资源 | 功能说明 |
| --- | --- | --- | --- | --- |
| JWT 签发和解析 | `create_access_token(account)`、`decode_access_token(token)` | 登录服务、公共认证组件 | 用户主键、`AUTH_SECRET_KEY`、Token 有效期配置 | 签发 JWT；解析时验证签名和有效期，提取用户 ID；无效 Token 不建立有效身份 |
| JWT 身份认证 | `Depends(get_current_account)` | 仅需登录的接口；鉴权中间件内部复用 | `user_account` | 从 `Authorization: Bearer <access_token>` 获取 JWT，验证后查询真实账号及身份；不直接以客户端传入身份判断权限 |
| 逐接口权限鉴权中间件 | `Depends(require_permission("接口权限标识"))` | 每个需要权限控制的业务接口 | `user_account.identity_type`、`app/access_control.yaml` | 接口声明需要的权限；组件先验证 JWT，再按用户表身份映射权限，允许或拒绝调用；未认证按 401、无权限按 403 处理，响应方式见第四节 |
| 权限计算与访问清单 | `permissions_for(identity_type)`、`access_for(identity_type, user_id)` | 公共鉴权组件、当前用户权限接口 | `app/access_control.yaml`；身份由可信用户记录取得 | 计算当前身份的权限和可见页面/模块，不接受前端自报权限作为授权依据 |
| 日志生成 | `init_logger()`、`get_logger(name)` | 应用入口、各业务接口和服务 | 本地 `app/logs/` 或 `LOG_DIR` | 统一初始化日志，记录时间、级别、模块、行号、处理信息及异常堆栈 |
| 统一返回格式 | `success(data)`、`fail(code, message, data)`、`ResponseModel` | 各业务 HTTP 接口 | 无专属表 | 将成功或失败结果组织为 `code/message/data`；Dify 原始结果先由业务适配器解析 |
| 全局异常处理 | `BusinessException`、`register_exception_handlers(app)` | 应用入口、各业务服务 | 日志文件；无专属表 | 收敛业务异常和未处理异常；当前 HTTP/参数校验异常统一范围见第四节 |
| 本地 Dify HTTP 请求 | `DifyHttpClient.post_json_sync(path, api_key=..., payload=...)`、`await client.post_json(path, api_key=..., payload=...)` | 各业务自己的 Dify 应用适配器 | 本地 Dify 地址、各业务应用 API Key；无专属表 | 只封装同步/异步 JSON POST、Bearer 请求头、超时、HTTP 状态检查和 JSON 解析；模型、工作流、请求业务字段和输出校验由各业务负责 |
| 数据库连接和请求级会话 | `engine`、`SessionLocal`、`Base`、`get_db()`、`dispose_db()` | 各业务接口、数据库访问层、应用生命周期 | 公共数据库连接；各业务模型共用 ORM 基类 | 统一连接池、请求会话、异常回滚及资源释放；业务服务负责明确提交事务，不自动建表 |
| 统一配置管理 | `app/config.py` 中的配置对象 | 所有后端公共组件和业务适配器 | 项目根目录 `.env` | 统一读取数据库、日志、JWT 和各业务 Dify 应用配置 |
| 密码哈希与校验 | `hash_password()`、`verify_password()`、`authenticate()` | 账号初始化、登录认证服务 | `user_account.password_hash` | 账号密码以哈希保存，登录验证哈希；Token 签发/解析复用上方 JWT 公共能力 |
| 请求参数校验与公共响应模型 | Pydantic 请求模型、`LoginRequest`、`ResponseModel` | 各业务接口 | 无专属表；参数和结果结构 | 公共层提供登录请求校验和通用响应模型，各业务声明自己的请求字段约束 |

鉴权中间件在当前 FastAPI 项目中通过依赖注入接入，每个受保护接口使用 `Depends(require_permission(...))`，无需新增一个供前端单独请求的“鉴权 HTTP 接口”。公共层验证身份和接口权限，各业务服务继续校验具体记录的数据归属、部门/学生关系、分派和业务状态。

上表中的公共方法不等于已经被所有业务接口接入；各业务需在对应接口中显式声明依赖。JWT、日志、统一返回和 Dify HTTP 请求能力均复用公共组件。

### 客服模块（合并内容）

模块覆盖公司信息咨询、公司业务查询、海外留学政策查询、课程与项目推荐、活动与讲座报名、FAQ 自助解答及日常闲聊七类场景。对外共六个 HTTP 接口，基础前缀为 `/api/v1`，只有客服对话入口涉及 AI 调用，其余接口访问业务数据库。

#### 1. 对外 HTTP 功能接口

| 功能 | 接口 | 调用用户 / 认证要求 | 对应数据库表或资源 | 功能说明 |
| --- | --- | --- | --- | --- |
| 客服对话 | `POST /api/v1/agent/chat` | 所有人，允许匿名，无需 JWT | `chat_session`、`chat_message`；Dify 客服应用 | 接收消息，编排意图识别与回复，保存会话/消息，返回意图、回复及前端动作；模型调用失败提供兜底话术 |
| 活动列表 | `GET /api/v1/agent/events` | 所有人，允许匿名，无需 JWT | `lecture_event` | 查询活动，支持按 status 筛选，例如报名中 |
| 活动详情 | `GET /api/v1/agent/events/{event_id}` | 所有人，允许匿名，无需 JWT | `lecture_event` | 按活动 ID 返回详情；列表字段足够时前端可不额外调用 |
| 活动报名 | `POST /api/v1/agent/events/signup` | 所有人，允许匿名，无需 JWT | `lecture_event`、`event_signup` | 校验活动及有效报名记录，写入报名并更新人数；源文档另要求状态、名额、行锁与事务保护，落实情况见第六章“客服模块”交付核对 |
| 课程列表 | `GET /api/v1/agent/courses` | 所有人，允许匿名，无需 JWT | `course_project` | 仅返回上架课程，支持 category 筛选；为课程推荐动作提供真实课程数据 |
| FAQ 查询 | `GET /api/v1/agent/faq` | 所有人，允许匿名，无需 JWT | `faq` | 关键词模糊匹配，未命中返回第一条；主要问答由 Dify FAQ 知识库承担，此接口为数据库兜底 |

#### 2. 模块内部功能与公共能力接入

| 功能 | 公共方法 / 调用位置 | 调用方 | 对应数据库表或资源 | 功能说明 |
| --- | --- | --- | --- | --- |
| 会话及消息管理 | `run_chat()`、`_ensure_session()` | 客服对话接口 | `chat_session`、`chat_message` | 复用或新建会话，保存用户及助手消息；源文档要求用户消息先提交，避免模型失败丢失记录 |
| Dify 客户端选择 | `get_dify_client()`、MockDifyClient、RealDifyClient | 客服对话服务 | DIFY_CLIENT 等后端配置 | 源文档定义 mock / real 切换；当前 real 实现差异见第六章“客服模块”交付核对 |
| 意图及前端动作 | 客服 Dify 场景客户端 | 对话服务及前端 | intent、reply、need_action、action | 课程推荐引导 show_courses，活动查询引导 show_events；前端再请求课程或活动接口 |
| 报名校验和处理 | `signup()` | 活动报名接口 | `lecture_event`、`event_signup` | 按活动和手机号检查有效报名，执行报名写入；取消后是否可重新报名按报名状态判断 |
| 参数及结果模型 | `app/schemas/agent.py` | 六个客服接口 | 无专属表 | 定义对话、活动、报名、课程及 FAQ 的请求/响应字段 |
| 数据库会话 | 公共 `get_db` 依赖 | 客服路由和服务 | MySQL；六张客服表 | 复用公共连接和请求级会话，业务服务负责事务写入 |
| 日志及异常 | 公共日志工具、统一异常组件 | 客服业务服务 | 本地运行日志 | 记录 Dify 调用失败等异常，复用公共日志及错误处理 |
| 统一响应 | `success()`、ResponseModel、BusinessException | 客服 HTTP 接口 | 无专属表 | 采用 code、message、data 响应结构 |
| Dify HTTP 传输 | 源文档指定 `DifyHttpClient` | real 客服场景客户端 | 本地 Dify API | 复用公共 JSON POST、Bearer 应用 Key、超时及 HTTP 错误检查；场景输入和输出解析由客服模块负责 |

#### 3. 数据表及用途

| 数据库表 | 功能作用 | 主要数据 |
| --- | --- | --- |
| `course_project` | 课程项目数据源 | 名称、类别、适用人群、简介、地点、报名方式和状态 |
| `lecture_event` | 讲座活动数据源 | 名称、类型、时间地点、名额、已报名人数和状态 |
| `event_signup` | 活动报名记录 | 活动 ID、姓名、手机号、扩展信息、报名时间及有效/取消状态 |
| `faq` | 数据库标准问答及兜底 | 问题、答案和分类 |
| `chat_session` | 客服会话 | 会话 UUID、访客标识和渠道 |
| `chat_message` | 客服对话历史 | 会话 ID、用户/助手角色、意图标签及消息内容 |

按源总览的报名约定，以活动 ID、手机号及有效状态进行状态式判重，不使用活动 ID 与手机号的永久组合唯一约束，以便取消后重新报名。实际约束、并发保护和业务实现仍应对照当前统一 DDL 与服务代码核验。

#### 4. 六张业务表的完整字段

以下字段仅摘录自《客服Agent实现方案.md》第四章，保留字段名称、类型、可空性、默认值、说明及索引/外键约束；未读取其他文件，也未据此核验数据库或代码。默认值中的“—”表示方案未列出默认值，两个单引号表示空字符串，NULL 表示空值。原有用途概述为业务说明，实际字段清单以下表为准。
##### 4.1 课程项目表 `course_project`

存课程/项目（留学申请、背景提升、语言培训三大类），课程推荐分支的数据源。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| id | BIGINT | 否 | 自增 | 主键 |
| course_name | VARCHAR(128) | 否 | — | 课程名称 |
| category | VARCHAR(32) | 否 | — | 类别：留学申请/背景提升/语言培训 |
| target_audience | VARCHAR(128) | 否 | '' | 适用人群（学历/意向国家等） |
| description | TEXT | 否 | — | 课程简介 |
| location | VARCHAR(128) | 否 | '' | 上课地点 |
| signup_method | VARCHAR(128) | 否 | '' | 报名方式 |
| status | VARCHAR(32) | 否 | '上架' | 状态：上架/下架（仅上架对访客可见） |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间 |
| updated_at | DATETIME(3) | 否 | 当前时间，更新时自动刷新 | 更新时间 |

- 索引：`idx_category_status (category, status)`、`idx_status_time (status, created_at)`——支撑按类别筛选 + 仅取上架的查询。

##### 4.2 讲座活动表 `lecture_event`

存近期讲座/分享会/见面会；`quota` 名额上限，`signed_count` 实时已报名人数（报名成功由接口 +1），`status` 控制能否报名。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| id | BIGINT | 否 | 自增 | 主键 |
| event_name | VARCHAR(128) | 否 | — | 活动名称 |
| event_type | VARCHAR(16) | 否 | — | 线上/线下 |
| start_time | DATETIME | 否 | — | 开始时间 |
| location | VARCHAR(128) | 否 | '' | 地点 |
| signup_method | VARCHAR(128) | 否 | '' | 报名方式 |
| quota | INT | 否 | 0 | 名额（0 表示不限） |
| signed_count | INT | 否 | 0 | 已报名人数 |
| status | VARCHAR(32) | 否 | '报名中' | 状态：报名中/已满/已结束 |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间 |
| updated_at | DATETIME(3) | 否 | 当前时间，更新时自动刷新 | 更新时间 |

- 索引：`idx_status_start (status, start_time)`——支撑「报名中 + 按时间排序」的列表查询；`idx_start_time (start_time)`。

##### 4.3 活动报名表 `event_signup`

访客在对话中完成报名的落库记录，是「报名闭环」的凭证。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| id | BIGINT | 否 | 自增 | 主键 |
| event_id | BIGINT | 否 | — | 活动ID（外键 → `lecture_event.id`） |
| customer_name | VARCHAR(64) | 否 | — | 客户姓名 |
| customer_phone | VARCHAR(32) | 否 | — | 客户手机号（判重依据） |
| customer_info | JSON | 是 | NULL | 客户扩展信息（意向国家、学历等） |
| signup_time | DATETIME | 否 | 当前时间 | 报名时间 |
| source | VARCHAR(32) | 否 | '客服对话' | 来源渠道 |
| status | VARCHAR(32) | 否 | '有效' | 状态：有效/取消 |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间 |

- 外键：`fk_signup_event (event_id) → lecture_event(id)`。
- 索引：`idx_event_status (event_id, status)`、`idx_signup_time (signup_time)`。
- **去重策略（重要，已变更）**：**不建 `(event_id, customer_phone)` 唯一约束**，改为**状态式去重**——仅当存在 `status=有效` 的报名记录时才拒绝；用户取消报名（`status=取消`）后可重新报名。早期方案用数据库唯一约束，会导致「取消后再报名」撞索引，故废弃。

##### 4.4 FAQ 问答对表 `faq`

存申请流程、费用、退费等高频问题标准答案，供 FAQ 兜底查询（知识库未覆盖时兜底）。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| id | BIGINT | 否 | 自增 | 主键 |
| question | TEXT | 否 | — | 问题 |
| answer | TEXT | 否 | — | 答案 |
| category | VARCHAR(32) | 否 | '' | 分类 |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间 |

- 索引：`idx_category (category)`。

##### 4.5 客服会话表 `chat_session`

一个访客一次进店咨询 = 一条会话；`session_id`（UUID）是贯穿多轮对话的主线，前端首访不带、之后带回即可续上同一会话。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| id | BIGINT | 否 | 自增 | 主键 |
| session_id | VARCHAR(64) | 否 | — | 会话唯一标识（UUID），**唯一索引 `uk_session_id`** |
| user_id | VARCHAR(64) | 否 | '' | 访客标识（匿名或留资后） |
| channel | VARCHAR(32) | 否 | 'web' | 渠道（web 等） |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间 |
| updated_at | DATETIME(3) | 否 | 当前时间，更新时自动刷新 | 更新时间 |

- 索引：`uk_session_id (session_id)` 唯一索引、`idx_user_id (user_id)`、`idx_updated_at (updated_at)`。

##### 4.6 客服消息表 `chat_message`

会话内每一条消息，`intent` 记录 Dify 识别的意图，用于审计、意图分布统计与对话追溯。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| id | BIGINT | 否 | 自增 | 主键 |
| session_id | VARCHAR(64) | 否 | — | 关联会话（外键 → `chat_session.session_id`） |
| role | VARCHAR(16) | 否 | — | user / assistant |
| intent | VARCHAR(32) | 否 | '' | 意图标签（由 Dify 返回；兜底时为空） |
| content | TEXT | 否 | — | 消息内容 |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间 |

- 外键：`fk_message_session (session_id) → chat_session(session_id)`。
- 索引：`idx_session_time (session_id, created_at)`——按会话取历史消息；`idx_intent (intent)`——意图统计。
- **实现注意**：ORM 未声明外键关系，插入时必须保证父行（`chat_session`）先落库——`_ensure_session` 新建会话后立即 `flush`，否则同事务内 INSERT 顺序不定会触发外键违例。

方案另说明：knowledge_vector 知识库向量数据存储在 Dify 侧，后端本期不建该表；方案未提供其字段定义，本文不补写。

### 客户信息研判模块（本次新增，规划口径）

来源：`sgtallm.md` 第一章及第四章 4.1。以下是新增设计，不替代本章既有接口与字段，也不表示已经交付。

| 模块 | 来源 | 接口 | 数据库表 | 鉴权方式 |
| --- | --- | --- | --- | --- |
| 公共基础能力 | 主文档（主体） | `POST /api/v1/auth/login`、`GET /api/v1/auth/public-access`、`GET /api/v1/auth/me/access` | `user_account`、`org_department`、`employee`、`customer_profile`、`student_profile`（及外键依赖） | JWT + `Depends(require_permission(...))` |
| 客服 Agent | 主文档（已合并） | `agent/chat`、`agent/events`、`agent/events/{id}`、`agent/events/signup`、`agent/courses`、`agent/faq` | `course_project`、`lecture_event`、`event_signup`、`faq`、`chat_session`、`chat_message` | 匿名开放，无需 JWT |
| 客户信息研判 | sgt.md（本次合并） | `customer/sources`、`customer/sources/{id}/parse`、`customer/judge`、`customer/judge/batch`、`customer/results/{id}`、`customer/results`、`customer/rules`（GET/PUT） | `customer_source`、`customer_info`、`research_rule`、`product`、`research_result` | JWT + `require_permission(customer.*)` |

客户研判的八个接口为基础前缀 `/api/v1` 下的受保护接口，需登录并具备对应 `customer.*` 权限；不与客服六个匿名接口混用授权规则。客户研判为全新模块（sgt.md 标注「规划中」），本次合并以「新增表 + 新增接口 + 接入公共能力」为主，不改造存量客服与公共契约。

#### 三模块职责与公共能力复用

| 模块 | 核心功能 | 对外接口 | 复用的公共能力 |
| --- | --- | --- | --- |
| 公共基础能力 | 登录认证、逐接口鉴权、日志、统一返回、Dify HTTP、数据库会话、配置 | 3 个 auth 接口 | —（自身提供） |
| 客服 Agent | 咨询、课程/活动查询、报名、FAQ、会话消息 | 6 个 agent 接口（匿名） | get_db、日志、统一返回、Dify HTTP、配置 |
| 客户信息研判 | 信息接入、多格式解析、关键字段提取、画像研判、结果输出、规则维护 | 8 个 customer 接口（受保护） | JWT 鉴权、get_db、日志、统一返回、Dify HTTP（可选）、配置 |

#### 八个研判接口与权限对应关系（规划）

| 方法及完整路径 | 功能 | 声明权限 | 备注 |
| --- | --- | --- | --- |
| `POST /api/v1/customer/sources` | 接入文本、PDF、Excel 来源 | `customer.source.create` | 上传协议、文件限制及返回字段见第十八章第024项 |
| `POST /api/v1/customer/sources/{id}/parse` | 解析来源并提取结构化字段 | `customer.source.parse` | — |
| `POST /api/v1/customer/judge` | 单条研判 | `customer.judge.create` | 命中和未命中均为正常业务结果 |
| `POST /api/v1/customer/judge/batch` | 批量研判 | `customer.judge.batch` | — |
| `GET /api/v1/customer/results/{id}` | 结果详情 | `customer.result.read` | 校验记录访问范围 |
| `GET /api/v1/customer/results` | 结果列表 | `customer.result.read` | 按第二章数据范围读取 |
| `GET /api/v1/customer/rules` | 读取规则 | `customer.rule.read` | — |
| `PUT /api/v1/customer/rules` | 维护规则并生成新版本 | `customer.rule.manage` | 旧版本保留 |

前四个接口的方法及路径、结果详情和规则 GET/PUT 来自新增文档调用流程；结果列表 GET 依据其接口清单及查询语义展开，为待接口负责人确认的契约。源文档八接口与七权限分别计数，不将相同 URL 的 GET/PUT 算为同一个操作。

### 智能报告模块（本轮新增）

来源：`cyl合并后.md` 第一、四章；负责人：陈宇林。报告方案定位为仅平台管理员和部门主管可访问的数据消费模块（按用户本轮确认；历史来源“管理员专属”已被此口径更新），只读上游、计算固定指标、调用报告 Workflow 撰写分析，将正文与指标保存到报告三表。除生成链路外，查询与配置操作不直接调用 Dify。

本轮保留客户研判八接口与五表；报告来源只合并过公共、客服、报告三个模块，不能用其目录或统计覆盖上一轮研判内容。下列均为文档设计或来源状态，未核验代码与运行环境。

#### 报告五接口及权限关系（当前文档目标）

路径与权限名沿用第五章已补充的报告调用契约；访问人群以用户本轮确认为准，配置职责依据《开发文档-Albert2.md》1.4、8.1。下表为开发目标，未修改真实路由、YAML或授权代码。

| 功能 | 方法及路径 | 动作权限 | 允许角色及范围 |
| --- | --- | --- | --- |
| 异步生成报告 | `POST /api/v1/report/generate` | `report.generate` | 仅平台管理员；可生成全公司及各部门报告；部门主管禁止手动生成 |
| 查询单份报告 | `GET /api/v1/report/{report_record_id}` | `report.read` | 平台管理员、部门主管；主管仅本部门授权报告；全公司报告不能仅靠过滤列表后直接读正文 |
| 报告列表 | `GET /api/v1/report/list` | `report.read` | 同详情的数据范围，只给授权元数据，total也受范围约束 |
| 读取报告配置 | `GET /api/v1/report/configs` | `report.config.read` | 平台管理员；部门主管不因可读报告而自动取得配置接口权限 |
| 修改报告配置 | `PUT /api/v1/report/configs/{report_code}` | `report.config.write` | 平台管理员；字段、版本及审计校验仍待实现 |

报告只消费经授权的上游数据。心理周报采用匿名聚合，报告访问权不授予心理原文、个人预警或请假审批能力。用户已明确主管只能查看，平台管理员可执行全部报告操作并访问全公司及所有部门报告。报告记录如何保存/验证范围仍待结构方案与实现，不擅增数据库字段；权限结论见第二章。

#### 来源合并概览（保留原范围）
| 项目 | 内容 |
| --- | --- |
| 主体 | 公共登录与权限入口（公共基础能力），为所有业务接口提供 JWT、鉴权、日志、统一返回、数据库会话、本地 Dify HTTP 传输 |
| 合并模块 1 | 客服 Agent（对外开放模块）：六个匿名接口，只有对话入口调用 Dify |
| 合并模块 2 | 智能报告（管理层报告模块）：五个接口；访问限平台管理员和部门主管，动作分工见当前权限清单，只有生成链路调用 Dify |
| 统一目录 | `D:\AI\StuProject` |
| 输出 | 合并后的 `马睿智/操作文档.md` + 本 allm.md |

**访问模型对照：** 客服模块「匿名开放」，不接公共 JWT；智能报告「平台管理员和部门主管可访问」，复用公共 JWT、逐动作授权及数据范围校验。报告配置限平台管理员；普通员工、客户、学生与匿名访客不得因公共入口或客服会话取得报告权限。

上表“输出主文档 + 本 allm.md”为报告来源原交付口径，本轮只更新用户指定的主操作文档，`cyl合并后.md` 保留不变，不另建或覆盖 allm.md。

### 企业 E1：业务范围与职责

来源：`msj_jlj_原文无损合并.md` 的企业 E1：业务范围与职责。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

项目服务留学咨询与学生服务机构，包含客户研判、客服 Agent、企业智能助手、学生智能助手、智能报告五个模块。企业管理模块面向内部员工，负责把客户跟进、日报、教务和售后处理串联起来。

企业管理对应企业智能助手。用户本轮选择用本项目前端、FastAPI和本地MySQL管理所需教务及CRM数据；当前范围包括课程/成绩/学业节点、客户/跟进/申请进度，不扩展为完整商业CRM、招生收费、财务或人事薪酬平台。历史“不建教务/CRM本体”的外部依赖口径由此更新，已确认的数据权限继续适用。

| 业务 | 企业管理负责的功能 | 与其他模块的边界 |
| --- | --- | --- |
| 意向客户 | 文字/语音录入、档案查询、追加跟进、状态更新、归档及申请进度维护 | 当前采用本地CRM页面及固定后端服务，共用客户主档；客服/研判只按原授权供线索，未来外部CRM适配保留为可选 |
| 员工日报 | 口述/文字提取、本人提交与修订、管理者按部门查阅 | 正式日/周汇总报告交给智能报告模块；不重复建设报告表 |
| 组织查询 | 部门层级、职能、员工工作联系方式 | 复用组织主数据，不承担薪酬、人事流程 |
| 新人指引 | 标准 QA、制度文档 RAG、答案来源及版本 | 资料由企业维护；没有来源不生成确定性制度结论 |
| 学生成绩 | 授权学生/课程的录入、查询、更正、作废 | 复用学生主档；外部教务仅提供只读接口时，不提供本地修改冒充教务成功 |
| 学生请假 | 老师待办、详情、审批结果展示与审批入口 | 统一账号 JWT；学生提交与老师审批共用 `student_admin_service` 和固定业务服务，旧契约适配见第 2、6 节 |
| 投诉反馈 | 工单查询、分派、跟进、给出解决方案 | 学生提交、确认解决、重开及评价由学生模块负责；共用同一工单 |
| 主动待办 | 客户跟进提醒、待审批请假、待处理投诉、站内通知 | 定时任务只生成提醒，不自动代替员工审批或处理业务 |

语音输入先转写成文本，再进入与文字相同的处理链。第一阶段可先接收已有转写文本；真实音频上传与转写适配作为同一需求的后续交付，不把“能提交文字”当作语音功能已经完成。


### 企业 E6：完整接口、权限及固定审批服务契约

来源：`msj_jlj_原文无损合并.md` 的企业 E6：完整接口、权限及固定审批服务契约。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

#### 6.1 企业模块拟实现/复用的接口

下表以 `/api/v1/enterprise` 为统一前缀，**路径列均为此前缀后的相对路径**。除明确注明既有登录外，本节为目标接口清单，不代表本地已经全部实现。保留早期企业接口的 `customer`、`daily-report`、`nl2sql`、`command` 命名。

“全体员工”指通过有效状态检查的业务员工；“配置管理员”指员工业务角色 `admin`。客户权限范围见第 5 节，不能因为接口列了主管就读取其他部门。

| 方法 | 相对路径 | 作用/权限标识 | 允许角色与范围 |
| --- | --- | --- | --- |
| GET | `/me/permissions` | 当前权限 `enterprise.access` | 全体员工，本人 |
| GET | `/customer`、`/customer/{customer_id}` | 客户列表/详情 `enterprise.customer.read` | 顾问本人客户；主管本部门客户 |
| POST | `/customer` | 新增 `enterprise.customer.create` | 顾问本人；主管本部门，指定负责人必须是本部门有效顾问 |
| PUT | `/customer/{customer_id}` | 修改普通资料 `enterprise.customer.update` | 顾问本人；主管本部门；不接受角色/归属等越权字段 |
| PUT | `/customer/{customer_id}/status` | 状态更新 `enterprise.customer.status` | 顾问本人；主管本部门 |
| POST | `/customer/{customer_id}/assign` | 转派 `enterprise.customer.assign` | 主管本部门；目标顾问同部门 |
| DELETE | `/customer/{customer_id}` | 归档 `enterprise.customer.archive` | 顾问本人；主管本部门；不是物理删除 |
| GET | `/customer/{customer_id}/followups` | 跟进查询 `enterprise.customer.read` | 可读该客户者 |
| POST | `/customer/{customer_id}/followups` | 追加跟进 `enterprise.customer.followup` | 可写该客户者；记录实际操作者 |
| PUT | `/customer/{customer_id}/followups/{followup_id}/schedule` | 完成/取消下次跟进安排 `enterprise.customer.followup` | 可写该客户者；不覆盖历史沟通原文 |
| POST | `/daily-report` | 提交本人日报 `enterprise.daily.write_own` | 全体员工，仅本人；同一日期不重复新增 |
| GET | `/daily-report`、`/daily-report/{report_id}` | 日报查阅 `enterprise.daily.read` | 本人；主管按提交部门快照读取本部门 |
| PUT | `/daily-report/{report_id}` | 修订 `enterprise.daily.write_own` | 仅原作者，版本校验 |
| DELETE | `/daily-report/{report_id}` | 作废 `enterprise.daily.write_own` | 仅原作者，原因必填，保留历史 |
| POST | `/daily-report/summary` | 部门即时汇总 `enterprise.daily.summary` | 主管本部门；只基于授权已提交内容，不代替正式报告模块 |
| GET | `/organization`、`/employees` | 部门树/通讯录 `enterprise.organization.read` | 全体员工，工作信息白名单 |
| GET | `/students`、`/students/{student_id}` | 学生最小档案 `enterprise.student.read` | 班主任/服务人员按有效关系；教务按成绩关系；配置管理员的维护视图只给必要主档字段 |
| GET | `/scores`、`/scores/{score_id}` | 成绩查询 `enterprise.score.read` | 班主任所负责学生；教务的学生/课程范围 |
| POST | `/scores` | 成绩录入 `enterprise.score.write` | 教务，学生与课程绑定有效 |
| PUT | `/scores/{score_id}` | 更正 `enterprise.score.write` | 教务，范围有效，更正原因必填 |
| DELETE | `/scores/{score_id}` | 作废 `enterprise.score.void` | 教务，范围有效，作废原因必填 |
| GET | `/tickets`、`/tickets/{ticket_id}` | 投诉列表/详情 `enterprise.ticket.read` | 老师本人被分派且关系有效的工单；主管本部门 |
| POST | `/tickets/{ticket_id}/assign` | 分派 `enterprise.ticket.assign` | 主管本部门，目标处理人有效且有学生服务关系 |
| POST | `/tickets/{ticket_id}/followups` | 人工跟进 `enterprise.ticket.handle` | 当前处理老师；主管如需亲自办理先按规则分派给本人并具备所需关系 |
| POST | `/tickets/{ticket_id}/resolve` | 给出方案 `enterprise.ticket.handle` | 当前处理老师；转为 `awaiting_student`，不直接关闭 |
| GET | `/knowledge`、`/knowledge/{knowledge_id}` | 知识查询 `enterprise.knowledge.read` | 全体员工；全员或本人部门可见、已发布且生效 |
| POST | `/onboarding/ask` | QA/RAG `enterprise.knowledge.read` | 全体员工；检索前限定部门和可见版本 |
| GET | `/todos` | 待办聚合 `enterprise.todo.read_own` | 全体员工，仅本人有权处理的事项 |
| GET | `/notifications` | 企业消息 `enterprise.notification.read_own` | 全体员工，仅本人企业模块消息 |
| POST | `/notifications/{notification_id}/read` | 已读 `enterprise.notification.read_own` | 本人接收的消息；不等于业务处理完成 |
| POST | `/nl2sql` | 自然语言只读查询 `enterprise.query` | 全体员工，但具体对象仍需客户/日报/成绩等权限 |
| POST | `/command` | 提取动作并生成预览 `enterprise.command` | 全体员工，按目标业务动作授权；不写库 |
| POST | `/command/confirm` | 确认并调用固定服务 `enterprise.command` + 目标动作权限 | 同一员工，重新校验权限、版本、有效期及参数摘要 |
| POST / PUT / DELETE | `/departments`、`/departments/{department_id}` | 部门新增/修改/停用 `enterprise.organization.manage` | 配置管理员；禁止成环，停用前检查有效员工与业务关联 |
| POST / PUT | `/employees`、`/employees/{employee_id}` | 员工资料维护 `enterprise.employee.manage` | 配置管理员；密码和系统账号由公共认证模块管理 |
| PUT | `/employees/{employee_id}/roles` | 角色配置 `enterprise.role.manage` | 配置管理员，完整审计；普通资料接口不能顺带改角色 |
| POST / PUT / DELETE | `/student-bindings`、`/student-bindings/{binding_id}` | 新增/修改/停用绑定 `enterprise.binding.manage` | 配置管理员；学生/员工存在、课程与关系有效 |
| POST / PUT / DELETE | `/knowledge`、`/knowledge/{knowledge_id}` | 新增/编辑草稿/停用 `enterprise.knowledge.manage` | 配置管理员，版本变化后重新审核与索引 |
| POST | `/knowledge/{knowledge_id}/publish` | 审核发布 `enterprise.knowledge.publish` | 配置管理员，审核信息及索引就绪；不得由模型直接发布 |
| GET | `/operation-logs` | 企业审计 `enterprise.audit.read` | 配置管理员，仅企业事件，敏感快照脱敏，不读取学生心理处置原文 |

组合行中的集合路径用于 POST，`/{id}` 用于 PUT/DELETE，不意味着对每个路径开放所有列出的方法。配置维护接口可后于核心业务交付，角色与数据基础可先由受控初始化数据提供。

#### 6.2 学生协作接口与请假目标契约

以下全部路径由学生模块开发和注册，企业只维护调用方，不另建 `enterprise_student.py` 重复注册。全部为待测试目标，具体字段与权限见附录 B。本轮只改两份协作文档。

| 方法 | 完整路径 | 主体与范围 |
| --- | --- | --- |
| GET | `/api/v1/internal/student/leave` | 统一 JWT + 审批权限 + 有效班主任关系；按当前 `reviewer_id` 查询本人的请假，目标筛选参数为 `approval_status` |
| GET | `/api/v1/internal/student/leave/{apply_id}` | 同上，`apply_id=student_admin_service.id`，返回最新 `row_version` |
| POST | `/api/v1/internal/student/leave/{apply_id}/decision` | 同一指定班主任；请求含 `expected_version`、`decision`、`comment` 与幂等头；调用共享固定审批服务 |
| GET | `/api/v1/internal/student/notifications` | 当前老师的学生模块通知 |
| POST | `/api/v1/internal/student/notifications/{notification_id}/read` | 本人通知已读 |
| GET | `/api/v1/internal/student/warnings` | 授权老师；学生心理协作入口，非通用员工查询 |
| GET | `/api/v1/internal/student/warnings/{warning_id}` | 授权老师与实际负责人 |
| POST | `/api/v1/internal/student/warnings/{warning_id}/ack` | 授权负责老师接手 |
| POST | `/api/v1/internal/student/warnings/{warning_id}/follow` | 授权负责老师人工跟进 |
| POST | `/api/v1/internal/student/warnings/{warning_id}/close` | 授权负责老师填写处理结果后关闭 |
| POST | `/api/v1/internal/student/sync/academic` | Bearer `STUDENT_SYNC_TOKEN`，映射 `service_code=student_sync、scopes=[student:sync]`，不是老师 JWT |
| POST | `/api/v1/internal/student/sync/progress` | 同上 |
| POST | `/api/v1/internal/student/sync/{kind}/pull` | 同上；`kind=academic/progress` |

心理协作与同步由学生开发，企业不重复实现。所有人员业务接口统一公共 JWT；同步接口单独校验服务凭据并映射 scope，不接受个人 JWT。系统 `admin` 不自动视作老师或同步身份，不接受旧学生自签登录令牌。

请假目标契约如下，路径保持上表约定：

- 列表筛选使用 `approval_status=pending/approved/rejected/cancelled`，可省略；仅查询 `apply_type=leave`，分页和 `total` 应用相同授权范围。
- 列表项及详情统一返回 `apply_id、student_id、apply_type、apply_content、approval_status、leave_start_at、leave_end_at、reviewer_id、reviewed_at、approval_comment、row_version、created_at、updated_at`；可额外返回受控的 `leave_type` 展示字段。仅输出这些业务字段，不透传 `edu_related_data` 全量内容、`request_hash` 或其他内部信息。
- `reviewed_at`、`approval_comment` 在未审批时可为 null；`reviewer_id` 未分派时可为 null，但不会出现在任意老师的审批列表，也不能由老师自行指定身份领取。
- 审批 body 为 `expected_version、decision、comment`，`decision` 仅允许 `approved/rejected`；`comment` 最多 2000 字，驳回时必填，批准时可省略。审批人、学生 ID、审批时间、目标表不接受客户端指定。
- 审批成功 `data` 返回 `apply_id、approval_status、row_version、reviewed_at、reviewer_id`。所有学生/老师业务方法统一 HTTP 200 + 第 6.3 节信封，应用产生的鉴权/校验错误同样处理；公共登录维持公共契约。运行行为仍待编码与测试。

学生侧使用 `/api/v1/student/leave` 入口，共用同一事实表和固定服务；以下均为开发与待测试目标：

| 方法 | 完整路径 | 权限与业务条件 |
| --- | --- | --- |
| POST | `/api/v1/student/leave` | 公共 JWT + `student.admin_service.create`，绑定本人 `student_id`，写入 `pending` 并按有效主班主任分派 `reviewer_id` |
| GET | `/api/v1/student/leave` | 目标本人列表；公共 JWT + `student.admin_service.read_own`，固定本人 `student_id` 与 `apply_type=leave` |
| GET | `/api/v1/student/leave/{apply_id}` | 目标本人结果详情；同上，不可查看其他学生；业务字段与老师详情的目标口径一致 |
| DELETE | `/api/v1/student/leave/{apply_id}` | 目标本人撤回；新增明确动作权限 `student.admin_service.withdraw_own`，携带幂等键及 `expected_version`，仅允许本人 `pending → cancelled`，保留申请与审计 |

学生目标撤回权限需由公共 YAML 显式授予学生身份，不能用查询权限隐含授予写权限。撤回与审批共用状态/版本并发控制，一方先完成后另一方返回 409。无班主任时提交记录仍可保留待分派，不自动授权任意老师接管；后续受控分派须检查有效主班主任并留审计。

#### 6.3 请求与响应约定

- 目标所有企业/学生/老师业务接口统一 HTTP 200 + `{code,message,data}`：0 成功，400 参数，401 身份，403 动作权限，404 对象不可见/不存在，409 状态/版本/幂等冲突，500 内部错误，503 依赖不可用；应用校验与鉴权错误同样封装。公共登录维持公共契约，网络/代理非200仍须处理，目标尚待实现与测试。
- 列表统一 `limit=1..100、offset≥0`，返回 `items、total、limit、offset`；统计总数也必须应用相同数据范围。
- 所有企业/学生业务写入、聊天与确认请求使用 `Idempotency-Key`，8～128 位可见 ASCII；同提交重试复用原键，同键不同参数返回 409。修改已有对象需 `expected_version`，通知已读等单调动作例外；提醒代次和会话版本按附录 B。历史校验如有差异，后续按目标契约改造，不在开发阶段保留冲突格式。
- 当前人、部门、操作者从服务端身份取得。客户转派等明确允许的目标人员字段须单独验证；日报不能接收任意 `employee_id` 代写。
- 普通查询返回业务数据和必要来源说明，不默认返回 SQL、异常堆栈、数据库结构或完整敏感字段。

#### 6.4 固定请假审批服务与事务

表单审批与对话中的 `leave.decide` 都调用同一审批函数；自然语言路径先完成预览确认，固定服务不调用 NL2SQL，也不让 Dify 直接写库。

1. 读取统一认证账号，检查员工有效状态、`teacher` 角色及审批动作权限；从账号关联取得真实员工 ID。
2. 仅在有权访问的请假集合内定位 `apply_id`，核验学生有效状态、有效 `class_teacher` 关系和 `reviewer_id=当前员工`。无动作权限为 403；对象不存在或不在授权范围为 404，避免泄露他人申请。
3. 将真实员工、动作、申请 ID、决定、意见、预期版本规范化计算参数摘要；按真实操作者、动作和请求幂等键生成唯一 `operation_key`。同键不同参数为 409；已成功的同参数重试在重验当前身份和范围后回放原回执，不再次审批或入队通知。
4. 对新操作在同一事务中占用幂等键，重新检查相关关系和申请，要求 `apply_type=leave`、`approval_status=pending`、`row_version=expected_version`。使用行锁或等价并发保护，保证审批、撤回和后续可能的分派变更互斥。
5. 固定参数化更新以 `id、apply_type、reviewer_id、approval_status、row_version` 为条件，写入 `approved/rejected`、服务端 `reviewed_at`、意见及 `row_version+1`。受影响行数必须为 1，否则回滚并返回 409；已批准、驳回或撤回的申请不能再次办理。
6. 同事务写成功审批操作记录、必要前后快照和可重放回执；学生结果通知使用 `student.leave.approved` / `student.leave.rejected` 事件，`entity_type=student_admin_service`，对象 ID 为真实 `id`，由学生通知任务按去重键消费。企业页面不重复发送相同结果通知。
7. 任一步失败全部回滚；事务提交成功才返回审批成功。通知投递失败单独重试，不回退已成功审批，也不以“已入队”冒充已送达。

在当前只允许指定老师审批的规则下，`reviewer_id` 与本次实际操作员工相同；实际操作者仍由审计独立保存。若以后新增转派，必须单独记录转派前后老师及原因；不得修改 `reviewer_id` 后再据此改写历史审批人。


### 学生 S一：21个学生方法、10个老师方法、3个同步方法

来源：`msj_jlj_原文无损合并.md` 的学生 S一：21个学生方法、10个老师方法、3个同步方法。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

目标为一个统一 Workflow 承接七类业务，数据库操作、权限和通知由后端固定服务执行。规划 21 个学生端业务方法、10 个老师协作方法和 3 个服务同步方法；这些是开发清单，不代表已注册或可调用。公共登录不计入学生端方法数量。学生模块维护全部学生接口、10 个老师协作接口及 3 个同步接口，企业模块只建设老师页面与调用编排，不重复注册这些路径或复制审批状态机。

#### 1. 学生端 HTTP 功能接口

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

#### 2. 老师协作与服务同步接口

##### 老师/员工侧：10 个方法

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

预警动作正文包含 `expected_version、note`。老师 JWT 来自公共登录，接口还校验 `teacher` 角色、动作权限、有效 `class_teacher` 关系与实际负责人，不能因 URL 有 internal 就无鉴权调用。预警 API 统一输出 `row_version`，映射到物理列 `mental_warning.version`；请假直接映射 `student_admin_service.row_version`。

##### 同步服务：3 个方法

| 方法与路径                                          | 调用方                                | 写入目标                                           |
| ---------------------------------------------- | ---------------------------------- | ---------------------------------------------- |
| POST /api/v1/internal/student/sync/academic    | 可信教务适配服务                           | student_academic_event（学生学业截止与考试节点镜像表）及必要的提醒重排 |
| POST /api/v1/internal/student/sync/progress    | 可信 CRM 适配服务                        | student_application_progress（学生留学申请阶段最新进度镜像表）  |
| POST /api/v1/internal/student/sync/{kind}/pull | 可信服务或后台触发，kind 仅 academic/progress | 从已配置外部来源拉取并写入对应镜像表                             |

同步接口统一采用服务专用凭据：`Authorization: Bearer <STUDENT_SYNC_TOKEN>`，不是个人 JWT。后端按服务配置安全比较凭据，生成 `service_code=student_sync、scopes=[student:sync]` 的可信服务上下文；错误或缺失为 401，有效身份缺少 scope 为 403。凭据仅从根目录 `.env` 读取，不交给学生页面。推送包含内部 `student_id、source_system、records`；拉取包含内部 `student_id`，由后端读取相应教务/CRM 外部身份。个人登录和服务凭据分支不能互相降级。

#### 3. 数据表与字段范围

学生负责七张专属表的目标设计：mental_health_profile、mental_warning、student_academic_event、student_academic_reminder、student_application_progress、student_assistant_session、student_assistant_turn。其 73 个目标字段见第八节；是否已建表和是否符合目标约束均需后续核验，不宣称其中任一张已通过落地测试。

请假唯一事实表为 `student_admin_service`；投诉共用 `service_ticket、service_ticket_record`；通知用 `business_notification`；幂等和审计用 `operation_log`。公共表完整普通字段由企业侧字段字典与双方附录 B 共同约定，学生侧使用相同表和主键，不再维护替代表。第八节保留专属表字段及公共关联，附录 B 补齐共享主键、物理外键目标和接口映射。


### 企业与学生接口的去重口径

学生来源21+10+3共34个方法（方法+路径）为开发目标。企业E6.2复述的13个协作方法和4个学生请假方法都已包含其中，不能再加17；企业E6.1组合行须按其声明拆分集合POST与单对象PUT/DELETE，不能做方法与路径的笛卡尔积。公共登录也不重复计入学生方法。

本轮不公布未经实际路由核验的全系统“已实现接口总数”。原四模块22操作为历史规划小计，企业和学生为新增范围；请假和老师协作全部由学生模块唯一注册，企业仅负责工作台及调用编排。


## 二、用户角色和接口鉴权

### 公共模块（主体）

#### 1. JWT 身份认证与逐接口鉴权

身份认证统一采用 JWT。权限校验由每个受保护接口调用公共鉴权中间件，依据用户表中的身份及对应权限，判断是否允许执行该接口。当前 FastAPI 代码通过 Depends(require_permission(...)) 接入公共鉴权组件，下文统称“鉴权中间件”；它在执行接口业务前完成认证和权限检查。具体流程为：

1. 用户提交账号密码，后端查询 `user_account` 并验证 `password_hash`。
2. 登录成功后签发带有效期的 JWT，返回 access_token、token_type 和 expires_in；后续请求携带 `Authorization: Bearer <access_token>`。
3. 每个受保护接口先调用鉴权中间件；中间件复用公共认证依赖，校验 JWT 签名及有效期，通过 Token 的 sub 取得 user_id，再查询用户表，取得真实 identity_type 和关联业务 ID。JWT 用于确认身份，接口权限以服务端当前用户记录和权限配置为准。
4. 当前实现用用户表中的 `identity_type` 到 `app/access_control.yaml` 查找权限集合。
5. 每个业务接口调用 require_permission(permission)，明确声明自己需要的权限，例如 student.admin_service.create；中间件检查该用户是否具备权限，通过后才执行接口。没有有效 JWT 时按 401 未认证处理；已认证但没有所需权限时按 403 禁止访问处理。响应信封及 HTTP 状态按第四节约定处理。
6. 业务模块继续检查本人/部门/学生关系、当前分派和状态等业务条件，限制可操作的具体记录。

**当前实现说明：** `user_account` 保存身份和关联 ID，没有独立的 `permissions` 字段，也没有在当前公共鉴权中查询独立用户权限关系表。因此准确口径是“用户表确定身份，权限配置确定该身份可以调用哪些接口”。若后续改为每个账号单独分配接口权限，需要增加相应数据模型和查询逻辑，不能描述成当前已经支持。

权限由服务端用户记录和配置决定，不接受前端自报身份。前端隐藏菜单仅用于展示；直接请求业务 API 时仍须鉴权。接口注册和调用由业务模块负责，公共鉴权负责允许或拒绝访问。

#### 2. 当前用户身份及权限

| 用户身份 | 用户表取值 | 当前 YAML 权限 | 范围说明 |
| --- | --- | --- | --- |
| 管理员 | `admin` | `admin.dashboard` | 当前只有管理员看板权限，不自动拥有全部业务接口权限 |
| 员工 | `employee` | `dashboard.employee`、`student.profile.read`、`student.admin_service.review`、`service_ticket.read`、`service_ticket.handle`、`report.read` | 业务仍须检查员工角色、部门、学生关系和分派范围；这些标识不表示所有接口都已接入校验 |
| 客户 | `customer` | `dashboard.customer`、`course_project.read`、`event_signup.create`、`service_ticket.create`、`service_ticket.read_own` | 客户本人的业务范围；不等同于学生身份 |
| 学生 | `student` | `dashboard.student`、`student.profile.read_own`、`student.admin_service.create`、`student.admin_service.read_own`、`student.notification.read_own` | 本人学生业务范围，不能审批请假或查看其他学生数据 |
| 匿名用户 | 无有效登录身份 | 无登录权限集合 | 仅公开清单、登录和业务明确公开的接口 |

以上保留旧配置事实，当前文档目标按下方用户确认后的权限清单实施对齐。尤其customer旧service_ticket.create/read_own与“仅学生客户提交本人投诉”冲突，不能据快照继续授非学生客户建单或代理读取学生工单；本轮尚未修改YAML。现有 `employee` 下的 `report.read` 与报告方案“仅管理层访问”的要求存在差异，需按最终业务授权调整。员工业务角色中的顾问、主管、老师、教务等不能仅凭统一 `employee` 身份区分，需由业务服务结合员工角色和关系校验。

#### 3. 公共接口访问权限

| 接口 | 允许用户 | 操作说明 |
| --- | --- | --- |
| `GET /api/v1/auth/public-access` | 所有用户，含未登录用户 | 获取公开页面/模块信息 |
| `POST /api/v1/auth/login` | 所有用户提交凭据 | 有效账号密码才能取得 Token |
| `GET /api/v1/auth/me/access` | 已通过认证且身份已配置的用户 | 仅返回当前账号权限，不允许指定其他用户查询 |

#### 4. 每个接口接入鉴权中间件的方式

各接口分别声明所需权限，不复用一个“登录成功即可访问所有业务”的规则。登录和公开清单等明确公开的接口无需挂载受保护接口的权限依赖。业务需要新增权限时，由负责人提供权限标识、允许角色和数据范围，公共模块统一维护权限映射；业务负责人将鉴权依赖接入每个对应接口。

关联表：本模块直接使用 `user_account`；其中 `employee_id`、`customer_id`、`student_id` 分别关联 `employee`、`customer_profile`、`student_profile`。业务表的维护归各业务模块。

### 客服模块（合并内容）

#### 1. 匿名开放原则

客服模块不建立独立用户体系，不接入平台 JWT 身份认证，也不为六个接口设置按角色划分的权限。访客打开网页即可咨询和报名；其他已登录身份访问时行为相同。

这里沿用源总览的最终开放规则，不沿用旧版客服鉴权方案中的 visitor Token 或身份权限目标态。公共模块中为受保护业务提供的逐接口鉴权组件，不作为客服六个公开接口的必需依赖。

#### 2. 用户与可访问功能

| 用户 / 身份 | 可访问接口 | 访问范围及说明 |
| --- | --- | --- |
| 匿名访客、潜在客户 | 全部六个客服接口 | 无需登录、无需 Token，可咨询、查课程/活动、报名及查询 FAQ |
| 已登录客户 | 全部六个客服接口 | 与匿名访问规则相同，不增加管理功能 |
| 员工、学生、管理员及其他身份 | 全部六个客服接口 | 本模块不按身份分配不同权限；平台身份不增加客服维护或私密数据访问能力 |

会话请求中的 user_id 是可选访客标识，不是经 JWT 验证的平台身份；session_id 用于会话关联，也不等同于接口授权凭据。现有清单没有任意会话历史查询、报名名单导出、课程维护或活动维护接口。

#### 3. 对外访问防护

| 功能接口 | 源文档中的防护要求 |
| --- | --- |
| 客服对话 | IP 限流，避免刷模型调用成本 |
| 活动报名 | 更严格的 IP 限流、状态式防重、手机号格式校验，可按需使用验证码；响应仅返回报名标识，不回传手机号明文 |
| 活动、课程、FAQ 查询 | 公开信息查询的常规限流 |

这些是源文档描述的运维及数据保护要求，不是角色权限。手机号加密属于后续可选增强；未核验限流和验证码已部署，不把这些要求写作当前已完成能力。对话也会写入消息，报名是采集姓名和手机号的业务写入入口。

### 客户研判权限方案（用户确认后的文档目标）

本轮用户明确：研判人员负责资料接入、解析、单条及批量执行；复核人员可读取规则；研判结果供客户顾问及其本部门读取，业务负责人为客户顾问。沿用员工角色代码analyst、reviewer、consultant及现有七项精确权限，不新增user_account.identity_type，不把customer身份当客户顾问。

| 主体 | 目标权限/职责 | 数据范围及限制 |
| --- | --- | --- |
| 研判人员analyst | customer.source.create、customer.source.parse、customer.judge.create、customer.judge.batch | 处理已授权、与负责顾问/部门对应的来源及任务；执行权不自动带来全公司结果读取权 |
| 复核人员reviewer | customer.rule.read；结果复核/查询使用customer.result.read并受下述部门范围约束 | 可读取适用规则，单凭reviewer不授rule.manage或跨部门结果读取权；不虚构结果修改/审批接口 |
| 客户顾问consultant（业务负责人） | 研判业务负责人；customer.result.read | 本人负责客户的结果；负责人从可信客户归属/顾问关联定位，不接受前端自报任意顾问 |
| 顾问所在部门的有效员工 | customer.result.read | 该负责顾问所属部门的研判结果；账号及部门须有效，不自动包含其他部门或子部门 |
| 平台管理员 | customer.rule.read、customer.rule.manage，负责规则配置及版本维护 | 沿用指定开发来源的配置职责；本轮“平台管理员都可以”针对报告，不扩展为所有研判业务操作或跨部门结果全读 |
| 客户customer、学生student、匿名访客 | 不授内部研判权限 | 可用公开客服，不因留资、报名或主档关联获得内部结果 |

客户顾问是员工consultant，平台客户customer不属于这个角色。研判结果读权限按负责顾问及其本部门计算；analyst/reviewer如需读结果也在此范围内，不借执行/复核身份跨部门读取。多角色按当前动作逐一求取有效范围，不将某角色的部门与另一角色的能力任意拼接。

当前五表字段未完整表达顾问/部门范围，后续必须由可信客户主档及顾问关联或经审查的任务归属方案闭合。来源未关联客户、顾问或部门缺失时不得默认全员可见；暂不擅加字段或外键。顾问/部门变更后的权限需重新计算；历史归属及数据留痕仍由后续结构/审计方案落实。

八个研判接口继续复用公共JWT及逐动作鉴权；公共依赖必须允许已授角色动作到达业务范围校验，不能只按employee统一放行或拒绝。精确权限仍为customer.source.create、customer.source.parse、customer.judge.create、customer.judge.batch、customer.result.read、customer.rule.read、customer.rule.manage，不依赖未经验证的通配。客服六接口继续匿名开放。

本节为明确的业务目标；真实角色配置、接口依赖和顾问/部门范围仍需接入与验证。

### 智能报告授权方案（用户确认后的文档目标）

当前授权依据：用户明确“报告访问人群只能管理员和部门主管用”；管理员沿用本次对话中的平台管理员 `identity_type=admin`，部门主管为有效员工且 `employee.role_codes` 含 `manager`。员工配置管理员 `role_codes=admin` 不等于平台管理员，单凭该角色不能访问报告。既有配置快照保留用于后续比对，不代表已经变更。

| 对象 | 当前文档目标 | 数据范围及条件 |
| --- | --- | --- |
| 平台管理员 | 查看、手动生成、读取/修改报告配置 | 全公司汇总及所有部门报告；报告内心理数据仍为匿名聚合，不授心理原文 |
| 部门主管 | 仅report.read：查看报告详情和列表 | 仅本人有效主部门；不生成、不读取/修改报告配置，不自动包含子部门或全公司报告 |
| 普通员工及其他员工角色 | 单凭employee、consultant、teacher、academic、analyst、reviewer或员工admin不授报告权限 | 兼任有效manager时，只按manager对应动作和范围计算 |
| 客户、学生、匿名访客 | 不授报告权限 | 不因主档关联、客服留资或公开页面获得访问权 |

精确权限为 `report.generate`、`report.read`、`report.config.read`、`report.config.write`；`report.mental_detail.read`继续默认不授。不依赖未验证的 `report.*` 通配，不把 `report.read` 放到全体employee的身份级授权中直接放行所有员工。

报告每个接口复用公共JWT账号上下文，再检查允许的人群、具体动作和数据范围。平台管理员分支与employee+manager分支均需可到达；不得先强制identity_type=admin将主管拒绝，也不得只检查employee将其他员工放行。角色、有效部门及数据范围由服务端读取，不信任前端或模型传入的角色/部门。`app/core/report_auth.py`如采用，必须复用公共认证，不建立第二套JWT。

部门过滤发生在取数、聚合和模型输入前，并延续到生成任务、报告存储、详情、列表、缓存及回放；仅过滤列表不能防止直接猜ID读取跨部门报告。现有报告37字段摘要未给范围承载方案，仍需后续设计，不把部门过滤写为已实现。来源《开发文档_msj.md》1.1、3.3、3.5及《开发文档-Albert2.md》1.4、4.5、8.1支持按部门/敏感级别授权和系统管理员管理报告配置。

### 按个人开发文档修订的权限清单（本轮当前口径）

新增取材范围为 `业务文档/06开发文档/个人开发文档/` 的9份文件；逐份权限依据见第十一章，剩余接入事项见末章。用户直接确认优先，其次采用本轮指定来源的明确业务规则；来源只有功能描述时不推导为所有员工拥有该功能。既有更细的有效绑定、当前负责人、版本及状态限制继续保留，除非与本轮明确结论冲突。以下均为文档开发目标，不代表已配置/已实现。

| 主体/角色 | 允许的动作 | 数据范围和必要条件 | 依据/当前状态 |
| --- | --- | --- | --- |
| 匿名访客、已登录客户及其他身份 | 客服对话、课程/活动公开查询、报名、FAQ六接口 | 仅公开信息；报名返回受控回执，不授任意报名记录或会话读取权 | Albert2 1.4、msj 1.1；沿用既有匿名契约 |
| 有效普通员工employee | 本人日报提交/修订、组织查询、新人知识问答、本人待办/通知 | 本人内容及有权访问的内部组织资料/知识；只给受控工作联系方式 | msj 3.3、Albert2 1.4；具体权限名沿用企业接口表 |
| 客户顾问consultant | 客户新增/查询/修改/状态/跟进/归档；作为研判业务负责人读取结果 | 本人负责客户；研判结果同时供负责顾问所在部门的有效员工读取，范围由后端确定；客户分派仍非顾问默认权 | 开发来源及企业E5/E7；研判结果范围与业务负责人已由用户确认 |
| 部门主管manager | 部门客户查询/管理/分派、部门日报查阅/汇总、部门工单分派/督办 | 当前主部门；日报按提交部门快照；主管身份不授成绩写入或请假审批 | msj 1.1、3.3、Albert2 1.4；具体动作及有效关系沿用企业契约 |
| 班主任/服务老师teacher | 负责学生的最小档案、班主任成绩只读、请假审批、工单处理、预警跟进 | 有效学生关系；请假需class_teacher且当前reviewer_id本人；工单/预警还需当前处理人；每次动作重验 | msj 3.3/3.4、Albert2 1.4；细分绑定沿用联合契约 |
| 教务academic | 成绩查询、录入、更正、作废 | 有效score_editor绑定的学生和显式课程；外部来源只读时拒绝本地写入 | 开发来源支持受控成绩办理；专用角色及绑定细则沿用企业E5，不推定全部员工可写成绩 |
| 企业配置管理员（员工admin） | 企业部门/员工配置、受控角色分配、学生员工关系；兼任知识/FAQ/课程/活动及版本内容运营 | 限企业配置及授权内容资源；不自动取得平台账号管理、报告配置/生成/读取、心理原文或老师审批 | 原企业E5 + 用户确认内容运营兼任，不新增角色代码 |
| 平台管理员identity_type=admin | 系统用户、角色、权限、规则、知识/Prompt版本、报告配置、参数及脱敏日志审计管理 | 高敏感数据仍需专门授权；不能以管理员身份冒充老师或服务任务 | Albert2 1.4、8.1明确；已有URL才映射接口，不虚构管理路由 |
| 研判人员analyst | customer.source.create、customer.source.parse、customer.judge.create、customer.judge.batch | 资料接入、解析及单条/批量执行；结果读取另按负责顾问及本部门范围，不自动全读 | 用户已确认；八接口及范围接入待实现验证 |
| 研判规则维护/复核人员 | 平台管理员customer.rule.read/manage；复核人员reviewer有customer.rule.read | reviewer可读适用规则，不自动维护；普通analyst不因执行权自动获得规则读取/维护 | 用户确认reviewer读取；系统管理员维护沿用指定开发来源 |
| 学生student | 本人请假提交/查询/撤回、投诉工单、心理关怀、学业/提醒、申请进度、生活问答、项目推荐、本人通知/会话/确认 | student_id从公共登录绑定；只读本人student_visible沟通；无审批/他人数据/内部预警权限；沿用第十六章精确权限 | msj 1.1、3.4、Albert2 1.4及开发流程学生闭环 |
| 非学生客户customer的售后工单 | 不授提交、代理学生提交或读取学生工单的权限 | 只有经公共登录绑定student_id的学生客户可提交本人投诉；不能因客户/学生主档关联直接授customer权限 | 用户已确认仅学生客户提交；旧customer工单权限为待移除/对齐配置快照 |
| 部门主管与平台管理员的报告功能 | 详情/列表；生成与配置按前述报告五接口表 | 主管限本部门；心理周报匿名聚合；报告权限不授个人预警及原文 | 用户确认 + msj 1.1/3.5、Albert2 1.4/4.5/8.1 |
| 内容运营（由企业配置管理员员工admin兼任） | 维护知识、FAQ、课程/活动及有效期，内容评测、审核与版本发布 | 使用既有企业配置管理员角色，不新设运营角色；维护不修改业务办理结果，模型不得直接发布；缺管理接口时仍为开发目标 | 用户已确认兼任；已有知识维护/发布权限沿用enterprise.knowledge.manage/publish |
| 系统任务/同步服务 | 提醒、报告生成、预警推送、教务/CRM同步 | 独立最小服务上下文；报告任务仅执行授权配置/范围；同步仍用STUDENT_SYNC_TOKEN和student:sync | msj 1.1、Albert2 4.5；不新增service人员登录身份 |

通用约束：公共JWT确定真实账号；员工按每个动作取得role_codes和范围；本人/客户归属/部门/学生关系及状态在业务服务重验。NL2SQL只读且仅访问白名单和授权行列，写操作由固定服务确认、事务及审计执行；模型既不能授权，也不能直接审批或执行写SQL。该口径依据msj 2、3.3、6及Albert2 1.4.1、3.5，保留主文档原有固定服务边界。

### 企业 E5：统一身份、员工角色与数据范围

来源：`msj_jlj_原文无损合并.md` 的企业 E5：统一身份、员工角色与数据范围。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

#### 5.1 复用统一身份

统一登录使用已有 `POST /api/v1/auth/login`；后续请求携带 `Authorization: Bearer <access_token>`，由 `get_current_account` 查询真实账号。不得默认 `user_id = employee_id`。

所有需要登录的学生、企业业务接口统一经过这一 JWT 认证入口，登录及明确公开的接口例外。当前 FastAPI 项目以公共 `get_current_account` 依赖挂载到受保护路由，接口再通过权限依赖取得同一账号上下文；这里的“统一鉴权中间层”不要求每个接口自行解析 JWT，也不新增学生侧校验器。同进程不为验票反复 HTTP 调用登录接口。若公共基础设施后续改为真正的 JWT 中间件，则由它提供同一当前账号上下文，业务层继续复用，避免中间件和依赖各维护一套校验。

| 层次 | 负责内容 | 请假审批必须满足的条件 |
| --- | --- | --- |
| 公共 JWT 认证 | 按公共配置验证令牌、查询真实账号及身份关联 | 取得真实 `user_id` 与 `employee_id`，不信任客户端提交的身份字段 |
| 接口动作授权 | 员工状态、角色、动作权限 | 有效员工、`teacher` 角色及 `student.admin_service.review` 权限 |
| 固定业务授权 | 对象归属、有效绑定、指定审批人、申请状态与版本 | 有效 `class_teacher` 关系、`reviewer_id=当前员工`、`apply_type=leave`、状态 `pending` 且版本匹配 |

学生提交或查询结果时，同样先通过公共 JWT，再在服务中限定 `student_id=当前账号.student_id`。JWT 有效不意味着能读取他人申请或审批任意学生。角色、绑定和申请状态必须在实际写入时重新核验。

| 统一身份 | 企业模块入口 |
| --- | --- |
| `employee` | 经员工状态、业务角色和数据范围检查后访问 |
| `admin` | 当前是系统管理身份，不绑定员工；不自动取得全部客户、成绩、投诉和审批权限。系统账号管理由公共模块负责 |
| `student` | 使用学生自助接口；不能访问企业员工接口 |
| `customer` | 使用客户/客服相关接口；不能访问企业员工接口 |
| 系统任务 | 使用受控服务上下文；当前账号结构未定义 `service` 登录身份，不通过新增伪员工绕过授权 |

员工必须处于 `active`、所属部门有效。企业业务角色来自 `employee.role_codes`，不是请求体或 Dify 返回值。每次实际执行业务前重新读取有效状态与关系。

#### 5.2 员工业务角色

沿用现有候选角色，不新增一整套角色关系表。所有有效业务员工享有普通员工基础能力，兼任角色按每个动作分别计算数据范围。

| 角色代码 | 中文角色 | 可调用的功能组 | 数据权限范围 |
| --- | --- | --- | --- |
| `employee` | 普通员工 | 本人日报、通讯录、新人指引、本人待办/通知、授权内自然语言查询 | 本人日报与通知；公开于内部的组织资料；已发布且有权访问的知识 |
| `consultant` | 客户顾问 | 基础能力 + 客户新增/查询/修改/状态/跟进/归档 | `customer_profile.employee_id = 当前员工`；新增负责人和部门由后端绑定为本人及本人部门 |
| `manager` | 部门主管 | 基础能力 + 部门客户管理/分派、部门日报查阅/即时汇总、部门投诉分派与处理督办 | 仅本人当前主部门；本期默认不自动包含子部门；日报以提交时部门快照过滤 |
| `teacher` | 班主任/学生服务人员 | 基础能力 + 学生最小档案、成绩只读、本人负责请假审批、授权工单跟进 | 有效 `class_teacher` 或 `service_advisor` 绑定；请假还需本人为当前审批人，工单还需本人为当前处理人 |
| `academic` | 教务人员 | 基础能力 + 成绩查询、录入、更正、作废 | 有效 `score_editor` 绑定的学生和课程；不因同部门自动拥有全体学生成绩修改权 |
| `admin`（员工角色） | 企业配置管理员 | 基础能力 + 部门/员工配置、受控角色分配、知识维护、学生员工关系维护、企业操作审计；兼任FAQ/课程/活动与内容版本运营 | 配置资源；业务敏感数据需额外业务角色。与不绑定员工的统一身份 `admin` 区分 |

补充规则：

- `manager` 本身不授予请假审批或成绩修改；主管兼班主任/教务时，分别按绑定范围检查对应动作。
- `teacher` 的成绩只读使用班主任绑定；成绩写入必须具备 `academic` 与对应 `score_editor`。课程为空不视为自动全课程，本期需显式授权课程。
- 工单处理可以由具有 `teacher` 角色且有 `service_advisor` 绑定的员工承担；分派后仍需检查当前负责人，不能仅凭任意学生关系处理任意工单。
- 权限集合不能与另一角色的范围随意交叉组合。例如“主管部门范围 + 教务修改能力”不能推导为修改全部门成绩。
- 联系方式仅返回受控工作联系方式，默认脱敏；不返回密文字段、个人登录身份键或密码哈希。

#### 5.3 授权落点

复用公共登录后，在 `app/core/enterprise_authorization.py` 增加企业授权依赖，得到 `employee_id、department_id、role_codes、动作对应的数据范围`。现有 YAML 继续管理公共身份、页面和模块入口；企业细粒度策略由该层解释，不能假定现有 `require_permission()` 已支持这些业务角色。

新增企业权限查询接口 `GET /api/v1/enterprise/me/permissions` 返回有效功能与范围摘要，供前端展示。后端每个列表、详情、导出、自然语言查询和写操作仍独立检查权限。查询范围应在数据库读取前约束，不能先取全库结果再由模型过滤。


### 学生 S二：业务范围、确认、版本与幂等

来源：`msj_jlj_原文无损合并.md` 的学生 S二：业务范围、确认、版本与幂等。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

#### 1. 公共 JWT 认证与业务范围校验

学生与老师使用公共账号登录接口取得 JWT，业务复用公共认证及权限依赖，按服务端真实身份、必要权限、本人归属或有效负责关系校验。internal 路径也必须认证，不能作为匿名内部接口。智能体本身不是额外拥有数据库权限的账号。

| 用户角色 / 调用主体 | 可用功能 | 权限与数据范围 |
| --- | --- | --- |
| 学生 student | 21 个学生端方法 | 仅本人记录及会话；办理先预览、再确认；不能审批或修改他人数据 |
| 老师 / 员工 employee | 10 个老师协作方法 | 需满足公共权限和负责关系；请假校验版本和审批关系；心理原文及风险依据仅授权处理人可读 |
| 可信教务 / CRM 同步服务 | 3 个同步方法 | 使用独立 STUDENT_SYNC_TOKEN，限定 academic / progress；凭据不得交给学生页面 |
| 公共管理员及其他身份 | 不默认授予学生/老师业务权限 | 必须按权限、角色和有效关系授权，不凭管理员身份查看全部心理原文或代审批 |
| 匿名用户 | 公共登录入口 | 不提供学生个人数据查询或办理授权 |

目标权限包在附录 B 逐组列出，并由公共 `access_control.yaml` 显式授予身份；角色、绑定和负责人校验继续由固定服务执行。`course_project.read` 只用于上架项目读取，不授予报名或订单权限。同步使用服务凭据和 `student:sync`，不使用学生或老师 JWT。

#### 2. 确认、版本与幂等

所有业务写入、聊天和办理确认请求携带 `Idempotency-Key`，8～128 位可见 ASCII；相同提交重试复用原键，同键不同参数返回 409。办理返回 `pending_action`；确认时提交后端签发的 `action_token`，固定服务重验身份、参数摘要、状态、版本和范围后执行，不再次调用模型。修改现有对象须传 `expected_version`；仅通知已读这种单调动作可以例外。会话并发、节点提醒代次及物理版本映射按附录 B 执行。


### 公共鉴权接入定位

当前业务权限目标见本章矩阵及第十六章B.4；公共授权接入、角色计算和服务身份的剩余事项统一见第十八章。

## 三、日志生成与业务操作记录

### 公共模块（主体）

各业务获取公共日志工具，按需记录启动、处理结果、外部调用失败和异常信息。

日志默认输出到控制台和 app/logs/ 下的日期命名日志文件，路径及等级由 LOG_DIR、LOG_LEVEL 配置。格式包含时间、级别、模块名称、行号和消息。当前日志文件名按进程加载时的日期确定。

公共模块提供日志工具，各业务负责调用工具记录具体业务事件。文本运行日志与数据库 `operation_log` 中的业务审计不同；账号密码、Token、Dify API Key 不写入日志，业务原文按需脱敏。

### 客服模块（合并内容）

#### 1. 咨询、推荐和报名流程

1. 访客提交 message，可携带 session_id 复用会话；user_id 为可选访客标识。
2. 后端建立或复用会话并保存用户消息，调用客服场景客户端得到意图和回复；调用失败记录异常并返回兜底话术。
3. 后端保存助手消息，返回 session_id、intent、reply、need_action、action。
4. 前端根据动作类型请求课程或活动接口，展示数据库中的真实列表；不直接连接 Dify。
5. 访客选择活动后提交报名，后端校验并写入报名记录，返回报名标识。

#### 2. 日志及记录分工

客服服务复用公共日志工具记录模型失败等运行异常。会话和消息保存在 chat_session、chat_message，报名保存在 event_signup；业务记录与运行日志分别管理。公共模块负责日志工具，客服模块负责具体调用位置及业务处理信息，不把手机号明文和应用 API Key写入运行日志。

### 报告运行日志与审计边界

报告复用公共运行日志记录取数、指标、模型及异步任务失败；fail_reason 不保存连接信息、Key、个人SQL参数或原始异常。运行日志不能代替业务审计。

### 学生 S三：业务操作、字段映射与审计

来源：`msj_jlj_原文无损合并.md` 的学生 S三：业务操作、字段映射与审计。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

#### 1. 常用操作流程

| 业务 | 操作顺序 | 闭环结果 |
| --- | --- | --- |
| 请假 | 学生提交 → 老师查询及审批 → 后台通知 → 学生查询 | 同一申请状态改变，保留审批意见、通知和审计 |
| 投诉 | 学生建单 → 企业分派和处理 → 学生查看回应 → 确认或重开 → 评价 | 状态、版本及可见沟通记录一致 |
| 心理预警 | 辅助评估 → 负责老师收到预警 → 接手、跟进、关闭 | 人工处理轨迹明确，通知送达不等于处理完成 |
| 学业提醒 | 教务同步 → 学生设置提醒 → 节点改期 → 后台投递 | 按最新版本及新时间提醒，避免重复投递 |
| 申请进度 | CRM 更新 → 同步镜像 → 学生查询 | 学生、外部申请、阶段和更新时间匹配 |
| 资料问答 | 维护资料 → 学生提问 → 展示来源 → 停用失效资料 | 有依据且来源可追溯，失效资料退出检索 |

#### 2. 请求字段与业务记录

请假提交使用 `leave_content、leave_type、leave_start_at、leave_end_at`，可传 `generate_ai_summary`；`leave_content` 由服务映射到 `apply_content`，`leave_type` 写入 `edu_related_data.leave_type`，时间统一 UTC。审批使用 `expected_version、decision、comment`，`decision=approved/rejected`，驳回意见必填且不超过 2000 字。API `apply_id` 始终对应 `student_admin_service.id`，详情字段与企业老师侧完全一致，见附录 B。

投诉 HTTP 提交字段为 content、ticket_type、category_code，智能体内部 ticket.submit 参数为 complaint_content、feedback_type、category_code，不能直接混用。提醒使用 academic_event_id、lead_minutes。

`operation_log` 保存真实操作者、业务变更与幂等审计；`student_assistant_turn` 保存聊天响应、请求键摘要和回执；`service_ticket_record` 保存沟通与流转。业务更改、成功审计、必要通知和幂等回执同事务完成，运行日志不能代替数据库审计。学生与企业各自只调用所负责的固定写入服务，不用模型生成的 SQL 改库。

心理关怀仅为支持性辅助，不是自动诊断或自动处分依据；人工关闭需接手及处置结果。心理原文和风险依据不用于普通项目推荐、企业报表或公共查询。


## 四、统一返回格式及异常处理

### 公共模块（主体）

各业务 HTTP 接口通过统一返回工具组织响应，固定包含 code、message、data 三个字段。

`code` 为业务状态码，`message` 为说明，`data` 为结果数据；成功为 0，常用失败码包括 400 参数错误、401 未登录、403 无权限、404 不存在、409 冲突、500 内部错误。

应用入口注册全局异常处理后，业务异常被转换为统一信封；未处理异常记录日志并返回通用内部错误。当前业务异常及未处理异常使用 HTTP 200 搭配业务码；HTTPException、参数校验异常仅企业路径进行了统一信封处理，其他路径仍可能返回框架格式，部分业务也显式使用实际 HTTP 错误状态。因此各模块“所有响应都统一”目前尚未完全落实，需要进一步统一异常出口和协议约定。

本地 Dify 原始响应先交由业务适配器解析，再由业务接口调用 `success()` 返回；公共 HTTP 工具不直接把模型响应变成业务成功结果。

### 客服模块（合并内容）

六个接口使用 code、message、data 三字段返回。code 为 0 表示成功，非 0 表示业务错误；业务错误按源总览约定使用 HTTP 200 搭配业务码。接口参数校验、框架 HTTP 异常的全局统一范围仍取决于公共异常组件，不能仅凭业务约定认定全部错误出口都已统一。

| 功能 | data 主要内容 / 行为 |
| --- | --- |
| 对话 | session_id、intent、reply、need_action、action |
| 活动列表 / 详情 | 活动信息；列表可按状态筛选 |
| 活动报名 | signup_id；不回传手机号明文 |
| 课程列表 | 上架课程信息；可按类别筛选 |
| FAQ | 匹配的标准问答；关键词未命中时返回第一条 |

模型异常由客服服务记录并转换为兜底回复；HTTP 请求成功不自动代表 Dify 工作流执行成功，real 客户端应检查业务状态和输出。参数、活动不存在、报名重复及名额不足等错误由对应业务层校验后交统一响应组件处理。

### 报告异步状态与错误返回

来源约定：同幂等键同口径返回已有记录，同键不同口径按 409 冲突处理；生成受理后立即返回 report_record_id，任务状态从 pending 转为 success 或 failed，并记录 fail_reason。报告“已受理”不表示已生成成功，查询接口应根据保存状态返回。

具体 HTTP 状态、业务码和 response data 模型尚未给出，继续受本章既有异常出口差异约束。无效 report_code、非法时间窗、上游缺表/缺列、权限不足、重复触发、模型失败及失败查询需要逐项约定，不凭“统一返回”推断所有路径已统一。

### 学生 S四：统一返回目标与异常处理

来源：`msj_jlj_原文无损合并.md` 的学生 S四：统一返回目标与异常处理。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

目标统一为 HTTP 200 + `{code,message,data}` 信封，与企业协作接口一致：`code=0` 成功，400 参数错误、401 凭据错误、403 动作无权限、404 对象不可见/不存在、409 版本/状态/幂等冲突、500 内部错误、503 依赖不可用。应用产生的校验、身份及业务错误均按此返回；网络、代理和其他非应用异常仍可能是非 200，调用方必须同时处理。公共登录接口维持公共模块契约；本方案不以历史接口状态推断现有行为已经统一。

| 场景 | 响应内容 / 处理要求 |
| --- | --- |
| 对话查询 | 返回本人真实记录，不由模型编造节点、申请进度或业务事实 |
| 对话办理 | 返回 pending_action 预览及确认凭证，未经确认不写对应单据 |
| 确认执行 | 返回固定业务服务形成的结果，重复请求复用幂等回执 |
| 资料不足或未接来源 | 明确暂无记录或无法核实，不用模型补造 |
| 来源同步 | 以 source_updated_at 防止旧数据覆盖；synced_at 仅表示最近成功同步，失败不刷新 |
| 通知 | 写入后经后台任务成功投递才对相应收件人展示；通知已读不等于事项已处理 |


### 企业学生错误协议适用范围

企业E6.3、学生S四与契约B.4采用HTTP200加业务code；范围内错误出口的接入和验证统一见第十八章第009项。

## 五、调用本地 Dify 大模型

### 六模块大模型调用总览（本轮按个人原文补充）

本节取材于操作文档个人版目录的8份文件：mrz.md、hzl.md、sgt.md、msj.md、jlj.md、cyl.md、allm.md、sgtallm.md；本轮不读取cyl合并后.md和msj_jlj_原文无损合并.md作为新增依据。此前业务内容继续保留，剩余问题统一见末章；排除新增取材不表示删除来源文件。

本节集中列业务入口、服务/适配器、公共传输及固定业务处理。精确字段仅保留来源已明确内容，不补造调用协议；运行状态仍需单独验证。

#### 1. 六模块调用关系总表

| 模块 / 负责人 | 触发模型的业务入口 | 服务和适配器 | Dify应用 / DSL | 模型负责的输出 | 固定代码和数据边界 |
| --- | --- | --- | --- | --- | --- |
| 公共基础 / 马睿智 | 无独立业务模型入口；供各业务复用 | app/core/dify.py：DifyHttpClient | 不维护统一业务模型或Prompt | 返回Dify原始JSON | 同步/异步JSON POST、Bearer Key、超时和HTTP检查；不解析全部业务结果 |
| 客服 / 何至朗 | POST /api/v1/agent/chat；仅real走真实模型 | run_chat → get_dify_client → RealDifyClient → 公共HTTP | dify/客服Agent-Chatflow.yml，实际约定为Workflow | intent、reply；业务适配器映射前端动作 | 会话消息、课程活动事实及报名由后端维护；另五客服接口不调模型 |
| 客户研判 / 业务负责人：客户顾问 | POST /api/v1/customer/sources/{id}/parse中的可选语义字段提取 | parser → extractor / extract_fields → clients/extract_dify.py → 公共HTTP | dify/customer-extract.yml为sgtallm列出的可选/待交付资产 | 研判所需结构化客户字段 | judge_service按版本规则确定是否命中；单条/批量判定不依赖模型自由裁决 |
| 企业 / 莫世杰 | command、nl2sql、onboarding/ask、daily-report/summary；真实语音入口待交付 | enterprise_command / enterprise_nl2sql及固定服务 → 对应Dify适配器 → 公共HTTP；语音先经faster-whisper本地适配器 | dify/enterprise下的提取、只读SQL、QA/RAG及摘要方案；语音DSL仅历史参考 | 受控动作字段、SQL候选、有来源回答、摘要或转写文本 | 确认后只调用固定写服务；受限SQL经AST校验再只读执行；表单不强制模型调用 |
| 学生 / 蒋立建 | POST /api/v1/student/chat、POST /api/v1/student/mental/monitor；请假表单可选AI摘要 | student_chat / 学生服务 → clients/student_assistant_dify.py → 公共HTTP目标 | dify/student/student_assistant.yml：一个统一Workflow | 查询/咨询回复、受控意图参数、pending_action预览；心理辅助结果 | 本人数据固定查询、确认Token和版本校验、固定落库/审计/通知；确认接口不再次调模型 |
| 智能报告 / 陈宇林 | POST /api/v1/report/generate的后台生成链路；定时生成复用同一链路 | report_service → 固定指标取数 → ReportDifyClient.generate_report → 公共HTTP | dify/report/report.yml：智能报告生成 | data.outputs.report_text，Markdown报告正文 | 固定SQL算真实指标、幂等和任务状态、指标快照与正文落库；其他四接口不调AI |

公共认证凭据、Dify应用Key、确认Token及同步服务Token用途不同；浏览器调用业务后端，后端才调用Dify，不能将应用Key交给前端。公共工具不是一个面向浏览器的统一“模型HTTP接口”。

#### 2. 公共模块：唯一HTTP调用层

依据：mrz.md第五章；msj.md第五章公共传输说明。

1. 业务适配器从app/config.py取得DIFY_API_BASE、DIFY_API_TIMEOUT_SECONDS和本业务应用Key，选择已确认的Dify路径并组装请求。
2. 同步路径调用DifyHttpClient.post_json_sync(path, api_key=..., payload=...)；异步路径调用await client.post_json(...)，由业务选择匹配的服务执行方式。
3. 基础地址默认值的来源记录为http://127.0.0.1/v1，接口路径例如/workflows/run；基址已含/v1时不再次重复拼接。实际部署地址由后端配置确认。
4. 公共层完成JSON POST、Authorization Bearer应用Key、超时、HTTP状态检查与JSON对象解析，随后把原始结果交还适配器。
5. 适配器继续检查工作流业务状态、输出路径及字段类型，转换成业务结果；HTTP200不等于Workflow成功。日志、响应与数据库提交仍各有职责。

公共层没有默认业务模型名称、统一Prompt或跨模块通用输出schema。来源明确尚不提供文件上传、SSE、自动重试、长期连接池复用和熔断，真实语音等需求须按公共能力扩展，不私建一套HTTP调用。

#### 3. 客服模块：一个对话入口调用Workflow

依据：hzl.md第五、六章；allm.md第四章只作为另一工作副本的流程/状态来源。

| 项目 | 调用约定 |
| --- | --- |
| 业务HTTP | POST /api/v1/agent/chat；匿名开放，不要求先登录 |
| 后端链路 | agent路由 → run_chat → get_dify_client().chat → RealDifyClient → DifyHttpClient.post_json_sync |
| Dify请求 | POST {DIFY_API_BASE}/workflows/run；inputs.query为用户消息；response_mode=blocking；user为visitor-加会话ID |
| Dify结果 | 从data.outputs读取intent、reply；清理不应展示的推理内容、验证字段后构造need_action/action |
| 前端动作 | show_courses / show_events提示前端再查真实课程/活动列表，模型不填造课程、名额或报名结果 |
| 应用配置 | DIFY_CLIENT=mock/real、DIFY_AGENT_API_KEY，加公共地址/超时；mock为关键词模拟，不能算真实模型调用 |
| DSL与知识 | 客服Agent-Chatflow.yml虽以Chatflow命名，来源约定调用Workflow；四知识库为公司信息、公司业务、留学政策、FAQ |
| 模型/供应商 | 来源没有明确具体模型名称；由目标Dify应用绑定，不自行指定 |
| 异常与记录 | 目标为用户消息保留、失败日志及兜底话术、助手消息保存；事务/兜底实现差异仍待核验 |

不调模型的客服操作为活动列表、活动详情、活动报名、课程列表和FAQ数据库兜底；课程推荐、活动推荐等七类咨询在同一对话工作流内处理，不因此新增七个后端模型入口。

状态差异必须保留：allm.md称real链路已实现，hzl.md却记录RealDifyClient初始化未实现、路由/配置/资产未接通；本次只提炼共同调用设计，不任选一方“已实现”为当前系统事实。

#### 4. 客户信息研判：可选模型抽取，固定规则裁决

依据：sgt.md第一、五章及附录；sgtallm.md目录与客户研判主线。

```text
来源接入 → text/pdf/excel解析器归一化文本
        → extract_fields（可选：extract_dify → 公共HTTP → 独立抽取应用）
        → 校验结构化字段并写customer_info
        → judge(customer_fields, rule_version)按产品规则比对
        → build_result → research_result（命中/未命中均正常返回）
```

| 项目 | 已明确调用内容 |
| --- | --- |
| 需要语义理解的场景 | PDF简历、非结构化文本中的姓名、学历、专业、工作年限、行业、城市、收入、意向产品、联系方式等字段提取 |
| 模型输入 | 归一化文本及抽取所需字段约束 |
| 模型输出 | 结构化字段，校验后才可写customer_info |
| 模型与Key | 独立应用Key，具体环境变量名和模型名称来源未给出；复用DIFY_API_BASE/超时，不借用客服或报告Key |
| 后端判定 | 两个产品的画像规则按research_rule版本执行，模型不得自行改变规则、补造关键事实或决定审批/业务写入 |
| 无模型路径 | 文本/表格等可由确定性解析提取；无模型仍可执行已具备字段的规则判定；不能把模型不可用时静默猜值称为降级成功 |

来源“准确率不低于95%”是需求目标，需明确规则真值样本与测试口径后验证，不能当成本次准确率结论。解析与规则缺失是错误，未命中产品画像是正常结果。

单条使用 customer.judge.create，批量使用 customer.judge.batch；按第二章权限矩阵接入并分别验证。

#### 5. 企业模块：按场景拆分调用，确认后走固定服务

依据：msj.md第三、五章。企业负责人在个人原文明确为莫世杰；其应用均为拟交付方案，不代表已运行。

| 场景 | 业务入口 / 触发点 | 适配器及DSL | 输入、输出与后续处理 |
| --- | --- | --- | --- |
| 写动作提取 | POST /api/v1/enterprise/command | enterprise_dify；enterprise_extract.yml | inputs采用text、action_catalog、field_schema、context、contract_version；输出结构化result，内含intent/action/target/fields/missing_fields/needs_clarification；只形成预览 |
| 通用自然语言只读查询 | POST /api/v1/enterprise/nl2sql | enterprise_nl2sql → enterprise_nl2sql_dify；enterprise_nl2sql_readonly.yml | question、schema_context、dialect、query_constraints、bound_filters、schema_version → query_result中的SQL模板/参数引用/引用清单；后端独立校验再执行 |
| 新人标准QA | POST /api/v1/enterprise/onboarding/ask的QA分支 | enterprise_dify；enterprise_onboarding_qa.yml | 已授权QA候选与问题 → 有来源回答；未命中不编造 |
| 制度RAG | 同一onboarding/ask的RAG分支 | enterprise_dify；enterprise_onboarding_rag.yml | 已限定部门/版本的资料 → 引用来源的回答；检索前过滤权限 |
| 日报即时摘要 | POST /api/v1/enterprise/daily-report/summary | enterprise_dify；enterprise_daily_summary.yml | 仅授权已提交日报 → 核心进展/产出/风险摘要；不自行读取全团队，不冒充正式日周报告 |
| 本地语音转写 | 登录后的音频上传/录入入口 | faster-whisper本地适配器；不调用enterprise_voice_transcribe.yml | 音频校验 → 本地转写 → 用户核对文本 → 既有动作/日报提取与确认；无需语音Dify应用Key |


写入链路：公共身份与企业授权 → 模型提取 → Schema与候选对象校验 → 返回预览和短期确认凭证 → 同一员工POST /api/v1/enterprise/command/confirm → 重验参数摘要、范围、状态与版本 → 动作白名单映射 → 固定服务事务（业务/审计/必要通知/幂等回执）。确认阶段不再次调用模型或NL2SQL；客户、成绩、请假、工单和日报规则由固定服务决定。

只读SQL链路：后端先构造授权schema和受限关系 → 独立生成应用 → AST核验单语句、逻辑关系/列/函数、绑定参数 → 查询成本与行数限制 → 只读账号执行。模型引用清单仅作参考，params只引用已核验的后端值。禁止回查物理基表、写SQL、任意执行或失败后退回不受控旧查询器；不将密码/心理表等纳入通用schema。

普通表单列表/详情与明确字段的写表单直接使用固定服务，不为每次打开页面或确认再消费模型；客户转派、教务成绩、请假审批仍在实际写入时检查角色、绑定与当前状态。

#### 6. 学生模块：统一Workflow覆盖七类业务

依据：jlj.md第一、三、五、六章。该个人原文与现有联合契约存在配置和状态差异，以下调用设计与差异同时保留。

| 业务场景 | 调用模型的用途 | 模型调用后的固定业务处理 |
| --- | --- | --- |
| 请假 | 聊天理解办理意图并提取申请信息；直接表单可选generate_ai_summary | 先预览，确认后StudentLeaveService写student_admin_service；老师审批不让模型代决策 |
| 投诉建议 | 聊天提取ticket.submit所需complaint_content/feedback_type/category_code | 映射content/ticket_type等固定字段并确认执行，后续由企业处理、学生确认/重开/评价 |
| 心理辅助关怀 | POST /student/mental/monitor及聊天相关路径用统一应用生成辅助评估 | 校验emotion/risk等结果后写评估/必要预警，通知授权老师人工处理；不作为医学诊断或自动处分 |
| 学业节点/提醒 | 理解问题，结合本人真实节点形成回复或提醒预览 | 本人固定查询或受控student-v1响应；设置提醒由固定服务按节点/设置代次执行 |
| 申请进度 | 结合本人CRM镜像解释当前阶段 | 真实进度来自student_application_progress，AI不自行推进阶段或伪造同步结果 |
| 生活咨询 | 统一聊天life意图 | 检索审核资料并展示来源，action=none；正式知识为空时明确无法核实 |
| 升学推荐 | 统一聊天upgrade意图 | 基于审核资料/真实上架项目提供建议，action=none；不自动报名、下单或创建客户线索 |

调用链：学生页面 → POST /api/v1/student/chat（message、可选conversation_token、幂等键）→ 公共JWT和本人范围 → 固定查询本人记录/审核资料 → student_assistant_dify → 公共HTTP目标 → 单一学生Workflow → 校验结构化输出 → 查询返回真实事实，办理返回pending_action及后端签发action_token → POST /api/v1/student/actions/confirm → 固定服务执行。确认过程不再次调模型。

生活咨询使用 life、升学推荐使用 upgrade，二者 action=none；直接心理评估请求使用 chat_content。模型输出经固定服务校验，不直接写入业务事实。

目标资产为dify/student/student_assistant.yml、assistant_prompt.md、knowledge.json、README.md；历史student_leave/student_ticket客户端和DSL保留参考，不额外部署多个学生智能体。老师审批、人工预警处置、固定列表/详情、同步写镜像及通知任务本身不靠模型决定业务事实；表单可选摘要是否触发统一应用需逐路径验证。

旧来源jlj.md列student_config.py/.env.student.local/STUDENT_DIFY_BASE等；统一目标仍是根.env经app/config.py读取DIFY_API_BASE/DIFY_API_TIMEOUT_SECONDS/STUDENT_DIFY_KEY。本轮实际核对：Settings与StudentLeaveDifySettings均位于app/config.py并读取同一根.env，旧请假使用STUDENT_DIFY_LEAVE_KEY/TIMEOUT/VERSION，另有STUDENT_SCORE_DIFY_BASE/KEY声明；统一STUDENT_DIFY_KEY及学生同步/动作签名配置尚未声明。不能把旧请假Key或成绩Key直接当统一学生应用Key；见第十八章第017项。

状态也分开：jlj.md声称Workflow草稿导入、本地账号/站内通知及79项回归等提交记录，同时明确真实模型、供应商绑定、应用Key/发布和正式来源未接通；现有联合方案则统一按开发待测试管理。保留原记录，但本次没有复跑或验证，草稿导入与mock均不算真实模型验收。

#### 7. 智能报告：固定指标输入，模型只写分析

依据：cyl.md第三、四、六、八、九章。原始个人文档较前次合并说明提供更完整契约，以下补充不等于部署已核验。

| 项目 | 调用约定 |
| --- | --- |
| 唯一对外生成触发 | POST /api/v1/report/generate；后台生成，立即返回report_record_id及pending |
| 生成参数 | report_code、可选start_time/end_time；当前业务时区统一Asia/Shanghai（用户确认，替代来源默认UTC）；未传时间窗仍按已约定完整周期，不能把17:00触发时间直接当当天完整统计窗 |
| 固定取数 | _fetch_metrics固定参数化SQL；目标可拆到report_metrics，先计算真实指标、应用心理聚合范围后再传模型 |
| 场景客户端 | app/clients/report_dify.py中的ReportDifyClient.generate_report()；经公共DifyHttpClient调用 |
| 工作流 | dify/report/report.yml，智能报告生成；来源节点为“用户输入 → LLM → 输出” |
| 输入与输出 | 输入report_code及metrics（已计算指标的JSON文本）；输出data.outputs.report_text |
| 模型标识 | cyl.md写deepseek-v4-pro；仅记录来源模型配置名，本轮未核验目标供应商是否提供或已绑定，其他模块不沿用此名 |
| 正文职责 | 用Markdown组织摘要、趋势、归因、建议；只引用输入已有数字，不编造/估算缺失指标 |
| 保存与失败 | 固定服务清理推理内容、核对正文数字，保存report_content/metric_json与report_metric；失败记录failed/fail_reason，不编造成功报告 |
| 定时生成 | 用户确认Asia/Shanghai：daily_report每天17:00；其余四类周报每周五17:00。调度仍待实现，复用授权生成服务；配置示例不启动任务 |

来源报告状态包含pending/running/success/failed；running的持久化、执行租约和恢复仍待验证。本轮静态核对实际配置/客户端，报告Key名已明确为REPORT_DIFY_API_KEY，输出键由REPORT_DIFY_OUTPUT_KEY配置，地址取REPORT_DIFY_API_BASE或回退公共DIFY_API_BASE；当前根.env已配置报告Key与输出键，但未验证Key有效性、Dify发布状态或调用成功。请求封装见下文及第十八章第018项，不再将变量名列为未知。

五类报告的模型输入均来自各自固定指标：customer_overview为客户状态/新增/跟进/流失等；daily_report与weekly_report为正式日报数量指标；mental_weekly为匿名评估/风险分布/预警及趋势；complaint_weekly为投诉状态/分类/时效/满意度。风险识别归学生、日报内容级摘要归企业；报告不再建重复识别/摘要智能体。客户研判customer_judgement和成交金额仍是未接上游，不能靠模型填补。

原始cyl.md已明确其他四个接口及权限，补齐前次合并说明的信息空缺：

| 方法及路径 | 目标权限 | 是否直接调用模型 |
| --- | --- | --- |
| POST /api/v1/report/generate | report.generate | 是，后台链路调用 |
| GET /api/v1/report/{report_record_id} | report.read | 否，读已存正文/指标 |
| GET /api/v1/report/list | report.read | 否，仅读元数据 |
| GET /api/v1/report/configs | report.config.read | 否，读配置 |
| PUT /api/v1/report/configs/{report_code} | report.config.write | 否，固定字段/row_version校验 |

report.mental_detail.read在来源中为默认不授的额外权限，本轮不创建个人明细接口或改变默认心理匿名聚合。报告访问人群现已由用户明确为平台管理员和部门主管，逐动作分工见第二章；全体employee旧report.read与目标仍需实施对齐，精确权限说明不代表已修改YAML或路由鉴权。

#### 8. 应用Key、DSL与模型配置汇总

所有Key只列已明确的变量名，不记录真实值；根配置入口不因场景拆分而改变。

| 用途 | Key / 其他调用配置 | 资产及协议状态 |
| --- | --- | --- |
| 公共地址/超时 | DIFY_API_BASE、DIFY_API_TIMEOUT_SECONDS | 公共JSON POST；业务Key由各自配置传入 |
| 客服 | DIFY_AGENT_API_KEY；DIFY_CLIENT=mock/real | 客服Agent-Chatflow.yml，约定/workflows/run、blocking |
| 企业动作提取 | ENTERPRISE_EXTRACT_DIFY_API_KEY | enterprise_extract.yml；/workflows/run；结构化result |
| 企业只读SQL | ENTERPRISE_NL2SQL_DIFY_API_KEY | enterprise_nl2sql_readonly.yml；/workflows/run；结构化query_result |
| 企业QA/RAG | ENTERPRISE_KNOWLEDGE_DIFY_API_KEY | 用户确认一个发布应用内QA/RAG分支；共享一份应用Key，原两份DSL作为分支来源整合，不部署为两个应用；当前未发布 |
| 企业日报摘要 | ENTERPRISE_SUMMARY_DIFY_API_KEY | enterprise_daily_summary.yml |
| 本地语音 | faster-whisper；ASR_BACKEND/MODEL_SIZE/DEVICE/COMPUTE_TYPE/MODEL_PATH为新增规划配置 | 当前不需要ENTERPRISE_VOICE_DIFY_API_KEY；后端本地推理，模型准备、安装及音频入口尚未实现 |
| 学生统一应用 | 目标STUDENT_DIFY_KEY；旧文写STUDENT_DIFY_BASE/KEY并独立加载 | student/student_assistant.yml；实际协议/完整Schema待核对 |
| 智能报告 | REPORT_DIFY_API_KEY、REPORT_DIFY_OUTPUT_KEY；REPORT_DIFY_API_BASE为空则回退DIFY_API_BASE | 实际客户端/workflows/run，blocking；inputs.report_code及JSON文本metrics→data.outputs的配置键；Key已配置但发布/模型绑定未验证，见第十八章第018项 |

ENTERPRISE_CONFIRM_SECRET、STUDENT_ACTION_SECRET是业务凭证签名用途，AUTH_SECRET_KEY是平台JWT用途，STUDENT_SYNC_TOKEN是受控同步身份用途，它们都不是Dify应用Key。模型供应商Key、具体模型绑定在Dify环境维护，不与应用调用Key混用。

#### 9. 调用失败与验收依据

客服失败按其目标兜底并保留消息；字段提取缺失/非法时澄清或报错，不能猜字段；企业确认失败不写业务；只读SQL校验失败不降级到不受控执行；学生查询缺来源明确无法核实、确认失败保留幂等一致性；报告模型失败转failed且正文不冒充成功。已有固定业务提交后发生通知失败，仅重试投递，不重放模型或业务写入。

各应用后续至少需提供：真实DSL版本与供应商绑定、输入输出样例、专用应用Key配置名、一次成功调用及超时/工作流失败/非法输出验证、与业务事实及权限范围对照结果。这个清单是调用验收目标，本轮只更新文档，不启动服务、访问模型、提交业务或验证来源测试数量。

#### 10. 本轮取材文件与定位

| 文件 | 对本轮调用说明的贡献 |
| --- | --- |
| mrz.md | 第五章公共HTTP边界、同步/异步方法、地址/超时与应用Key职责 |
| hzl.md | 第五章客服Workflow参数/输出与mock-real；第六章实现差异 |
| sgt.md | 第一/五章可选抽取与规则判定边界、精确接口权限、95%需求目标 |
| msj.md | 第三/五章动作/确认、独立只读SQL、六类DSL、企业Key配置；明确负责人莫世杰 |
| jlj.md | 第一/五/六章学生统一Workflow、入口/确认与旧独立配置、草稿/真实模型差异 |
| cyl.md | 第三/四/六章报告精确路由/权限、模型标识、客户端方法、输入输出及固定指标；第五章状态等辅助口径 |
| allm.md | 第四章另一副本的客服real链路/兜底描述，状态与hzl并列保留 |
| sgtallm.md | 可选customer-extract.yml、extract_dify路径、研判主线与独立应用；批量权限的另一口径 |

以下为各场景已有设计说明，调用状态需实际验证；当前实施事项统一见第十八章。


### 公共模块（主体）

各业务都有自己的 Dify 应用及模型能力。本模块只提供从后端到本地 Dify 的 HTTP 请求封装。各业务负责人负责自己的模型选择、Prompt、工作流/对话应用、知识库、业务输入和结果解释。

| 分工 | 公共模块负责 | 业务模块负责人负责 |
| --- | --- | --- |
| 地址与连接 | 接收 Dify API 基础地址，拼接请求路径 | 确认使用的本地 Dify 服务和应用类型 |
| 应用凭据 | 使用传入的应用 Key 设置 `Authorization: Bearer ...` | 为业务应用配置独立 Key，交由服务端配置读取 |
| HTTP 请求 | 同步/异步 JSON POST、超时、HTTP 错误检查、JSON 对象解析 | 选择 `/workflows/run` 或 `/chat-messages`，组装对应请求体 |
| 模型能力 | 提供 HTTP 传输工具 | 模型、工作流、Prompt、知识库及业务策略 |
| 返回结果 | 返回 Dify 原始 JSON 对象，底层异常交调用方处理 | 检查工作流业务状态，提取输出、校验结构，并转换成业务结果 |
| 后续动作 | 不承担各业务的数据写入或审批判断 | 调用业务服务执行落库、审批、通知和状态变更 |

#### 调用方式

本地 Dify 基础地址默认从 `DIFY_API_BASE` 读取，当前默认值为 `http://127.0.0.1/v1`。各应用使用各自的 API Key；调用地址为后端可访问的 Dify 地址，模型供应商的配置由各业务在 Dify 中维护。

同步业务调用同步 HTTP 方法，异步业务调用异步 HTTP 方法。应用 Key 从后端配置读取，不由浏览器提交，也不写入文档。具体输入和输出字段由各业务定义，调用用户标识由可信认证上下文生成。

当前工具只封装 JSON POST；SSE 流式输出、文件上传、自动重试、连接池长期复用、熔断和 HTTP 失败到业务错误码的统一映射尚未提供。各业务如需要这些能力，应明确需求后扩展；工作流返回 HTTP 200 仍可能执行失败，必须由业务适配器检查，不能只依据 HTTP 成功判断模型调用成功。

### 客服模块（合并内容）

#### 1. 调用入口与职责

只有客服对话接口调用 Dify。源总览指定后端调用本地 Workflow：基础地址默认 http://127.0.0.1/v1，路径为 /workflows/run。输入字段为 inputs.query，输出从 data.outputs 中读取 intent 和 reply；响应模式为 blocking，调用用户标识采用 visitor- 加会话 ID。文件名虽含 Chatflow，源总览明确实际为 Workflow 模式。

| 分工 | 公共模块负责 | 客服模块负责 |
| --- | --- | --- |
| HTTP 连接 | JSON POST、应用 Key 请求头、超时及 HTTP 状态检查 | 选择客服应用地址及 Workflow 路径，组装客服请求 |
| 模型与知识 | 提供通用传输组件 | 客服模型、Prompt、意图路由、知识库和话术生成 |
| 结果解析 | 返回 Dify 原始 JSON 对象 | 校验工作流状态，提取意图和回复；源总览要求清理推理内容、映射前端动作 |
| 业务数据 | 提供公共数据库会话及响应工具 | 查询活动/课程、提交报名、保存会话/消息；Dify 不直接连接或写入业务数据库 |
| 失败处理 | 提供底层异常及日志能力 | 记录错误、返回客服兜底话术 |

#### 2. mock / real 配置

源总览通过 DIFY_CLIENT 选择 mock 或 real：mock 用关键词模拟七类场景，无外部模型依赖；real 使用 DIFY_AGENT_API_KEY 调用发布后的客服工作流。DIFY_API_BASE 指定本地服务地址，DIFY_API_TIMEOUT_SECONDS 指定超时。各项由服务端环境配置读取，文档不记录真实密钥。

源总览描述缺少 Key 时走兜底、不改变前端接口；当前目录的 real 实现仍需按第六节核实，不能把配置 real 等同于已经可用。

#### 3. 四类知识库与工作流资产

| 资产 | 功能范围 |
| --- | --- |
| 公司信息知识库 | 机构概况、联系方式、业务板块及部门架构 |
| 公司业务知识库 | 德国双元制、新加坡本硕升学等项目资料 |
| 留学政策知识库 | 德国/新加坡签证、学费、奖学金及就业移民资料 |
| FAQ 知识库 | 源总览列出的 36 条标准问答，区别于关系库 FAQ 兜底表 |
| 客服 Workflow DSL | 源总览描述 20 节点：意图分类、四类知识检索、七类话术分支及结束输出；导入后需绑定模型和知识库 |

### 客户研判的大模型辅助抽取（可选新增）

来源：`sgtallm.md` 2.1、4.3、5.4。客户研判的最终判定以甲方《用户画像研判规则》及规则引擎为准，Dify 仅可辅助非结构化信息提取，不替代规则裁决。

调用目标为 `parser → extractor → clients/extract_dify.py → 公共 DifyHttpClient`；可选资产为 `dify/customer-extract.yml`。抽取应用使用独立应用及 Key，校验工作流业务状态与输出结构，不仅检查 HTTP 200。

新增文档没有给出抽取应用 Key、规则配置的确切环境变量名、请求字段、输出模型、文件传输方式、超时及失败回退契约，均待负责人补齐；不借用客服 Key，不把新增目录树当作已经运行的客户端。

### 智能报告 Workflow 调用与边界

来源：`cyl合并后.md` 4.2、4.4 与目录树。目标调用链为 `report_service → report_metrics 固定取数/指标计算 → clients/report_dify.py → 公共 DifyHttpClient → 智能报告 Workflow`；传入 report_code 与 metrics，读取 report_text，剥离 `<think>` 推理内容后保存正文和指标快照。

资产为 `dify/report/report.yml`、`dify/report/README.md`。本轮已核对app/clients/report_dify.py与app/config.py：REPORT_DIFY_API_KEY独立配置，地址取REPORT_DIFY_API_BASE或DIFY_API_BASE，共用DIFY_API_TIMEOUT_SECONDS；POST /workflows/run，response_mode=blocking，inputs含report_code及json.dumps后的metrics，输出读取data.outputs[REPORT_DIFY_OUTPUT_KEY]（默认report_text），并检查data.status=succeeded。变量名、路径和编码已有代码依据；部署Dify版本、模型/知识库绑定、真实成功及失败/重试策略仍待验证，不以HTTP200或去think代替事实正确及脱敏。

“只有生成入口调用 Dify”指生成业务链路；若启用定时生成，调度任务也会复用该链路，而非另一个对外公开模型入口。报告采用固定 SQL 和固定指标口径，NL2SQL 切换为未来待办，不把报告生成解释为可让模型任意执行 SQL。

### 企业 E9：Dify公共HTTP、全部配置与YAML交付

来源：`msj_jlj_原文无损合并.md` 的企业 E9：Dify公共HTTP、全部配置与YAML交付。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

#### 9.1 所有 Dify HTTP 统一使用公共文件

固定使用 `app/core/dify.py` 的 `DifyHttpClient`。业务适配器调用其 `post_json_sync()` 或 `post_json()`，不得另起一套 `requests`/`httpx` 调用 Dify。

| 层 | 负责什么 |
| --- | --- |
| `app/core/dify.py` | POST JSON、Bearer API Key、超时、HTTP 状态、JSON 对象返回 |
| `app/clients/enterprise_dify.py` | 普通模型提取、QA/RAG、语音等 Dify 应用的请求与结果映射 |
| `app/clients/enterprise_nl2sql_dify.py` | 独立的通用只读 NL2SQL 请求/结果映射，供通用服务注入调用 |
| `app/services/enterprise_command.py` | 业务意图、预览、确认和固定服务分发，不自行 HTTP 调模型 |
| `app/services/enterprise_nl2sql.py` | schema 组装、生成器编排、只读策略和查询协调 |

普通模型提取采用 Workflow：后端通过公共传输层请求 `/workflows/run`，输入为 `text、action_catalog、field_schema、context、contract_version`，输出为结构化 `result`。适配器同时检查 Workflow 成功状态、结果类型、契约版本及字段白名单；HTTP 200 不等于 Workflow 业务成功。

通用 NL2SQL Workflow 采用独立应用和第 8 节输入，输出结构化 `query_result`，不把字段改名后又套回旧的 question-only 适配器。Dify 外层协议仍可复用 `/workflows/run`，复用 HTTP 协议不等于复用旧业务契约。

#### 9.2 `.env` 配置

**API Key、数据库密码、JWT 密钥及本模块签名/加密密钥统一从 `StuProject/.env` 经 `app/config.py` 读取。**下表为配置方案，本轮未写入或修改 `.env`，也未复制其中任何真实值。

| 变量 | 状态/用途 |
| --- | --- |
| `DIFY_API_BASE` | 已有公共 Dify 地址，包含基础 API 路径；所有企业 Workflow 共用 |
| `DIFY_API_TIMEOUT_SECONDS` | 已有配置字段，Dify 请求超时 |
| `ENTERPRISE_EXTRACT_DIFY_API_KEY` | 拟新增，普通模型字段提取应用 Key |
| `ENTERPRISE_NL2SQL_DIFY_API_KEY` | 拟新增，独立通用只读 SQL 生成应用 Key，不回退到旧通用 Key |
| `ENTERPRISE_KNOWLEDGE_DIFY_API_KEY` | 拟新增，新人QA/RAG单一应用Key；两分支由同一发布应用处理，当前使用明确占位值 |
| `ENTERPRISE_SUMMARY_DIFY_API_KEY` | 拟新增，授权日报即时摘要应用 Key |
| `ENTERPRISE_VOICE_DIFY_API_KEY` | 历史语音Dify方案变量；用户已改选faster-whisper，本期不要求、不启用、不在示例中保留假Key |
| `ENTERPRISE_DIFY_CONTRACT_VERSION` | 拟新增，企业提取/查询结果版本标识 |
| `AUTH_SECRET_KEY` | 公共登录 JWT 密钥，由公共设置统一读取；是否配置正确待后续验证，不在此声明已核验实际值 |
| `STUDENT_DIFY_KEY` / `STUDENT_SYNC_TOKEN` / `STUDENT_ACTION_SECRET` | 学生应用、服务同步与业务凭证专用；均从根 `.env` 经 `app/config.py` 读取，与学生文档一致 |
| `ENTERPRISE_CONFIRM_SECRET` | 拟新增，业务确认凭证签名；不与登录 JWT 或 Dify Key 混用 |
| `ENTERPRISE_PHONE_ENCRYPTION_KEY` | 拟新增，电话字段加密 |
| `ENTERPRISE_PHONE_LOOKUP_SECRET` | 拟新增，标准化电话匹配 token 的 HMAC 密钥 |
| `ENTERPRISE_READ_DB_USER` / `ENTERPRISE_READ_DB_PASSWORD` | 拟新增，只读查询连接凭据；地址/库名沿用公共数据库配置 |
| `DB_*` | 已有公共写库配置，硬编码业务服务使用 |
| `ENTERPRISE_SCORE_AUTHORITY` | 已有配置字段：`local` / `external_readonly`，决定成绩是否允许本地写入 |

供应商模型名称、供应商绑定在实际 Dify 环境中配置；StuProject `.env` 的应用 Key 用于调用已发布应用，不会自动变成 Dify 工作区的模型供应商 Key。若部署还需要供应商密钥，应由部署配置受控映射，不能将真实值写入 YAML、提示词或前端。

配置交付使用已建立的纯占位.env.example；根.gitignore忽略真实.env并保留示例。此交付项不再列为配置问题；真实密钥与运行.env不变。启动时按启用功能校验必要变量，缺 Key 返回依赖不可用，不静默使用其他模块的 Key；不独立加载 `.env.student.local` 或 `STUDENT_DIFY_BASE`。

#### 9.3 Dify YAML 放置位置与节点职责

所有拟生成的 Dify DSL `.yml` 置于根目录 `dify/enterprise/`，不放入 `app/` 或业务文档目录。

| 拟交付文件 | 工作流及节点 |
| --- | --- |
| `enterprise_extract.yml` | Start → 普通 LLM 提取动作/字段 → 结构化结果校验 → End；不生成 SQL，不请求写库接口 |
| `enterprise_nl2sql_readonly.yml` | Start（独立 schema 契约）→ 只读 SQL 生成 → 输出 SQL 模板及参数引用 → End；最终安全校验在 Python 后端 |
| `enterprise_onboarding_qa.yml` | 已授权 QA 候选 → 标准问答匹配 → 带来源答案；无匹配不编造 |
| `enterprise_onboarding_rag.yml` | 已限定可访问资料 → 检索 → 基于来源回答 → 引用/无依据说明；权限过滤在检索前完成 |
| `enterprise_daily_summary.yml` | 仅接收后端已筛选的日报 → 提炼进展/产出/风险 → 即时摘要；不自行查询全团队 |
| `enterprise_voice_transcribe.yml` | 语音交付阶段的转写应用；文件上传/转写协议按实际 Dify 部署核验，通过公共客户端适配 |
| `README.md` | 导入步骤、部署版本、模型绑定、知识库绑定、输入输出契约、环境变量名和联调说明 |

普通模型用支持结构化输出的常规模型完成提取即可，不需要用 NL2SQL 替代字段提取。提取模型与 SQL 模型可以不同，但后端输出契约保持稳定。首期 QA 与 RAG 两条路径均给出方案，资料不足时优先使用已审核 QA，不默认两套知识内容已经备齐。

真实 YAML 生成后还需要在目标 Dify 实例导入并发布、绑定模型及知识库、取得各自应用 Key，再写入服务端 `.env`。仅生成文件不等于工作流已可用，本轮也未生成 YAML。


### 学生 S五：唯一学生Workflow

来源：`msj_jlj_原文无损合并.md` 的学生 S五：唯一学生Workflow。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

学生页面调用统一聊天接口，后端先读取本人记录和已审核资料，再调用唯一 Dify Workflow；模型返回后由后端校验意图、参数和权限。查询返回事实，咨询展示来源，办理形成确认预览。

| 分工 | 公共模块 / 外部依赖 | 学生模块负责 |
| --- | --- | --- |
| 身份与权限 | 公共账号、JWT 和公共权限配置 | 学生归属、老师负责关系、业务状态及确认凭证校验 |
| Dify 连接 | 唯一公共传输 `app/core/dify.py` 的 `DifyHttpClient` | `student_assistant_dify` 只适配应用契约；地址读 `DIFY_API_BASE`，应用 Key 读 `STUDENT_DIFY_KEY` |
| 模型能力 | 模型供应商需真实可用 | 唯一统一 Workflow、提示词、结构化输出契约 |
| 数据查询 | 本地固定查询，或组长 student-v1 适配服务 | 本人范围与字段白名单，不接受模型生成的可执行 SQL |
| 业务执行 | 共用业务数据库及公共事务能力 | 固定服务落库、审计及通知，确认时不再次调用模型 |
| 知识与项目 | 资料负责人维护真实来源，项目模块维护上架项目 | 检索已审核资料、展示依据；缺资料时明确无法核实 |

学生侧只规划部署 `dify/student/` 下的统一应用；企业侧独立应用位于 `dify/enterprise/`，应用数量不同不影响协作。历史最小单元仅作参考。模型供应商、DSL 导入、应用发布、密钥和真实调用均需后续验证，本文件不宣称已导入或通过真实模型验收。


### 普通模型写动作、只读NL2SQL与语音传输的边界

企业写入由普通模型提取字段，服务端预览确认后调用固定业务服务；学生确认同样不再次调用模型。企业enterprise_nl2sql为独立schema契约，不强制所有业务统一切换；报告继续固定SQL，学生默认local固定查询，group模式另需student-v1业务响应适配。

DifyHttpClient目前仅JSON POST。当前语音改为faster-whisper本地库调用，音频上传在受保护业务入口处理，不为本地ASR另建Dify客户端，也不要求扩展公共Dify传输上传音频；若未来改为远程ASR再独立冻结适配协议。文本提取/问答等Dify调用仍用唯一公共HTTP工具，不能把文本输入当作语音已实现。


### 当前配置示例与分类调度目标

本轮新增项目根.env.example（纯占位）和“业务文档/09杂谈/马睿智/配置示例/”下的report-schedule.example.json、integrations.example.json，并更新.gitignore忽略真实.env、保留.env.example。未改动现有.env、app/config.py、SQL、数据库、Dify或部署服务；没有启动任务。

占位Key以app-PLACEHOLDER_开头，不是有效Dify Key；JWT/业务签名/同步Token等运行凭据保持空值并注明部署时生成，不使用公开假密钥签发可用身份。模板中当前未声明的企业/学生字段单列为规划项，不能认为复制示例即可运行；集成JSON是接口接入清单，不是当前已有加载器。外部地址使用.invalid域名占位，不指向真实第三方。

| report_code | 分类周期 | 北京时间生成时间 | 时区 |
| --- | --- | --- | --- |
| daily_report | day | 每天17:00 | Asia/Shanghai |
| customer_overview | week | 每周五17:00 | Asia/Shanghai |
| weekly_report | week | 每周五17:00 | Asia/Shanghai |
| mental_weekly | week | 每周五17:00 | Asia/Shanghai |
| complaint_weekly | week | 每周五17:00 | Asia/Shanghai |

分类来自cyl.md报告列表及all.sql现有种子（本轮只读），不是把全域客户经营报告自行改为日报。report-schedule.example.json用period/local_time/weekday表达目标，避免未经验证的cron方言：all.sql旧种子是含秒的六字段，周五数字约定与调度库须适配核对；不把POSIX五字段或另一调度库表达式直接当现有可运行配置。

调度JSON保留target_enabled=true、execution_enabled=false：前者表示用户要求交付并启用定时能力，后者只表示当前示例不执行。完成应用发布、实际上游/指标、权限/审计和幂等调度后，由系统管理员按授权配置启用；不存在已接通上游时不定时生成伪造报告。真实生成窗口继续与触发时间分开定义，不因周五17:00执行就推断周五之后的数据已经完整。

本轮后续选择已更新为本地教务/CRM、faster-whisper及个人页通知，当前无需外部系统地址、云ASR Key、webhook或群机器人。示例已同步移除这些外部占位项；实际实现仍需后续按范围落地，密钥只在本机配置。

## 六、通用功能复用、职责及交付核对

### 公共模块（主体）

数据库会话、统一配置、密码与 Token 管理、请求参数校验与公共响应模型均纳入本模块公共能力，已同步列入第一节功能接口表。

| 通用功能 | 当前情况 | 使用方式 / 分工 |
| --- | --- | --- |
| 数据库连接和请求级会话 | 已有 `engine`、`SessionLocal`、`Base`、`get_db()`、`dispose_db()` | 各业务共用连接池和 ORM 基类；请求异常回滚并关闭会话，提交事务仍由业务服务明确执行；不自动建表 |
| 统一配置管理 | 已有 `app/config.py` | 从项目根目录 `.env` 读取数据库、日志、认证和 Dify 配置；各业务新增配置项时统一声明，不复制配置文件 |
| 密码哈希与 Token 管理 | 已有密码哈希、校验和 JWT 签发/解析 | 账号创建时复用 `hash_password()`；受保护接口复用认证依赖；当前未提供独立注册、找回密码、刷新 Token 或退出登录接口 |
| Pydantic 请求校验与公共响应模型 | 已有基础设施 | 各业务在 schemas 定义自身字段，公共层提供 ResponseModel 和统一错误出口；全路径校验错误格式仍待补齐 |

NL2SQL 可作为跨模块复用的业务服务，但它包含 SQL 生成、查询执行及权限范围策略，不属于“只发送 HTTP”的 Dify 公共传输层。通知、工单审计、幂等和业务状态机也需业务规则，不将其自动纳入本人的已完成公共功能。

### 客服模块（合并内容）

#### 1. 复用公共能力

| 通用功能 | 客服模块使用方式 | 分工 |
| --- | --- | --- |
| 数据库连接和请求级会话 | 复用 get_db、ORM 基类及连接池 | 公共层维护连接，客服服务维护业务事务 |
| 统一配置管理 | 读取 Dify 模式、应用 Key、地址、超时及数据库配置 | 配置字段由后端统一声明，各业务维护自己的应用值 |
| 日志及统一异常处理 | 记录模型失败，处理业务错误 | 复用公共工具，客服负责业务错误及兜底策略 |
| 参数校验与公共响应模型 | 客服 schema 校验请求并定义响应，复用统一返回格式 | 各接口字段由客服模块维护 |
| Dify HTTP 请求 | real 场景客户端按源总览设计复用 DifyHttpClient | HTTP 工具由公共模块维护，客服负责应用及结果解析 |

#### 2. 交付状态入口

客服路由、real客户端、消息事务、报名并发及资产的差异与剩余交付事项统一见第十八章。

### 客户研判的公共能力复用与交付状态

客户研判复用 JWT、权限依赖、get_db、日志、统一响应、配置，以及可选的 Dify HTTP 工具。客户研判负责人维护来源接入、文件解析、字段提取、规则引擎、八接口与五表；公共负责人维护公共组件，数据库负责人审核增量结构。

`sgtallm.md` 将客户研判标为“规划中”，且声明未读取实际目录。本次未启动服务、访问模型或数据库；所有研判文件、接口、表、规则及 DSL 均为方案/待核验，不认定已存在或可用。公共响应仍存在原文记载的异常出口差异，新增模块需接入最终约定，不能直接宣称三模块所有响应已经统一。

### 报告公共能力复用与业务责任

来源：`cyl合并后.md` 4.1、4.4。公共模块维护认证、鉴权、配置、会话、日志、响应与 HTTP 工具；陈宇林负责报告配置、指标口径、异步生成、场景适配、心理周报脱敏、定时生成和报告三表。

边界继续保留：

- 日报「内容级摘要」属企业模块，报告只做数量级指标或复用 `employee_daily_report.ai_summary`。
- 心理「风险识别」属学生模块，报告只读 `mental_health_profile` / `mental_warning` 做聚合。
- NL2SQL 切换为未来待办，当前取数用固定 SQL。

报告只读上游业务表、不回写其状态；是否持有 ORM 与是否具备数据库写权限是两件事，应另行验证只读策略。报告不重新实现客户研判规则引擎、心理风险识别、员工日报内容级摘要或客服获客逻辑。心理取数/脱敏、投诉指标口径、路由鉴权及调度等均为来源列出的待办或待核验项。

### 学生 S六：公共能力复用、对接与开发边界

来源：`msj_jlj_原文无损合并.md` 的学生 S六：公共能力复用、对接与开发边界。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

#### 1. 公共能力分工

| 通用功能 | 学生模块使用方式 | 说明 |
| --- | --- | --- |
| 公共登录与权限 | 复用 auth、authorization、access_control | 业务身份由公共账号关联，不能凭前端传入 student_id 冒充他人 |
| 配置管理 | 根目录 `.env` 经 `app/config.py` 统一读取 | 学生专用变量也声明在公共设置入口，不再独立加载 `.env.student.local` 或 `STUDENT_DIFY_BASE` |
| 数据库与数据访问 | 目标 API→Service→Repository/Model 分层 | 共享表只保留一套元数据；写入经固定服务和参数化仓储，结构仍待实现与测试 |
| 参数契约 | schemas 定义学生、老师、同步及模型输出 | 业务参数与智能体动作参数分别校验 |
| 后台任务 | StudentTasks 与 run_student_tasks | 提醒、通知、补分派及失败重试，需持续运行 |
| 幂等、审计和会话隔离 | 固定业务服务及对应持久化表 | 均为开发及待验证目标，不引用历史回归数证明落地 |

#### 2. 对接对象、职责及当前边界

| 对接对象      | 现有入口或配置                                           | 对方需要提供/实现什么                                   | 对接成功应看到的效果            | 当前边界               |
| --------- | ------------------------------------------------- | --------------------------------------------- | --------------------- | ------------------ |
| 组长公共认证 | `/api/v1/auth/login`、公共 JWT 依赖与权限配置 | 配置有效账号、身份外键和目标权限 | 学生只见本人，老师只处理授权记录 | 开发中，待身份及越权测试 |
| 组长查询服务    | 默认 STUDENT_QUERY_BACKEND=local；可切 group           | 若切 group，提供 student-v1 受控查询响应，不是任意自然语言 SQL 接口 | 查询结构、身份和字段与本地一致       | group 模式预留，未验证真实远端 |
| 企业/老师请假模块 | 学生模块维护的 10 个老师协作接口 | 企业开发页面和调用编排；学生开发唯一请假审批与预警固定服务 | 学生提交→老师审批→学生结果 | 双方开发中，未完成联合测试；企业不新增重复老师路由 |
| 企业售后工单模块  | 共用 service_ticket、service_ticket_record           | 对齐已有企业工单接口、分派/处理流程、状态值与版本规则                   | 企业回应后学生可查记录，解决后可确认或重开 | 不编造尚未核实的企业 URL     |
| 本地教务模块 | 本项目教务页面→公共JWT→教务固定服务；现有成绩local模式 | 学生/课程/成绩/考试/DDL的授权维护与版本审计，不默认依赖外部URL | 学生仅见本人数据，节点改期更新提醒 | 页面、完整维护接口和结构仍待实现 |
| 本地CRM/申请模块 | 本项目客户/跟进/申请进度页面→固定服务 | 顾问维护本人客户和申请进度，主管本部门；客户学生关联受控确认 | 学生查看本人授权进度及更新时间，模型不推进状态 | 本地权威来源及字段语义待实现 |
| 资料维护模块 | STUDENT_KNOWLEDGE_FILE | 提供审核过的生活/升学资料、来源和启停状态 | 有依据，撤下资料不再使用 | 待提供正式资料并测试 |
| 项目/客服模块   | course_project 固定只读查询                             | 维护上架项目及报名方式；承接进一步咨询                           | 推荐来自真实项目，学生有真实后续联系渠道  | 未实现自动报名/生成线索       |
| 个人页站内通知 | StudentTasks/EnterpriseTasks及本人消息列表/已读接口 | 按event_code前缀领取、事务入队、去重及发布为可读；不接群机器人或外部推送 | 学生个人页收结果，员工个人页收待办；只能读本人通知 | 消息页/任务/收件人鉴权仍待实现验证 |
| Dify 平台 | `DIFY_API_BASE` + `STUDENT_DIFY_KEY` + 统一 Workflow | 提供可用模型、发布应用、严格 JSON 输出 | 结构化结果进入固定业务链 | 待真实模型与完整业务测试 |

#### 3. 查询、同步及通知契约

组长查询默认使用 local，可切 group。group 请求使用 student-v1，包含 contract_version、scenario、subject、filters、limit、offset；响应要求 code=0，data 包含 contract_version、subject_id、scenario、rows、total。每行携带正确 student_id，字段必须在白名单中。现有服务若只接自然语言并返回 SQL，需增加适配层或继续使用本地固定查询，不能直接把任意 NL2SQL Workflow 地址当作完成接入。

student_profile.student_id 是内部主键；external_student_id 为教务外部编号，crm_student_id 为 CRM 外部编号。来源响应必须回传同一外部编号并提供 source_system、records。时间带时区，来源更新时间用于版本保护，不能只改字段名就假定是同一个学生。

当前通知仅写business_notification并发布到本人站内消息页，页面刷新或轮询读取，channel采用站内渠道目标in_app。学生接收本人审批/工单/提醒结果；员工接收本人待办及分派通知。不再配置外部webhook、短信、邮件、企业微信或飞书群机器人；旧外部适配规则仅保留未来参考。消息可读、已读及业务已处理分别记状态，不能因页面已读就批准请假或关闭工单。

#### 4. 开发与验证边界

本文件列出的是目标设计及分工，不保留“已提交完整功能”“79 项通过”“本地账号或站内通知已验证”等作为本次结论。两个模块均未完成落地测试，需要按附录 B 的共同验收清单逐项取得证据。

是否已具备真实模型、正式教务/CRM 来源、制度资料、通知渠道和可用页面均待核验。文档中所有接口、字段、约束和流程均不表示数据库或服务已经部署。本轮不运行业务测试或迁移。


### 新增模块的职责与服务唯一性

企业负责客户/跟进、日报、组织/知识、成绩受控维护、企业工单动作与工作台；学生负责学生入口、唯一StudentLeaveService、老师协作、心理/节点/进度/会话及学生任务。投诉共用一张service_ticket及过程记录，企业不能代学生确认关闭、重开或评价；其他模块也不得复制审批状态机。

学生文档明确负责人蒋立建；企业来源未给负责人姓名，保留企业模块负责方而不根据文件简称猜测。共享Table/ORM不能在同一元数据重复声明，公共连接/异常处理不替业务服务自动提交事务。


## 七、架构目录（文件名及功能作用）

### 公共模块（主体）

以下列出公共模块涉及的目录、主要文件及作用。目录树为文件索引，不包含实现代码。各业务的模型配置、工作流及业务适配逻辑仍由对应负责人维护。

```text
D:/AI/StuProject/
├── .env                         项目配置：数据库、日志、JWT 密钥及各业务 Dify 应用凭据
├── environment.yml              项目运行环境及依赖声明
├── app/
│   ├── main.py                  FastAPI 入口：路由挂载、日志初始化、异常处理及生命周期
│   ├── config.py                统一配置：读取 .env 并提供配置对象
│   ├── database.py              数据库连接池、ORM 基类、请求级会话及连接释放
│   ├── access_control.yaml      用户身份到权限的映射、页面及模块访问策略
│   ├── api/
│   │   └── auth.py              登录、公开访问清单、当前用户权限清单 HTTP 接口
│   ├── core/
│   │   ├── auth.py              JWT 身份认证依赖：校验 Token、查询当前账号
│   │   ├── authorization.py     公共鉴权组件：逐接口检查权限并计算访问清单
│   │   ├── logger.py            日志初始化、日志对象获取及控制台/文件输出
│   │   ├── response.py          统一响应模型、成功/失败返回及全局异常处理
│   │   └── dify.py              本地 Dify 通用同步/异步 JSON HTTP 请求封装
│   ├── services/
│   │   └── auth_service.py      账号密码校验、密码哈希、JWT 签发及解析
│   ├── models/
│   │   └── user_account.py      user_account 用户表 ORM 映射及身份关联
│   ├── schemas/
│   │   └── auth.py              登录请求字段及参数约束
│   ├── clients/                 各业务应用适配器；复用公共 HTTP 工具
│   │   ├── nl2sql_dify.py       NL2SQL 应用输入构造及输出解析，属于场景适配
│   │   └── report_dify.py       报告应用输入构造及输出解析，属于场景适配
│   └── logs/                    默认运行日志输出目录
└── scripts/
    └── sql/
        └── all.sql              统一数据库建表脚本，包含 user_account 及关联表
```

各 Python 包内的 __init__.py 为包初始化文件，目录树省略重复列举。clients/ 中的业务适配器用于说明公共 HTTP 工具的调用位置，不表示其模型配置和业务解析也由本模块负责人承担。数据库建表脚本由团队统一维护，公共账号模型与其保持一致。

各业务接入时，先为接口声明 JWT 认证和权限依赖，再按需使用公共配置、数据库会话、参数校验和日志工具；模型调用复用 Dify HTTP 封装，业务结果通过统一返回工具输出。

### 客服模块（合并内容）

#### 1. 当前可见的主要文件

```text
D:/AI/StuProject/
├── .env                              服务端环境配置；不在文档中披露真实值
├── app/
│   ├── main.py                       FastAPI 应用入口；客服路由挂载现状见第六章“客服模块”交付核对
│   ├── config.py                     统一配置入口；客服专用配置声明待核对补齐
│   ├── database.py                   MySQL 引擎、会话、ORM 基类及 get_db 依赖
│   ├── api/
│   │   └── agent.py                  六个客服 HTTP 接口、参数依赖及返回组织
│   ├── services/
│   │   ├── agent_service.py          对话编排、会话消息、活动报名、课程及 FAQ 业务
│   │   └── dify_client.py            客服 mock / real 客户端及切换入口
│   ├── schemas/
│   │   └── agent.py                  客服请求和响应字段、Pydantic 校验模型
│   ├── models/
│   │   └── agent.py                  六张客服业务表的 SQLAlchemy ORM 映射
│   └── core/
│       ├── dify.py                   公共 Dify HTTP 请求工具
│       ├── logger.py                 公共日志工具
│       └── response.py               统一返回模型、业务异常及全局异常处理
├── scripts/
│   └── sql/
│       ├── all.sql                   统一建表脚本，包含客服六张表

```

#### 2. 源总览列出的其他资产（当前目录未发现，待交付核实）

| 文件路径（相对系统根目录） | 源总览中的功能作用 |
| --- | --- |
| `dify/客服Agent-Chatflow.yml` | 客服 Workflow DSL，导入 Dify 后绑定模型和知识库 |
| `dify/README.md` | DSL 导入、字段对齐、版本兼容和知识库维护说明 |
| `dify/knowledge/README.md` | 四类知识库的作用、内容范围和维护流程 |
| `dify/knowledge/公司信息.md` | 公司信息知识库源资料 |
| `dify/knowledge/公司业务.md` | 公司业务知识库源资料 |
| `dify/knowledge/留学政策.md` | 留学政策知识库源资料 |
| `dify/knowledge/FAQ.md` | FAQ 知识库源资料，源总览描述为 36 条问答 |
| `dify/knowledge/dataset_ids.json` | 知识库 dataset_id / document_id 映射及 DSL 绑定依据 |
| `scripts/sql/agent_seed.sql` | 源总览描述的 7 门课程、4 个活动、8 条 FAQ 种子数据 |
| `scripts/reupload_dify_kb.py` | 按空行分段重新上传四类知识库；源总览说明会删除旧文档 |
| `scripts/test_dify_kb.py` | 四类知识库检索命中验证 |
| `scripts/test_workflow_run.py` | 七类场景直接调用 Workflow 的联调验证 |
| `业务文档/03开发设计/客服Agent-Dify-Chatflow搭建方案.md` | 工作流节点、输入输出契约及后端对接说明，源总览所列关联文档 |

目录和文件清单用于定位职责，不含实现代码。客服模块维护自己的场景业务和 Dify 应用，公共模块提供数据库会话、日志、响应及 HTTP 传输组件；模型生成话术，后端作为业务落库入口，前端根据动作请求真实业务数据。

### 三模块统一目录索引（新增方案，不替代前述状态）

来源：`sgtallm.md` 2.1。以下保留完整统一目录树，已存在、待交付与可选状态仍需逐项核验。

目录名与文件名沿用源文档原文（客服资产、客户研判文件均按 sgt.md/主文档列出的名字），未读取实际目录。括号标注主责模块：〔公共〕〔客服〕〔客户研判〕〔待交付/可选〕。

```text
D:/AI/StuProject/
├── .env                               项目配置：数据库、日志、JWT 及各业务 Dify 凭据〔公共+客服+客户研判合并，真实值不入文档〕
├── environment.yml                    项目运行环境及依赖声明〔公共，合并三方依赖〕
├── dify/                              Dify 应用与知识库资产
│   ├── 客服Agent-Chatflow.yml         客服 Workflow DSL〔客服，待交付〕
│   ├── customer-extract.yml           客户研判字段抽取 Workflow DSL〔客户研判，可选/待交付〕
│   ├── README.md                      Dify 资产导入与维护说明〔待交付〕
│   └── knowledge/
│       ├── README.md                  知识库维护流程〔待交付〕
│       ├── 公司信息.md                 公司信息知识库〔客服〕
│       ├── 公司业务.md                 公司业务知识库〔客服〕
│       ├── 留学政策.md                 留学政策知识库〔客服〕
│       ├── FAQ.md                     FAQ 知识库〔客服〕
│       ├── 客户画像研判规则.md          《用户画像研判规则》源文件〔客户研判，依据甲方文件〕
│       └── dataset_ids.json           知识库 dataset_id/document_id 映射〔客服〕
├── app/
│   ├── main.py                        FastAPI 入口：挂载 auth、agent、customer 路由〔公共，合并三方挂载〕
│   ├── config.py                      统一配置：公共 + 客服 + 客户研判配置项〔公共〕
│   ├── database.py                    数据库连接池、ORM 基类、请求级会话及释放〔公共〕
│   ├── access_control.yaml            身份权限映射：公共 + 客户研判 customer.* 权限〔公共〕
│   ├── api/
│   │   ├── auth.py                    登录、公开清单、当前用户权限清单〔公共〕
│   │   ├── agent.py                   客服六个 HTTP 接口〔客服〕
│   │   └── customer.py                客户研判八个 HTTP 接口〔客户研判〕
│   ├── core/
│   │   ├── auth.py                    JWT 身份认证依赖〔公共〕
│   │   ├── authorization.py           逐接口权限鉴权组件〔公共〕
│   │   ├── logger.py                  日志初始化与获取〔公共〕
│   │   ├── response.py                统一返回模型、业务异常及全局异常处理〔公共〕
│   │   └── dify.py                    本地 Dify 同步/异步 JSON HTTP 请求封装〔公共〕
│   ├── services/
│   │   ├── auth_service.py            账号密码校验、密码哈希、JWT 签发/解析〔公共〕
│   │   ├── agent_service.py           客服对话、报名、课程、FAQ 业务〔客服〕
│   │   ├── dify_client.py             客服 mock / real 客户端及切换〔客服〕
│   │   ├── customer_service.py        客户研判接入、解析调度、结果组装〔客户研判〕
│   │   ├── parser.py                  多格式解析：文本、PDF、Excel 分派与归一化〔客户研判〕
│   │   ├── extractor.py               关键字段提取逻辑〔客户研判〕
│   │   └── judge_service.py           画像研判规则引擎：加载规则、逐条比对〔客户研判〕
│   ├── models/
│   │   ├── user_account.py            公共账号 ORM〔公共〕
│   │   ├── agent.py                   客服六表 ORM〔客服〕
│   │   ├── customer_source.py         客户信息来源表 ORM〔客户研判〕
│   │   ├── customer_info.py           客户关键字段表 ORM〔客户研判〕
│   │   ├── research_rule.py           研判规则表 ORM〔客户研判〕
│   │   ├── product.py                 甲方产品表 ORM〔客户研判〕
│   │   └── research_result.py         研判结果表 ORM〔客户研判〕
│   ├── schemas/
│   │   ├── auth.py                    登录请求字段及参数约束〔公共〕
│   │   ├── agent.py                   客服请求/响应字段〔客服〕
│   │   └── customer.py                客户研判请求/响应字段〔客户研判〕
│   ├── clients/                       各业务 Dify 适配器，复用公共 HTTP 工具
│   │   ├── nl2sql_dify.py             NL2SQL 场景适配〔公共，场景负责人维护〕
│   │   ├── report_dify.py             报告场景适配〔公共，场景负责人维护〕
│   │   └── extract_dify.py            客户研判字段抽取适配〔客户研判〕
│   └── logs/                          默认运行日志输出目录〔公共〕
└── scripts/
    ├── sql/
    │   ├── all.sql                    统一建表脚本：公共 + 客服 + 客户研判〔公共/数据库负责人〕
    │   └── agent_seed.sql             客服种子数据〔客服，待交付〕
    ├── reupload_dify_kb.py            知识库重传脚本〔客服，待交付〕
    ├── test_dify_kb.py                知识库检索验证〔客服，待交付〕
    └── test_workflow_run.py           客服工作流联调〔客服，待交付〕
```

各 Python 包内的 `__init__.py` 省略。`clients/` 中三个适配器只说明公共 HTTP 工具的调用位置，模型配置、Prompt、知识库与输出解析归各场景负责人。客户研判的 `extract_dify.py` 仅在启用大模型辅助解析时使用；规则判定不依赖它。

目录中 `nl2sql_dify.py`、`report_dify.py` 的“公共”仅指复用公共传输能力，业务适配器仍归各自场景负责人，并非本次新增公共基础能力；不能据此把其他场景纳入已完成交付。

### 四模块统一目录增补（保留研判模块）

以 `cyl合并后.md` 2.1 的完整目录为底稿，补入上一轮研判路径。此前“公共/客服”“公共/客服/研判”的目录仍为对应范围的历史索引，本节用于本轮四模块导航。所有“新建”“已含”“DDL 一致”均为源方案标注，本次未读取实际目录或实现，不等于资产已交付。

```text
D:/AI/StuProject/
├── .env                               服务端配置（数据库、日志、JWT、各业务 Dify Key）
├── environment.yml                    依赖与环境
├── .gitignore                         忽略规则（.env、日志、缓存、本地运行数据）
├── app/
│   ├── main.py                        FastAPI 入口：按交付状态挂载 auth / agent / customer / report 路由
│   ├── config.py                      统一配置
│   ├── database.py                    连接池、ORM 基类、get_db 会话
│   ├── access_control.yaml            身份→权限映射（含 report.* 收敛）
│   ├── api/
│   │   ├── auth.py                    公共：登录、公开清单、当前权限（3 个接口）
│   │   ├── agent.py                   客服：对话、活动、报名、课程、FAQ（6 个接口）
│   │   ├── customer.py                客户研判八接口（规划）
│   │   └── report.py                  报告：生成、查单份、列表、查/改配置（5 个接口）
│   ├── core/
│   │   ├── auth.py                    JWT 身份认证
│   │   ├── authorization.py           逐接口鉴权
│   │   ├── logger.py                  日志
│   │   ├── response.py                统一返回与异常
│   │   ├── dify.py                    本地 Dify HTTP 传输（同步/异步）
│   │   └── report_auth.py             报告管理员鉴权依赖（新建）
│   ├── services/
│   │   ├── auth_service.py            公共账号与 JWT
│   │   ├── agent_service.py           客服业务编排
│   │   ├── dify_client.py             客服 mock/real 客户端
│   │   ├── customer_service.py        客户研判编排（规划）
│   │   ├── parser.py                  text/pdf/excel 解析（规划）
│   │   ├── extractor.py               字段提取（规划）
│   │   ├── judge_service.py           研判规则引擎（规划）
│   │   ├── report_service.py          报告配置读写 + 异步生成
│   │   ├── report_metrics.py          报告取数与固定指标（新建）
│   │   └── report_anonymizer.py       心理周报脱敏（新建）
│   ├── models/
│   │   ├── user_account.py            公共账号
│   │   ├── agent.py                   客服六表 ORM
│   │   ├── customer_source.py / customer_info.py  研判来源与结构化信息（规划）
│   │   ├── research_rule.py / product.py / research_result.py  研判规则、产品与结果（规划）
│   │   └── report.py                  报告三表 ORM
│   ├── schemas/
│   │   ├── auth.py / agent.py / customer.py / report.py
│   ├── clients/
│   │   ├── nl2sql_dify.py             NL2SQL 场景适配
│   │   ├── extract_dify.py            客户研判可选抽取适配（规划）
│   │   └── report_dify.py             报告 Workflow 适配
│   ├── tasks/
│   │   └── report_tasks.py            报告定时生成（新建）
│   └── logs/                          运行日志
├── dify/
│   ├── 客服Agent-Chatflow.yml          客服 Workflow DSL（待交付核实）
│   ├── README.md / knowledge/          客服知识库资产（待交付核实）
│   ├── customer-extract.yml           客户研判抽取 Workflow（可选/待交付）
│   ├── knowledge/客户画像研判规则.md   客户研判规则源资料（待核验）
│   └── report/
│       ├── report.yml                  智能报告生成 Workflow DSL
│       └── README.md                  报告 Workflow 说明
└── scripts/
    ├── init_report_tables.py          报告三表初始化
    ├── run_report_tasks.py            报告调度进程（新建）
    ├── reupload_dify_kb.py / test_dify_kb.py / test_workflow_run.py   客服联调（待交付核实）
    └── sql/
        ├── all.sql                     统一建表脚本（含全部表）
        ├── agent_seed.sql              客服种子（待交付核实）
        └── bk/智能报告/
            └── report_module_ddl.sql   报告三表 DDL（与 all.sql 一致）
```

`scripts/init_report_tables.py` 与报告 DDL 是初始化/结构资产，不能据文件名认定在有数据环境下可安全执行；`run_report_tasks.py` 是规划的调度入口，本次没有启动。四模块共用一份 main/config/database/core 实现，不因目录并列复制公共代码。


### 报告来源的路径统一

| 冲突点 | 处理方式 |
| --- | --- |
| `D:\AI\StuProject`（主体口径） vs `C:\Users\Windows\PycharmProjects\project_1\StuProject`（另一工作副本） | 文档统一采用主体的 `D:\AI\StuProject`；另一副本仅作为工作副本线索保留，不作为合并基座 |
| 各模块文档使用相对路径（`app/`、`dify/`、`scripts/`） | 均按统一系统目录拼成全路径，相对层级不变 |
| `客户需求表.xlsx` 等桌面路径 | 属个人本地参考，不入统一目录树 |

另一工作副本路径仅是来源线索，不改变用户指定的系统目录或自动决定代码合并基座。个人桌面的《客户需求表.xlsx》本次未读取，不因文档提及而纳入系统交付。

### 企业 E10：完整规划目录与文件职责

来源：`msj_jlj_原文无损合并.md` 的企业 E10：完整规划目录与文件职责。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

下列是后续实施目录，不在本轮创建代码文件；优先复用已有等价文件，避免覆盖其他模块。

```text
StuProject/
├── app/
│   ├── api/
│   │   ├── enterprise.py                  # 企业 HTTP、Schema、权限依赖、结果信封
│   │   ├── student_leave.py               # 学生维护四个请假入口，复用公共 JWT
│   │   └── student.py                     # 学生维护其余业务、老师协作与同步入口；企业不重复注册
│   ├── schemas/
│   │   ├── enterprise.py                  # 请求、模型结果、预览、查询契约
│   │   └── student_leave.py               # 扩展老师查询/审批结果，统一 apply_id 与状态
│   ├── models/
│   │   ├── user_account.py                # 已有公共账号；不重复定义
│   │   ├── student_leave.py               # 复用共享 Table，补齐审批结果字段投影
│   │   └── enterprise.py                  # 未映射的企业/共享表，复用已有元数据
│   ├── core/
│   │   ├── dify.py                        # 已有唯一 Dify HTTP 入口
│   │   ├── auth.py                        # 已有统一登录依赖
│   │   ├── authorization.py               # 已有公共身份权限
│   │   ├── enterprise_authorization.py    # 员工角色与动作数据范围
│   │   └── enterprise_sql_guard.py        # SQL AST 白名单与只读校验
│   ├── clients/
│   │   ├── enterprise_dify.py             # 普通模型、知识、摘要等应用适配
│   │   └── enterprise_nl2sql_dify.py       # 新通用只读查询生成适配
│   ├── services/
│   │   ├── enterprise_command.py          # 提取、预览、确认、动作分发
│   │   ├── enterprise_nl2sql.py           # 仅通用只读 NL2SQL
│   │   ├── enterprise_customer.py         # 客户硬编码功能
│   │   ├── enterprise_daily_report.py     # 日报硬编码功能
│   │   ├── enterprise_score.py            # 成绩硬编码功能
│   │   ├── enterprise_ticket.py           # 工单硬编码功能
│   │   ├── student_leave_service.py       # 学生维护唯一请假服务，企业表单与对话只委托
│   │   ├── enterprise_knowledge.py        # 知识、组织维护协调
│   │   └── enterprise_notification.py     # 待办、站内通知与去重
│   ├── repositories/
│   │   ├── enterprise_repository.py       # 参数化读写、受限查询关系、事务内数据访问
│   │   └── student_leave_repository.py    # 扩展已有请假仓储，条件更新、版本与事务
│   ├── tasks/
│   │   └── enterprise_tasks.py            # 企业提醒扫描、通知投递/重试
│   ├── config.py                         # 追加 .env 字段声明
│   ├── access_control.yaml               # 公共入口策略，企业业务角色由专用层解释
│   └── main.py                           # 核对并挂载已补齐路由，统一公共身份依赖
├── dify/
│   └── enterprise/                       # 本模块所有 DSL 与导入说明
├── frontend/
│   ├── enterprise.html                   # 后续企业工作台
│   ├── js/enterprise.js                  # 页面、预览与确认交互
│   ├── js/api.js                         # 复用客户端，后续补 Bearer/幂等/所需方法
│   └── css/enterprise.css                # 企业页面样式
├── scripts/
│   ├── sql/enterprise/                   # 经差异核对后的增量迁移/种子数据，不放运行时代码
│   ├── run_enterprise_tasks.py            # 独立任务入口
│   └── check_enterprise_contracts.py      # 权限、SQL约束、幂等与状态联调检查
├── .env                                  # 所有本服务密钥，本轮不改
└── 业务文档/
    ├── 04接口设计/                         # 后续更新学生企业侧对接、OpenAPI、请求集合
    └── 06开发文档/接口方案/企业管理/
        └── 企业管理_实施方案说明.md         # 原总体方案位置；本轮只改09杂谈下jlj.md和msj.md
```

`api → service → repository/model` 保持单向依赖；外部应用由 `clients` 适配，公共传输放 `core`；YAML 放 `dify`，初始化/任务启动脚本放 `scripts`。共享表若已由其他 ORM/Table 映射，不在同一元数据中重复声明，也不让本模块启动时自动建表。

上表学生相关文件由学生模块维护，企业不修改出第二套审批服务或重复路由。共享表、Table 和仓储按附录 B 协同设计；学生投递 `student.` 消息，企业投递 `enterprise.` 消息，审批结果由唯一服务生产，不通过企业页面再次生成。

公共重建脚本不作为日常升级入口。后续先核对实际结构和孤儿数据，再按附录 B 生成有明确顺序的增量迁移、索引与外键；本轮未连接数据库。共享表迁移由双方统一交付，不能各自自动重建同一表。


### 学生 S七：完整规划目录与文件职责

来源：`msj_jlj_原文无损合并.md` 的学生 S七：完整规划目录与文件职责。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

以下为目标目录分工，不是当前已完成文件清单。已有可复用实现后续核验后接入；所有 `[新增文件]` 表示规划职责。本轮不创建这些代码文件。请假与心理老师接口只由 `app/api/student.py` 维护，禁止在企业模块重复注册。

```text
StuProject/
├─ app/                                  [已有，继续复用]
│  ├─ main.py                            路由与页面入口，每个方法/路径仅挂载一次
│  ├─ access_control.yaml                公共角色权限，补充学生/负责老师权限
│  ├─ config.py                          公共配置入口，包含学生专用设置
│  ├─ api/                               [已有目录]
│  │  ├─ auth.py                         复用公共登录
│  │  ├─ student_leave.py                学生请假入口，禁止重复注册到 student.py
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
│  │  ├─ student_leave_service.py        唯一共享请假服务：学生提交/撤回/查询、老师审批
│  │  ├─ student_ticket_service.py       [新增文件] 投诉最小单元业务
│  │  ├─ student_common.py               [新增文件] 最小单元公共逻辑
│  │  ├─ student_service.py              [新增文件] 其他学生/预警服务；请假只委托唯一请假服务
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
│  ├─ run_student_app.py                 [新增文件] 读取根 .env 的学生开发入口
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
│  └─ student-assistant/                  开发笔记，不作为已验收证据
├─ .env.example                          统一无密钥配置模板，含学生专用变量
└─ .env                                  唯一运行配置来源，实际密钥禁止上传
```

沿用 api、schemas、services、repositories、models、clients 和 tasks 分层；统一应用使用 dify/student，增量 SQL 使用 scripts/sql/student，测试分别保留最小单元与整体回归目录。不另建平行框架目录；真实密钥、运行数据、日志和缓存不作为交付资产。


### 六个模块的累计目录关系

保留前述auth、agent、customer、report目录，同时按交付状态增补enterprise、student_leave、student_ticket、student路由及相应services/repositories/models/schemas/clients/tasks/frontend。企业E10与学生S七只描述新增两模块，不能替代此前四模块目录。

student_auth只负责业务确认/会话凭证及服务身份分支，人员认证继续复用core/auth；不得误当第二套学生JWT。历史student_leave/student_ticket Dify客户端和DSL仅留参考，学生当前目标只部署dify/student一个应用。公共main/config/access_control/.env.example保持唯一；run_student_app是开发入口，不据其存在创建独立配置加载或重复注册路由。


## 八、各模块调用、事务与联动流程

### 1. 接口、调用组件及持久化关系

| 入口 / 场景 | 认证与权限处理 | 后端调用关系 | 数据与返回 |
| --- | --- | --- | --- |
| POST /api/v1/auth/login | 公开接收凭据，验证账号密码 | auth 路由 → auth_service → 用户表 → JWT 签发 | user_account；统一返回 access_token、token_type、expires_in |
| GET /api/v1/auth/public-access | 公开访问 | auth 路由 → public_access → YAML | 公开页面/模块元数据，不等于自动挂载业务路由 |
| GET /api/v1/auth/me/access | 校验 JWT 后读取当前用户 | get_current_account → user_account → access_for → YAML | 当前身份权限与可见页面/模块，不返回其他用户权限 |
| POST /api/v1/agent/chat | 匿名公开，不调用 JWT 权限依赖 | agent 路由 → run_chat → 客服场景客户端；real 目标链路继续调用公共 DifyHttpClient | chat_session、chat_message；返回 intent/reply/action；real 链路尚待落实 |
| GET /api/v1/agent/courses | 匿名公开 | agent 路由 → list_courses → 公共数据库会话 | course_project，只返回上架课程；用于 show_courses 动作 |
| GET /api/v1/agent/events | 匿名公开 | agent 路由 → list_events → 公共数据库会话 | lecture_event，可按 status 筛选；用于 show_events 动作 |
| GET /api/v1/agent/events/{event_id} | 匿名公开 | agent 路由 → get_event → 公共数据库会话 | lecture_event，展示选择的活动 |
| POST /api/v1/agent/events/signup | 匿名公开；执行活动、名额及有效报名校验 | agent 路由 → signup → 公共数据库会话和业务事务 | 读 lecture_event，写 event_signup 并增加报名数；返回 signup_id 及约定结果 |
| GET /api/v1/agent/faq | 匿名公开 | agent 路由 → search_faq → 公共数据库会话 | faq；作为标准问答兜底 |
| 其他明确受保护的业务接口 | 每个接口声明 require_permission，内部复用 JWT 认证 | 接口 → 公共鉴权 → 对应业务服务 | 先认证和检查权限，再验证业务数据归属；未认证/无权限按公共错误约定返回 |

### 2. 一次客服咨询到报名的联动

1. 浏览器调用客服对话接口，可携带已有 session_id；不要求先登录公共账号。
2. 后端利用公共数据库会话建立或复用客服会话，保存访客消息。用户消息提前提交、失败仍保留消息为客服源文档目标，现有实现差异继续见第六章。
3. 客服场景客户端根据 mock / real 配置执行。real 的目标方式为调用公共 HTTP 工具，请求本地 Dify Workflow；应用 Key 来自后端配置。公共工具只处理传输，客服适配器校验工作流输出并清理不应展示的推理内容。
4. 后端保存助手消息并用公共响应工具返回；失败时的日志与兜底由客服业务层负责，不能把底层 HTTP 200 等同于模型业务成功。
5. 前端看到 show_courses 或 show_events 后，分别请求课程或活动列表。模型只生成话术和动作，列表及名额以数据库返回为准。
6. 访客选择活动后提交报名。固定业务服务校验活动状态、名额和有效报名记录；目标是在锁住活动行的同一事务中写报名并更新人数，失败一起回滚。现有代码未实现的并发保护不得写成已完成。
7. 后端统一返回报名结果，运行异常记录公共日志。浏览器不直连 Dify，不取得 Dify Key，不直接写数据库。

### 3. 身份、会话与两类 Bearer 凭据

| 标识 / 凭据 | 用途 | 关联限制 |
| --- | --- | --- |
| 公共 access_token（JWT） | 浏览器访问需要登录/权限的后端接口 | 由公共认证验证签名及有效期，经 user_id 查询 user_account，再映射权限 |
| Dify 应用 API Key | 后端请求本地 Dify 应用的 Bearer 凭据 | 仅服务端使用；不作为平台用户 JWT，也不授予用户业务权限 |
| user_account.user_id | 平台账号内部主键 | 不是客服访客会话 ID |
| chat_session.session_id | 关联多轮客服消息 | 是会话关联标识，不是已认证账号或权限凭证 |
| chat_session.user_id | 字符串访客标识，可匿名或留资后关联 | 不等同于 user_account.user_id，也不能直接信任为平台登录身份 |
| event_signup.customer_phone | 报名联系及有效状态判重 | 不自动创建登录账号，不直接映射 customer_profile 主键 |

当前合并范围没有客服访客自动转为统一账号、客户档案或销售线索的已确定流程，不能仅凭手机号或同名字段自动关联。若后续需要，须约定确认、去重和归属后再扩展业务服务。

### 4. 共用组件与事务边界

公共模块维护 config、database、logger、response、auth、authorization 及 Dify HTTP 工具。客服模块维护六个 API、请求/响应 schema、六表 ORM、对话与报名服务、场景客户端及模型/知识库。

数据库 get_db 提供会话及异常回滚/关闭，业务服务负责事务提交；统一响应不提交数据库，日志不代替持久化业务事实。API 权限和数据校验先于业务写入；Dify 不连接业务库、不自动执行 SQL 或报名。工作流异常、数据库异常、参数校验异常和权限异常需要最终进入约定错误出口，当前尚未完全统一的部分保留第六章中的差异说明。

### 5. 配置接通关系

| 配置组 | 主要配置 | 使用者及约束 |
| --- | --- | --- |
| 认证与权限 | AUTH_SECRET_KEY、AUTH_TOKEN_EXPIRE_MINUTES、ACCESS_CONTROL_FILE | 公共 JWT 服务、认证及权限组件 |
| 数据库 | DB_HOST、DB_PORT、DB_USER、DB_PASSWORD、DB_NAME、DB_ECHO | 公共数据库层，客服复用同一会话入口 |
| 日志 | LOG_LEVEL、LOG_DIR | 公共日志工具，客服按处理位置调用 |
| Dify 传输 | DIFY_API_BASE、DIFY_API_TIMEOUT_SECONDS | 公共 HTTP 层与场景适配器使用 |
| 客服应用 | DIFY_CLIENT、DIFY_AGENT_API_KEY | 客服场景客户端使用；源文档描述与当前配置声明的差异见第六章 |

真实值放服务端环境配置，本文只记录配置名。未配置 real 所需项不能宣称真实模型已接通；当前 real 初始化即失败的事实也不能只靠配置切换解决。

### 客户研判主线调用流程（规划）

```text
前端/业务 ──POST /api/v1/customer/sources──▶ 鉴权(customer.source.create)
                                              └▶ customer_service 写入 customer_source(status=pending)
                                                  └▶ 返回 source_id
前端/业务 ──POST /api/v1/customer/sources/{id}/parse──▶ 鉴权(customer.source.parse)
                                                        └▶ parser 按 source_type 分派(text/pdf/excel) → 归一化文本
                                                           └▶ extractor 提取关键字段（可选走 clients/extract_dify.py → 公共 DifyHttpClient）
                                                              └▶ 写入 customer_info，回写 customer_source(status=parsed)
                                                                 └▶ 返回关键字段
前端/业务 ──POST /api/v1/customer/judge──▶ 鉴权(customer.judge.create)
                                          └▶ judge_service 加载 research_rule(该产品 is_active 生效版本)
                                             └▶ 逐条规则比对 customer_info 关键字段
                                                └▶ 按 product 分别产出 matched/matched_fields/unmatched_reasons
                                                   └▶ 写入 research_result（每客户×每产品一条）
                                                      └▶ 返回命中结论（命中/未命中均为正常结果，不走异常分支）
前端/业务 ──GET /api/v1/customer/results/{id}──▶ 鉴权(customer.result.read) └▶ 返回结构化结论
```

批量研判 `customer/judge/batch` 按来源范围批量执行，逐条走单条研判逻辑并汇总成功/失败数。规则维护 `GET/PUT /api/v1/customer/rules` 由 `customer.rule.read` / `customer.rule.manage` 控制，更新走新版本号、旧版本保留，满足可维护性。


### 四模块调用边界与报告生成流程

来源 `cyl合并后.md` 4.1 的示意图把匿名客服也画在公共 JWT 后方，并将其他受保护业务标成管理员；本节按已有匿名规则及逐接口授权口径修正。

```text
浏览器/前端
  ├─ 明确公开接口 → 客服 Agent（无需JWT）→ 客服 Workflow / 业务数据库
  └─ 受保护接口 → 公共 JWT 认证与逐接口鉴权
                    ├─ 报告管理员策略 + 报告权限 → 固定SQL/指标 → 报告Workflow → 报告三表
                    ├─ 客户研判权限 + 员工角色/数据范围 → 来源/提取/规则 → 研判五表
                    └─ 其他业务自己的角色与权限 → 各业务范围校验
```

- **公共模块**：提供 JWT 签发/解析、`get_current_account`、`require_permission`、日志、统一返回、数据库会话、Dify HTTP 传输；只负责「允许/拒绝」与基础设施，不承担业务规则。
- **客服模块**：匿名开放，不接 JWT；对话编排、活动/课程/FAQ 查询、报名落库；Dify 只生成话术与动作，后端以数据库事实为准。
- **报告模块**：平台管理员和部门主管可访问，复用公共JWT、精确report权限与数据范围；配置和手动生成均限平台管理员，主管仅查看；作为数据消费末端只读上游、算指标、调Dify写分析、落库。

#### 报告生成主线（来源设计）

1. 管理员登录取得 JWT，调 `POST /api/v1/report/generate`（`report_code` + 可选时间窗）。
2. 报告路由经公共鉴权校验管理员与 `report.generate`（当前未挂鉴权，为待办）。
3. 幂等判定：同键同口径返回已有记录，同键不同口径返回 409。
4. 建 `report_record`（`status=pending`）立即返回 `report_record_id`，后台任务异步执行：
   - 固定 SQL 从上游源表取数（只读）；
   - 计算指标（固定口径）；
   - 调「智能报告生成」Workflow（`report_code` + `metrics` → `report_text`）；
   - 剥离 `<think>` 推理内容，写正文与指标快照；
   - 置 `success`；任一步失败置 `failed` + `fail_reason`。
5. 管理员轮询 `GET /report/{report_record_id}` 取结果；`GET /report/list` 只看元数据；心理周报默认匿名聚合。

合并限制：报告管理员策略和逐权限依赖尚待接入；详情/列表前缀归一见第一章。后台任务必须使用自己的数据库会话，不能在响应结束后继续依赖已关闭的请求会话；不把“异步”声明写成已经可靠执行的保证。

#### 客服既有流程（报告来源复述）

访客对话（匿名）→ 建/复会话并保存消息 → 客服场景客户端（mock/real）返回意图与动作 → 前端按 `show_courses` / `show_events` 请求真实列表 → 报名校验（状态式去重、名额、事务）→ 写 `event_signup` 并更新 `signed_count`。

既有客服会话提交、失败兜底和报名行锁的实际差异仍以原章节记录为准；报告接入不关闭这些待办。


### 企业 E2：请假统一、历史事实与字段状态转换

来源：`msj_jlj_原文无损合并.md` 的企业 E2：请假统一、历史事实与字段状态转换。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

#### 2.1 主要依据

原方案参考下列业务资料。本次只基于本文件与同目录 `jlj.md` 对齐开发契约，未重新核验代码、SQL、配置、真实数据库或部署环境。历史引用不是已完成测试的证据。

| 依据 | 本方案的使用方式 |
| --- | --- |
| [总需求](../../01需求拆解/总需求.txt)、[企业需求拆解](../../01需求拆解/企业智能助手.txt)、[企业需求文档](../../02需求文档/企业智能助手.md) | 确认功能范围、业务背景及跨模块协作 |
| [开发设计文档](../../03开发设计/开发设计文档.md)、[通用接口设计](../../04接口设计/接口设计文档.txt)、[数据库设计文档](../../05数据库设计/数据库设计文档.md) | 获取原始分层和接口意图；早期简化字段不直接覆盖公共 SQL |
| [公共建表脚本](../../../scripts/sql/all.sql) | 本地字段字典的主要依据；读取脚本不代表已核验真实数据库 |
| [历史企业设计](../../../scripts/sql/bk/企业智能助手/企业智能助手_功能与数据库设计方案.md) | 参考精简后的表、角色与只读 NL2SQL 边界；统一账号以当前代码为准 |
| [学生企业侧对接](../../04接口设计/学生助手_企业侧对接.md)、[企业侧 OpenAPI](../../04接口设计/学生助手_企业侧_OpenAPI.json) | 确认学生侧公布的 13 个协作接口及交接约定 |
| `app/core/dify.py`、`app/core/auth.py`、`app/core/authorization.py`、`app/access_control.yaml`、`app/models/user_account.py`、`app/config.py` | 复用 HTTP、登录、权限及配置入口，区分现状与待实现能力 |

本文所有“拟新增”“建议”“目标态”均为后续实施方案，不表示相关文件、接口已经实现。

#### 2.2 学生请假统一开发边界

双方均处于开发阶段，取消“学生接口已可用”与“企业需补齐同一接口”的并行假设。下表为唯一目标分工，不依据历史提交或某个文件是否缺少认定已完成状态。

| 项目 | 统一约定 | 负责方 |
| --- | --- | --- |
| 事实表/主键 | `student_admin_service.id` 对外为 `apply_id`，只处理 `apply_type=leave` | 公共表结构双方共同维护 |
| 学生接口 | 提交、列表、详情、撤回四种方法，只访问本人 | 学生模块，`app/api/student_leave.py` |
| 老师接口 | 请假查询/审批、心理预警/处置、学生通知共 10 种方法 | 学生模块，`app/api/student.py`；企业不重复注册 |
| 唯一请假服务 | `StudentLeaveService` 实现提交、查询、撤回及老师审批 | 学生维护，其他学生/企业服务只委托 |
| 老师工作台 | 授权待办、详情、审批确认和结果展示 | 企业开发页面及调用编排 |
| 工单协作 | 学生提交/补充/确认/重开/评价，企业分派/处理/给方案 | 按动作拆分，字段和事务见附录 B |
| 当前交付状态 | 均按开发和待测试目标管理 | 双方按联合验收清单举证 |

**统一公共账号 JWT 与 `student_admin_service`，不建设企业请假替代表或双写。**开发阶段直接使用附录 B，不默认建设历史兼容层；只有核实存在旧调用方或真实历史数据时才另行制定适配/迁移。本轮不操作数据库。

表清单、API 字段与学生文档统一。历史 `student_leave_request` 只在 A.16 作为停用结构说明，不进入当前建表或路由清单。

#### 2.3 其他需要区分的现状

- 早期文档的 `intention_customer` 对应目前的 `customer_profile` 与 `customer_followup`；`complaint_feedback` / `after_sales_ticket` 对应共享的 `service_ticket` 与 `service_ticket_record`。不重复建设同义事实表。
- 当前统一登录身份有 `admin`、`employee`、`customer`、`student`；`consultant`、`manager`、`teacher` 等属于员工业务角色，不能直接当作新的 `identity_type`。
- 公共权限依赖负责身份级动作授权，业务授权层检查角色、归属、绑定及负责人，不能只改菜单可见性。
- 企业 NL2SQL 采用 schema 和受控只读契约；学生固定查询独立维护，不把企业 SQL 生成响应当作学生查询结果。
- 代码是否可复用需后续核验；缺失功能由所属模块按固定规则实现。学生维护唯一请假服务，企业不得按文件名另起同一审批逻辑。

#### 2.4 请假统一落地方案

**一张事实表、一套业务服务、一套登录身份。**学生提交、老师列表/详情、老师审批和学生结果查询都定位 `student_admin_service` 同一条记录，并强制 `apply_type=leave`，不能把考务申请当作请假处理。

| 事项 | 已选设计 |
| --- | --- |
| 登录身份 | `JWT.sub → user_account.user_id → student_id / employee_id`，复用公共认证，不再单独签发学生模块的 `actor_type/actor_id` 登录令牌 |
| 唯一事实表 | `student_admin_service`；数据库主键为 `id`，API 对外统一称 `apply_id` |
| 固定业务服务 | 学生维护唯一 `StudentLeaveService` 与 `student_leave_repository.py`，统一提交/查询/撤回/审批；企业只调用 |
| 当前审批人 | 可空 BIGINT 物理外键 `reviewer_id → employee.employee_id`；未分派为 NULL，审批时等于真实当前员工 |
| 实际操作人 | 审批事务在 `operation_log.employee_id` 保存实际审批员工；快照保留审批前后的指定审批人、状态、意见与版本，不将旧的两个员工字段机械合并 |
| 审批结果 | 目标字段为 `approval_status、reviewed_at、approval_comment、row_version`，双方映射相同列；现有结构待核对，不新增同义列 |
| 状态 | `pending → approved/rejected`；学生撤回为 `pending → cancelled`；批准、驳回、撤回后不能再次审批 |
| 通知与审计 | 审批结果、操作记录、学生结果通知和幂等回执同事务提交；企业端不重复更新或重复入队 |

旧契约字段与目标模型的转换仅发生在接口边界：

| 旧交接字段/状态 | 目标字段/状态 | 转换要求 |
| --- | --- | --- |
| `leave_request_id` / `apply_id` | `apply_id`，对应 `student_admin_service.id` | 仅同一对象的命名映射；旧表历史 ID 不保证等于新表 ID，迁移时须独立建立映射 |
| `reason` | `apply_content` | 请假理由原文，不用 AI 摘要替换 |
| `start_at` / `end_at` | `leave_start_at` / `leave_end_at` | 统一 UTC，接口时间包含偏移 |
| `submitted` / `withdrawn` | `pending` / `cancelled` | 旧兼容入口入站转换；旧响应如需保留契约再反向转换；标准接口只使用目标状态 |
| `approved` / `rejected` | 同名状态 | 保持含义 |
| `approver_employee_id` | `reviewer_id` | 指定审批老师，不代表任何历史实际决策者 |
| `decision_employee_id` | 成功审批审计中的 `operation_log.employee_id` | 从对应成功审批事件读取，不能仅凭当前 `reviewer_id` 推断历史操作者；历史缺失时明确缺失 |
| `decision_at` / `decision_comment` | `reviewed_at` / `approval_comment` | 审批形成结果后写入 |
| `leave_type` | `edu_related_data.leave_type` | 与当前提交服务一致，仅暴露受控扩展键，不透传内部 AI 分析结果 |
| `request_no` / `attachment_key` | 本地无直接等价列 | 标准契约不承诺原样返回；兼容调用方确有需要时另定可追溯来源或字段扩展，不编造值或默默丢弃附件 |

开发交付直接按附录 B 更新 Schema、接口导出和前端，不混合两套状态。只有核实存在旧调用方时才另定明确版本的适配入口；本期不默认实施兼容。适配也只能委托同一固定服务，不访问另一张请假表或新增登录校验器。

如果目标环境已有 `student_leave_request` 历史数据，后续先备份、核对记录数与关联，再单独制定一次性迁移：建立旧 ID 到目标 ID 的映射，转换状态，保留指定/实际审批人及时间、意见，重映射相关通知与审计引用，完成抽样核对后切换写入口。两张表均有数据时不能简单按姓名合并或直接复用旧主键；迁移完成后停止旧表写入，旧数据按留存要求处理。没有旧数据则无需迁移，本轮不操作数据库。


### 企业 E3：查询、动作提取与固定写入分层

来源：`msj_jlj_原文无损合并.md` 的企业 E3：查询、动作提取与固定写入分层。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

```mermaid
flowchart TD
    UI[企业文字或语音转写输入] --> AUTH[统一登录与员工业务授权]
    AUTH --> PARSE[普通大模型识别意图并提取结构化字段]
    PARSE --> Q[查询请求]
    Q --> SQL[enterprise_nl2sql.py 通用只读 NL2SQL]
    SQL --> GUARD[SQL 语法、字段、数据范围校验]
    GUARD --> READ[受限 SELECT 执行并返回结果]
    PARSE --> W[新增、修改、归档、审批等动作]
    W --> CHECK[Schema 校验、对象定位、业务校验与预览]
    CHECK --> CONFIRM[员工确认]
    CONFIRM --> DISPATCH[动作白名单映射]
    DISPATCH --> SERVICE[已有或预定义的硬编码业务服务]
    SERVICE --> TX[事务：业务变更、审计、必要通知]
    PARSE --> KB[新人 QA 或授权 RAG]
```

关键约定：

1. **只读查询**可以走固定列表/详情接口，也可以由 `enterprise_nl2sql.py` 将自然语言与 schema 转成受限 `SELECT`。
2. **增删改**由普通模型返回 `action + target + fields + missing_fields`，后端映射到已经编写好的函数。提取“SQL 所需关键字”指业务字段和值，不要求模型输出 SQL 文本、表名、列名或 SQL 片段。
3. 客户状态、成绩、审批、投诉等业务规则由硬编码服务决定；普通模型不能通过 `action` 任意调用模块函数。
4. Dify 和模型不直连业务库，不拿业务库账号，不负责鉴权、提交事务、计算真实操作者或发送业务成功回执。
5. 同进程优先直接调用公共服务，不为复用自己应用里的函数再发 HTTP；跨服务才通过专用客户端调用公开契约。


### 企业 E7：受控动作、预览确认、业务状态与外部系统

来源：`msj_jlj_原文无损合并.md` 的企业 E7：受控动作、预览确认、业务状态与外部系统。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

#### 7.1 普通模型的输入与输出

后端提供当前允许的动作、字段定义及必要上下文，模型只做结构化提取。原始输入、历史对话、知识文档均不能改变动作白名单。

输入例：“把 C20260018 改为已流失，原因是预算不足。”模型返回的业务结构示例：

```json
{
  "intent": "write",
  "action": "customer.change_status",
  "target": {"customer_no": "C20260018"},
  "fields": {"status": "lost", "lost_reason": "预算不足"},
  "missing_fields": [],
  "needs_clarification": false
}
```

其中不含 SQL。客户编号先在当前员工有权访问的数据内解析为内部 `customer_id`。重名、编号不明确、缺少流失原因等情况返回待补充字段，不猜测目标，不执行。

#### 7.2 动作到固定功能的映射

下列是目标服务职责名，不声称当前分支已有所有同名函数。实施时绑定到实际已有函数；缺失功能先按固定业务规则补齐。

| 受控动作 | 模型允许提取的主要字段 | 后端固定功能 |
| --- | --- | --- |
| `customer.create` | 姓名、电话、学历、国家、来源、首次跟进 | 客户创建服务：编号、密文、匹配 token、归属、去重候选、审计 |
| `customer.update` | 客户定位、允许修改的普通资料 | 客户资料更新服务；不修改身份角色或随意转派 |
| `customer.change_status` | 客户定位、目标状态、流失/回退原因 | 客户状态机服务，更新状态时间，保留历史 |
| `customer.assign` | 客户定位、目标顾问、原因 | 主管转派服务，校验部门和目标顾问 |
| `customer.add_followup` | 客户定位、内容、渠道、发生时间、下次时间 | 追加跟进服务，同时维护最近跟进时间 |
| `customer.archive` | 客户定位、原因 | 客户归档服务，设置 `is_archived` |
| `daily_report.submit/update/void` | 日期、正式内容、修订或作废原因 | 本人日报固定服务，唯一键与版本校验 |
| `score.create/update/void` | 学生、课程、学期、考核、次数、得分、满分、原因 | 成绩固定服务，权限范围、数值及唯一键校验 |
| `leave.decide` | 申请定位、同意/驳回、意见 | 调用统一 `StudentLeaveService` 固定审批能力，按 `student_admin_service` 更新；审批事务、权限与幂等见第 6.4 节 |
| `ticket.assign/follow/resolve` | 工单定位、处理人、内容、可见性、方案 | 企业工单固定服务，更新状态、处理记录与必要通知 |

配置角色、账号和授权关系通过专门维护入口处理，首期不放入普通对话动作白名单。

#### 7.3 预览、确认、执行

1. `POST /command` 鉴权后调用提取 Workflow，严格校验动作和字段类型，只查询本人有权访问的候选对象。
2. 生成业务预览：目标编号、当前值、将变更的字段、必要原因、当前版本及缺失字段。查询/预览阶段不写业务表。
3. 字段完整时返回短期签名确认凭证，建议 5 分钟有效，绑定当前账号、员工、动作、内部对象 ID、已规范化字段、版本、过期时间及随机请求标识。不把敏感明文放进可解码凭证；凭证保存规范化参数摘要。
4. `POST /command/confirm` 由同一员工提交相同规范化参数及凭证，后端验证摘要、有效期与归属，再检查最新角色、对象状态、绑定与版本；参数变化必须重新预览。
5. 按动作白名单调用固定服务。**确认阶段不再次要求模型解释命令，也不调用 `enterprise_nl2sql.py`。**
6. 本地事务内占用唯一幂等键，执行业务、记录前后快照、入队必要通知、保存回执；失败回滚。同键同参数回放已完成结果时仍检查当前权限。

表单直填接口提交的是已经明确的业务字段，可以直接调用同一固定服务，不为表单强制增加一次模型调用。自然语言与表单不能各自维护一份状态规则。

#### 7.4 业务状态与跨系统边界

- 客户默认 `new → contacting → qualified → signed`，签约前可转 `lost`，原因必填；从 `lost` 恢复为 `contacting` 或更正已签约状态只允许主管并说明原因。归档与客户状态分开。
- 日报 `submitted → void`；正式内容由员工确认后提交，AI 摘要不能替代正式内容。作废后重新启用需明确恢复动作，不用新增记录绕过唯一键。
- 成绩 `valid → void`；更正和作废均保留旧得分、旧满分、新值及原因。教务配置为 `external_readonly` 时拒绝所有写入。
- 工单 `open/reopened → assigned → processing → awaiting_student`；学生确认后才 `closed`，未解决由学生重开。企业不能直接设置学生满意度或代替学生确认关闭。
- 学生请假统一为 `pending → approved/rejected/cancelled`，其中 `cancelled` 仅由学生本人撤回；企业老师只能审批 `pending`。服务只操作 `student_admin_service`，旧状态只在明确版本的兼容边界转换，不进入主业务模型。
- 外部 CRM/教务写回不能与本地事务假装原子提交：先生成稳定外部请求 ID，保存待处理状态，由适配器核实后完成本地快照与回执。外部超时结果不明时记为 `unknown_external`，不自动重发非幂等业务，也不返回已成功。
- Dify 调用在数据库写事务之前完成，不持有业务行锁等待模型响应。


### 企业 E8：独立通用只读NL2SQL契约及执行校验

来源：`msj_jlj_原文无损合并.md` 的企业 E8：独立通用只读NL2SQL契约及执行校验。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

#### 8.1 职责与独立契约

拟放置在 `app/services/enterprise_nl2sql.py`，作为“自然语言 + schema + 方言 + 查询限制 → SQL 候选”的通用查询编排服务。通过注入查询生成适配器支持替换模型，不复用 `app/clients/nl2sql_dify.py` 的旧 `generate_sql(question)` 契约，也不调用旧查询执行入口。

| 输入 | 来源/意义 |
| --- | --- |
| `question` | 查询语义，可保留自然语言问题，但不是只有一个 question 的旧接口 |
| `schema_context` | 后端提供允许的表/视图、字段、关系、注释、枚举；不传完整库表结构 |
| `dialect` | 本期固定 `mysql`，由后端提供 |
| `query_constraints` | 允许 SELECT、最大行数、允许聚合/排序及可用查询域 |
| `bound_filters` | 后端解析的查询条件与占位参数，日期等采用规范化值 |
| `schema_version` | 字段和查询契约版本，用于追溯 |

输出候选为 `sql_template + params + referenced_tables + referenced_columns + schema_version`。后两项只作为校验参考，实际引用必须从 SQL AST 再解析；不相信模型自报的引用清单。

这属于通用 NL2SQL 能力：生成器理解 schema 与查询约束，不内置“某一句客户话术对应某条 SQL”的硬编码模板。**只读是执行权限边界，不影响通用自然语言查询能力。**

#### 8.2 查询域与数据授权

| 查询域 | 允许内容 | 强制范围 |
| --- | --- | --- |
| 客户与跟进 | 客户编号、姓名、学历、国家、状态、授权跟进内容、日期 | 顾问本人；主管本部门；跟进通过客户主键继承范围 |
| 日报 | 日期、正式内容、摘要、提交时间 | 本人或主管本部门的已提交日报 |
| 学生成绩 | 最小学生标识、课程、学期、考核、得分、满分 | 班主任所负责学生；教务所授权学生及课程 |
| 投诉 | 工单编号、分类、状态、期限和有权查看的处理内容 | 当前负责老师，或主管本部门；内部与学生可见内容按调用端区分 |
| 组织与知识 | 部门职能、员工工作信息、已发布制度元数据 | 工作字段白名单；知识按全员/本部门、生效期筛选 |

账号表、密码哈希、手机号密文、登录身份键、操作审计原始快照、心理表、系统配置不开放给通用 NL2SQL。

实施建议：由仓储层构造请求级受限 CTE/派生关系，向生成器只暴露查询域的逻辑关系；业务字段取显式列，全部行提前应用真实员工/部门/学生课程范围。模型 SQL 的表引用必须全部落在这些受限关系上，禁止回查物理基表。每个 JOIN、子查询、聚合都基于这些受限关系，不能仅给最外层拼一条 WHERE。

#### 8.3 执行前校验

使用项目依赖中已有的 SQL 解析器能力，例如 `sqlglot`，按 MySQL 方言解析 AST；具体实现与该版本 API 在编码时核验。

1. 只接受一个查询语句；逐节点校验只读查询及其子查询，不仅检查字符串是否以 `SELECT` 开头。
2. 拒绝 INSERT、UPDATE、DELETE、DDL、CALL、SELECT INTO、锁定读取、系统 schema、跨库对象、任意文件/网络访问、危险函数、用户变量与递归查询等超出白名单的语法。
3. 所有逻辑表、列、函数、JOIN 关系均须在该请求的允许集合中；禁止 `SELECT *`，避免 schema 扩展后意外暴露字段。
4. 模型没有参数值决定权：占位符必须与已规范化条件一一对应，用户字符串使用绑定参数，不拼接进 SQL。
5. 真实授权范围由后端构造，不接受模型输出的 `employee_id/department_id` 作为权限依据；查询条件只能缩小当前授权集合。
6. 默认返回不超过 100 行；分页与总数查询均受限，限制执行时间、查询复杂度及 join 数；禁止用“返回行数少”代替扫描成本控制。
7. 执行使用只有受控查询权限的只读连接/数据库账号作为第二道保护；客户端不接收 SQL，不提供自由 SQL 调试执行接口。
8. SQL 校验失败、依赖不可用、查询歧义均返回明确失败/待澄清；不降级为旧的不受控查询服务。

具体表单列表、审批待办等规则固定的查询优先使用已有仓储查询，不为每次打开列表消耗模型。


### 企业 E11：待办聚合与通知分工

来源：`msj_jlj_原文无损合并.md` 的企业 E11：待办聚合与通知分工。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

待办从业务事实查询，不新增通用待办主表：客户取尚未完成且到期的跟进安排；请假取 `student_admin_service` 中 `apply_type=leave、approval_status=pending、reviewer_id=当前老师` 且班主任关系有效的记录；投诉取分派给本人且未解决/已超时的工单。

定时任务按受控系统身份扫描，真实处理时员工仍须重新鉴权。提醒采用 `enterprise.` 事件前缀，通知键包含业务对象、事件、处理轮次、接收人和渠道；与学生模块的 `student.` 消息分开领取，避免重复消费。

请假审批结果属于 `student.` 事件，统一由第 6.4 节的共享审批服务入队、学生通知任务消费。企业待办可以直接聚合请假事实，不能因为企业页面展示了结果就再次生产一条相同学生通知。

业务变更和通知入队同事务；站内发布任务按租约领取，失败退避重试，达到上限进入dead_letter。成功将通知发布为对应个人页面可查询时才记sent，不要求浏览器在线或已打开；read_at另记。已读不自动关闭工单或批准请假。本期没有短信、邮件、企业微信或群机器人投递。


### 与研判、报告、客服的新增联动限制

1. 企业客户服务可承接经确认的客服/研判线索，但继续使用候选匹配、受控归属和幂等，不能仅凭同号自动合并；拟新增ENTERPRISE_PHONE_*密钥必须与主档及研判同套规则核对，不能对已有密文/token直接切换新密钥。
2. 企业日报字段字典与学生心理/工单状态方案为报告上游增加字段参考，并不证明接口或表已落地。customer_judgement/deal_amount缺口依旧；报告只读聚合且不能读取心理原文作推荐或通用经营分析。
3. 老师工作台通知必须按事件归属调用学生或企业通知入口：student.ticket.*即使由企业服务生产也由StudentTasks投递，事件生产者与投递者不是一回事。以第十六章B.7具体表为目标，不按页面所属模块重复发通知。
4. 固定写服务与模型抽取职责分开，Dify不持有数据库写权限、不替服务生成操作者；查询生成候选SQL只有通过受控关系及AST校验才可执行。


### 当前本地教务/CRM、语音与个人页通知方案

教务与CRM采用本地页面，语音采用faster-whisper；学生结果及员工待办分别进入本人的个人页面，不接群机器人。本项目当前以本地页面、FastAPI固定服务和MySQL提供所需数据闭环，不要求先购买或提供外部教务/CRM系统。

#### 本地页面与数据职责

| 页面/功能 | 当前目标 | 授权与数据边界 |
| --- | --- | --- |
| 教务管理页 | 维护学生课程/成绩及考试、DDL等学业节点，节点改期联动提醒 | 现有academic/score_editor处理授权学生和课程成绩；班主任只读负责学生。学业节点维护须补逐动作授权，不向全体employee开放 |
| CRM管理页 | 维护客户、顾问归属、跟进、状态及学生申请进度 | 顾问本人客户、主管本部门；转派、归并及学生关联遵循既有确认/审计规则；申请进度由可信负责人维护，不由模型推进 |
| 学生个人页 | 查询本人课程/成绩/学业节点/申请进度、查看本人结果通知及未读数 | 公共JWT绑定student_id，本人范围；页面不直连MySQL，不接收他人敏感记录 |
| 员工个人页 | 查询本人待办、分派/审批提醒及站内通知，支持已读 | 公共JWT绑定employee_id；待办按实际可处理业务事实计算，通知按收件人计算；查看和办理分别鉴权 |

调用链为本地前端→公共登录/JWT→逐动作与对象范围校验→固定业务服务/仓储→MySQL。复用现有frontend与后端结构，不另建平行账号、重复客户/学生主档或请假事实表。原有employee/customer/student/admin与已确认权限矩阵继续适用；本地CRM页面不等于给平台customer账号授员工能力。

当前只实现本项目所需教务/CRM子集，不推定包含招生收费、支付、合同、人事薪酬等完整产品功能。源设计的学业/进度表原按外部镜像描述，转为本地权威维护时需复核必填字段、主键/唯一性、source_system/外部ID语义及审计；不得伪造第三方外部ID、把演示数据当真实同步或未经评审新增重复表。既有student-v1/group查询、服务同步Token和外部unknown_external均保留未来可选分支，当前页面不依赖它们。

#### faster-whisper本地语音

本地音频上传→格式/大小/时长和当前账号校验→faster-whisper适配器→转写文本展示核对→既有Dify业务字段提取或固定表单服务→预览/确认后写入。faster-whisper负责转文字，不能决定业务权限、直接审批或直接写库；确认阶段不重复推理。

使用faster-whisper的本地Python调用，不需要ENTERPRISE_VOICE_DIFY_API_KEY、云ASR供应商凭据或专用语音Dify应用。源enterprise_voice_transcribe.yml仅保留历史资产参考，不部署为当前必需应用；其他Dify场景继续走公共DifyHttpClient，不为ASR复制HTTP栈。

模板中的ASR_BACKEND=faster_whisper、ASR_MODEL_SIZE=small、ASR_DEVICE=cpu、ASR_COMPUTE_TYPE=int8、ASR_MODEL_PATH为新增规划变量，尚未加入Settings/加载器。small+CPU/int8仅作开发初始配置，后续按本机资源和中文音频实测调整，不承诺当前速度/准确率。正式离线使用需预先准备本地模型目录；本轮没有安装依赖、下载模型或启动推理。依据：[faster-whisper官方项目](https://github.com/SYSTRAN/faster-whisper)。

#### 个人页站内通知与待办

仅采用站内渠道目标in_app，不需要短信、邮件、企业微信/飞书机器人或外部webhook。学生通知发到本人个人页；员工待办/通知发到本人工作台。消息列表、未读数、详情和已读接口均从当前登录账号取得收件人，不能由前端传任意收件人ID查询。

沿用business_notification、StudentTasks/EnterpriseTasks、按event_code前缀消费及通知去重；业务变更与消息入队同事务。发布任务将合法收件人消息成功发布为个人页可查时记sent；页面可轮询或刷新，不要求用户在线才算发布成功。read_at仅表示已读，待办是否完成仍看业务状态；失败重试不能重复审批/处理，通知正文仍按最小必要字段输出。

目标只保留一份共用通知表及原业务任务分工，不新建两套消息系统。员工消息不等于全部门消息，部门主管身份也不能读其他员工的个人消息；跨角色兼任仍按当前身份及数据范围验证。

#### 本轮文件与后续实施边界

主文档、.env.example与配置示例/integrations.example.json已同步为本地方案：移除当前语音Dify Key、外部教务/CRM/通知URL及Token占位；保留STUDENT_SYNC_TOKEN为仅未来外部同步可选字段；增加明确标为规划的本地ASR配置。Dify仍按用户确认1.11.4、应用未发布；QA/RAG单应用；日报每日17:00、四类周报周五17:00，Asia/Shanghai，均不改变。

本轮完成方案和示例调整；本地页面、完整教务/申请维护接口、数据结构适配、ASR安装/模型、站内任务和报告调度尚未实现或验收。未修改真实.env、应用代码/SQL/数据库、Dify或部署服务，不将配置示例当已可运行的系统。此前要求提供外部供应商的问项不再作为当前前置条件；本地节点维护权限/完整API、统计口径及原数据保护/并发待办仍须在实施中补齐。

### 本轮业务问题的直接补齐口径

以下仅依据本文已有字段、状态和范围做简单文档对齐，尚未修改代码或验证运行；落实工作移入第十八章研发待办，不重复列为待用户决定的问题。

1. 规则生效：判定时产品必须启用，规则is_active=true，且effective_from为空或不晚于判定时刻、effective_to为空或晚于判定时刻；采用左闭右开[from,to)。起止均有值时必须from<to，空边界为无界。无有效规则或出现多条有效版本时停止该产品正常研判并提示配置未就绪/冲突，不把异常当未命中。
2. 字段映射：以本文逐字段表为准，不因概述补“意向国家”等物理列。raw_fields仅保存必要、受控白名单且脱敏的业务扩展；不保存完整简历/原文件、明文电话/邮箱或心理原文，不用于绕过原文保护。原件保留与期限仍待第十八章第022项。
3. 缺失与停用：关键字段缺失时返回缺失清单，进入补资料/人工复核，不强行记不匹配；无有效规则、产品停用或规则格式错误时不生成正常命中/未命中结果。具体产品准入与评分阈值仍待第十八章第028项；不新增未经审核的数据库状态枚举。
4. 工单指标：首次回应取first_response_at-created_at，自动回执/内部备注不计；每轮给方案与最终关闭分别统计。每轮起点为首次created_at或该轮重开事件，终点为同cycle_no给方案记录；最终关闭只有当前closed且存在closed_at才计入。重开清空当前solution/resolved_at/closed_at不抹去历史轮次；无法从记录还原时标不可计算，不填0或猜测。
5. 心理报告：原始取数→聚合metrics→Dify输入→正文/列表→日志全链路使用汇总白名单。只提供评估次数、风险等级分布、预警总数/处置状态及按获准周期汇总的趋势；评估次数不冒充去重学生人数。学生ID、姓名、联系方式、聊天原文、个人情绪值/预警原因及个人可追踪标识不进入报告链路。部门/时间细分和小样本阈值仍待第十八章第045项，未确定前不开放可定位个人的细分或下钻。
6. 通用统计：先按权限和时间窗过滤，再按业务主键/事件去重；事件时间列依本文各对象定义，业务时区Asia/Shanghai、存储沿用UTC目标。查询窗口统一[start,end)，结束时点不重复计入下期。分母0、缺上游或缺历史时返回不可计算/依赖未就绪及说明，不把缺失当0；跨周期比较使用同一指标版本。实际指标选择及分母仍待第十八章第038项，默认自然/滚动窗口仍待第十八章第038项。

联系方式与心理资料的原始文件/文本如确需保留，须在受控存储保护并按授权访问，运行日志不输出完整原文；具体期限与匿名阈值未被本轮自行决定。以上没有改变既定报告角色、北京时间17:00的日报/周报生成计划或个人页通知方式。

## 九、公共与各业务表字段、关联和设计差异

客服六张表的完整 47 个字段、默认值、索引和外键已保留在第一章“客服模块”的字段小节。本章补充 user_account，以及其关联所需的 employee、customer_profile、student_profile、org_department 四张共享表，避免只有表名而缺少字段定义。

本章字段和约束从本次读取的 scripts/sql/all.sql 提取，未执行数据库迁移。共享表由相应模块维护，不因文档合并转为客服模块负责；operation_log 在源文档中用于区分业务审计，并非本次客服功能新增审计表。

### user_account（9 个字段）

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| user_id | BIGINT | 否 | 自增 | 统一用户主键 ID。 |
| username | VARCHAR(64) COLLATE utf8mb4_bin | 否 | 未声明 | 登录用户名，唯一。 |
| password_hash | VARCHAR(255) COLLATE utf8mb4_bin | 否 | 未声明 | 密码哈希，不得存储明文密码。 |
| identity_type | VARCHAR(20) COLLATE utf8mb4_bin | 否 | 未声明 | 用户身份：employee 员工、customer 客户、student 学生。 |
| employee_id | BIGINT | 是 | NULL | 对应员工表 employee.employee_id；非员工身份时为空。 |
| customer_id | BIGINT | 是 | NULL | 对应客户表 customer_profile.customer_id；非客户身份时为空。 |
| student_id | BIGINT | 是 | NULL | 对应学生表 student_profile.student_id；非学生身份时为空。 |
| created_at | DATETIME(3) | 否 | CURRENT_TIMESTAMP(3) | 用户记录创建时间（UTC）。 |
| updated_at | DATETIME(3) | 否 | CURRENT_TIMESTAMP(3)；更新时自动刷新 | 用户记录最近更新时间（UTC）。 |

**关联、索引与约束：**

- PRIMARY KEY (user_id)
- UNIQUE KEY uq_user_username (username)
- UNIQUE KEY uq_user_employee (employee_id)
- UNIQUE KEY uq_user_customer (customer_id)
- UNIQUE KEY uq_user_student (student_id)
- CONSTRAINT fk_user_employee FOREIGN KEY (employee_id) REFERENCES employee (employee_id) ON DELETE RESTRICT ON UPDATE RESTRICT
- CONSTRAINT fk_user_customer FOREIGN KEY (customer_id) REFERENCES customer_profile (customer_id) ON DELETE RESTRICT ON UPDATE RESTRICT
- CONSTRAINT fk_user_student FOREIGN KEY (student_id) REFERENCES student_profile (student_id) ON DELETE RESTRICT ON UPDATE RESTRICT
- CONSTRAINT ck_user_identity_link CHECK ((identity_type = 'admin' AND employee_id IS NULL AND customer_id IS NULL AND student_id IS NULL) OR (identity_type = 'employee' AND employee_id IS NOT NULL AND customer_id IS NULL AND student_id IS NULL) OR (identity_type = 'customer' AND employee_id IS NULL AND customer_id IS NOT NULL AND student_id IS NULL) OR (identity_type = 'student' AND employee_id IS NULL AND customer_id IS NULL AND student_id IS NOT NULL))

### org_department（10 个字段）

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| department_id | BIGINT | 否 | 自增 | 部门记录主键 ID，供员工、客户、学生及部门层级引用。 主键（PK）。 |
| department_code | VARCHAR(32) COLLATE utf8mb4_bin | 否 | 未声明 | 部门唯一业务编码。 |
| department_name | VARCHAR(100) | 否 | 未声明 | 部门名称。 |
| parent_department_id | BIGINT | 是 | NULL | 上级部门 ID，关联本表；顶级部门为空。 外键（FK）关联 org_department.department_id。 |
| function_description | TEXT | 是 | NULL | 部门职能与职责说明。 |
| employee_id | BIGINT | 是 | NULL | 部门主管员工 ID，关联 employee。 外键（FK）关联 employee.employee_id。 |
| status | VARCHAR(32) COLLATE utf8mb4_bin | 否 | 'active' | 部门状态：active 启用、disabled 停用。 |
| created_at | DATETIME(3) | 否 | CURRENT_TIMESTAMP(3) | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| updated_at | DATETIME(3) | 否 | CURRENT_TIMESTAMP(3)；更新时自动刷新 | 记录最近更新时间，UTC |
| row_version | INT | 否 | 1 | 并发版本号；每次业务修改由硬编码后端递增 |

**关联、索引与约束：**

- PRIMARY KEY (department_id)
- UNIQUE KEY uq_department_code (department_code)
- KEY idx_department_parent (parent_department_id)
- KEY idx_department_manager (employee_id)
- CONSTRAINT fk_org_department_parent_department_id FOREIGN KEY (parent_department_id) REFERENCES org_department (department_id) ON DELETE RESTRICT ON UPDATE RESTRICT
- CONSTRAINT ck_department_status CHECK (status IN ('active','disabled'))
- CONSTRAINT ck_org_department_row_version CHECK (row_version >= 1)

### employee（17 个字段）

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| employee_id | BIGINT | 否 | 自增 | 员工主键 ID，是所有员工业务关联的内部标识，不使用工号代替。 主键（PK）。 |
| employee_no | VARCHAR(32) | 否 | 未声明 | 员工唯一工号。 |
| full_name | VARCHAR(100) | 否 | 未声明 | 员工姓名，允许重名。 |
| department_id | BIGINT | 否 | 未声明 | 当前主部门 ID，关联 org_department。 外键（FK）关联 org_department.department_id。 |
| position_title | VARCHAR(100) | 是 | NULL | 员工岗位或职务名称。 |
| login_provider | VARCHAR(32) COLLATE utf8mb4_bin | 否 | 未声明 | 登录来源，如企业统一登录。 |
| login_subject | VARCHAR(128) COLLATE utf8mb4_bin | 否 | 未声明 | 登录来源提供的不可变账号标识。 |
| role_codes | JSON | 否 | 未声明 | 受控角色代码数组；权限由后端固定配置解释。 |
| work_phone_ciphertext | VARBINARY(512) | 是 | NULL | 加密保存的工作联系电话。 |
| work_email | VARCHAR(254) | 是 | NULL | 工作邮箱。 |
| status | VARCHAR(32) COLLATE utf8mb4_bin | 否 | 'active' | 员工状态：active 启用、disabled 停用、left 离职。 |
| joined_date | DATE | 否 | 未声明 | 入职日期。 |
| left_date | DATE | 是 | NULL | 离职日期，未离职时为空。 |
| external_employee_id | VARCHAR(128) COLLATE utf8mb4_bin | 是 | NULL | 权威通讯录中的员工 ID。 |
| created_at | DATETIME(3) | 否 | CURRENT_TIMESTAMP(3) | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| updated_at | DATETIME(3) | 否 | CURRENT_TIMESTAMP(3)；更新时自动刷新 | 记录最近更新时间，UTC |
| row_version | INT | 否 | 1 | 并发版本号；每次业务修改由硬编码后端递增 |

**关联、索引与约束：**

- PRIMARY KEY (employee_id)
- UNIQUE KEY uq_employee_no (employee_no)
- UNIQUE KEY uq_employee_login (login_provider, login_subject)
- UNIQUE KEY uq_employee_external (external_employee_id)
- KEY idx_employee_department_status (department_id, status)
- CONSTRAINT fk_employee_department_id FOREIGN KEY (department_id) REFERENCES org_department (department_id) ON DELETE RESTRICT ON UPDATE RESTRICT
- CONSTRAINT ck_employee_status CHECK (status IN ('active','disabled','left'))
- CONSTRAINT ck_employee_roles CHECK (JSON_TYPE(role_codes) = 'ARRAY' AND JSON_LENGTH(role_codes) > 0)
- CONSTRAINT ck_employee_dates CHECK (left_date IS NULL OR left_date >= joined_date)
- CONSTRAINT ck_employee_row_version CHECK (row_version >= 1)

### customer_profile（22 个字段）

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| customer_id | BIGINT | 否 | 自增 | 客户主键 ID，是跟进记录及关联学生使用的内部标识。 主键（PK）。 |
| customer_no | VARCHAR(32) | 否 | 未声明 | 客户唯一业务编号。 |
| full_name | VARCHAR(100) | 否 | 未声明 | 客户姓名，不作为唯一身份依据。 |
| phone_ciphertext | VARBINARY(512) | 是 | NULL | 加密保存的客户手机号。 |
| phone_lookup_token | CHAR(64) COLLATE utf8mb4_bin | 是 | NULL | 标准化手机号的带密钥匹配标记，用于提示重复候选。 |
| education_level | VARCHAR(32) | 是 | NULL | 客户学历层次。 |
| target_country_code | VARCHAR(8) COLLATE utf8mb4_bin | 是 | NULL | 意向留学国家编码。 |
| source_channel | VARCHAR(32) | 否 | 未声明 | 客户来源，如人工、客服留资或 CRM。 |
| source_reference | VARCHAR(128) | 是 | NULL | 来源留资或研判任务引用。 |
| employee_id | BIGINT | 是 | NULL | 当前顾问员工 ID，未分派时为空。 外键（FK）关联 employee.employee_id。 |
| department_id | BIGINT | 否 | 未声明 | 当前客户管理部门 ID。 外键（FK）关联 org_department.department_id。 |
| status | VARCHAR(32) COLLATE utf8mb4_bin | 否 | 'new' | 客户状态：new、contacting、qualified、signed、lost。 |
| status_changed_at | DATETIME(3) | 否 | CURRENT_TIMESTAMP(3) | 当前客户状态开始生效的时间。 |
| lost_reason | TEXT | 是 | NULL | 流失原因，状态变为 lost 时必须填写。 |
| last_followup_at | DATETIME(3) | 是 | NULL | 最近一次有效跟进时间，由业务服务维护。 |
| authority_source | VARCHAR(20) | 否 | 'local' | 数据权威来源：local 本平台、crm 外部 CRM。 |
| external_customer_id | VARCHAR(128) COLLATE utf8mb4_bin | 是 | NULL | CRM 中的客户 ID。 |
| external_updated_at | DATETIME(3) | 是 | NULL | 最近确认的外部客户更新时间。 |
| is_archived | BOOLEAN | 否 | 0 | 是否已归档，默认 false；保留销售状态和历史，归档后不进入默认客户列表。 |
| created_at | DATETIME(3) | 否 | CURRENT_TIMESTAMP(3) | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| updated_at | DATETIME(3) | 否 | CURRENT_TIMESTAMP(3)；更新时自动刷新 | 记录最近更新时间，UTC |
| row_version | INT | 否 | 1 | 并发版本号；每次业务修改由硬编码后端递增 |

**关联、索引与约束：**

- PRIMARY KEY (customer_id)
- UNIQUE KEY uq_customer_no (customer_no)
- UNIQUE KEY uq_customer_external (external_customer_id)
- KEY idx_customer_employee_status (employee_id, status)
- KEY idx_customer_department_status (department_id, status)
- KEY idx_customer_phone_token (phone_lookup_token)
- CONSTRAINT fk_customer_profile_employee_id FOREIGN KEY (employee_id) REFERENCES employee (employee_id) ON DELETE RESTRICT ON UPDATE RESTRICT
- CONSTRAINT fk_customer_profile_department_id FOREIGN KEY (department_id) REFERENCES org_department (department_id) ON DELETE RESTRICT ON UPDATE RESTRICT
- CONSTRAINT ck_customer_status CHECK (status IN ('new','contacting','qualified','signed','lost'))
- CONSTRAINT ck_customer_authority CHECK (authority_source IN ('local','crm'))
- CONSTRAINT ck_customer_lost_reason CHECK (status <> 'lost' OR (lost_reason IS NOT NULL AND CHAR_LENGTH(TRIM(lost_reason)) > 0))
- CONSTRAINT ck_customer_archived CHECK (is_archived IN (0,1))
- CONSTRAINT ck_customer_profile_row_version CHECK (row_version >= 1)

### student_profile（15 个字段）

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| student_id | BIGINT | 否 | 自增 | 学生主键 ID，是成绩、请假、投诉及学生员工关系使用的内部标识。 主键（PK）。 |
| student_no | VARCHAR(32) | 否 | 未声明 | 学生唯一业务编号。 |
| full_name | VARCHAR(100) | 否 | 未声明 | 学生姓名，允许重名。 |
| phone_ciphertext | VARBINARY(512) | 是 | NULL | 加密保存的学生手机号。 |
| customer_id | BIGINT | 是 | NULL | 关联客户 ID，不自动授予客户账号访问学生数据的权限。 外键（FK）关联 customer_profile.customer_id。 |
| department_id | BIGINT | 否 | 未声明 | 学生教务或服务归属部门 ID。 外键（FK）关联 org_department.department_id。 |
| login_provider | VARCHAR(32) COLLATE utf8mb4_bin | 是 | NULL | 学生登录来源，尚未开通账号时为空。 |
| login_subject | VARCHAR(128) COLLATE utf8mb4_bin | 是 | NULL | 学生登录身份键，与登录来源同时填写。 |
| status | VARCHAR(32) COLLATE utf8mb4_bin | 否 | 未声明 | 学生服务或在读状态。 |
| external_student_id | VARCHAR(128) COLLATE utf8mb4_bin | 是 | NULL | 教务系统中的学生 ID。 |
| is_archived | BOOLEAN | 否 | 0 | 是否已归档，默认 false；归档不删除已有成绩、请假和投诉关联。 |
| created_at | DATETIME(3) | 否 | CURRENT_TIMESTAMP(3) | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| updated_at | DATETIME(3) | 否 | CURRENT_TIMESTAMP(3)；更新时自动刷新 | 记录最近更新时间，UTC |
| row_version | INT | 否 | 1 | 并发版本号；每次业务修改由硬编码后端递增 |
| crm_student_id | VARCHAR(128) COLLATE utf8mb4_bin | 是 | NULL | CRM 系统中的学生 ID；脚本末尾 ALTER 增加 |

**关联、索引与约束：**

- PRIMARY KEY (student_id)
- UNIQUE KEY uq_student_no (student_no)
- UNIQUE KEY uq_student_login (login_provider, login_subject)
- UNIQUE KEY uq_student_external (external_student_id)
- KEY idx_student_department_status (department_id, status)
- KEY idx_student_customer (customer_id)
- CONSTRAINT fk_student_profile_customer_id FOREIGN KEY (customer_id) REFERENCES customer_profile (customer_id) ON DELETE RESTRICT ON UPDATE RESTRICT
- CONSTRAINT fk_student_profile_department_id FOREIGN KEY (department_id) REFERENCES org_department (department_id) ON DELETE RESTRICT ON UPDATE RESTRICT
- CONSTRAINT ck_student_login_pair CHECK ((login_provider IS NULL AND login_subject IS NULL) OR (login_provider IS NOT NULL AND login_subject IS NOT NULL))
- CONSTRAINT ck_student_archived CHECK (is_archived IN (0,1))
- CONSTRAINT ck_student_profile_row_version CHECK (row_version >= 1)
- UNIQUE KEY uq_student_crm (crm_student_id)；由脚本末尾 ALTER 增加

### 公共关联说明

账号username及业务关联ID的唯一键、外键和身份CHECK见上方字段表。customer_profile、employee、student_profile的部门与负责人由org_department、employee承接；客服报名event_id指向lecture_event.id，消息session_id指向chat_session.session_id，访客user_id不自动关联统一账号。知识向量由Dify承载，不虚构统一向量物理字段。字段与实现的剩余差异统一见第十八章。

### 客户研判五表设计与合并后的相关表范围

来源：`sgtallm.md` 第三章。本章前述五张公共表及第一章六张客服表完整保留。新增五表为设计草案；“16 张”是本次三模块相关表的规划总数，不是当前实际建表数量或全项目表数。

合并后共三类、16 张相关表：

| 类别 | 表名 | 归属 | 说明 |
| --- | --- | --- | --- |
| 公共账号及依赖 | `user_account`、`org_department`、`employee`、`customer_profile`、`student_profile` | 公共 | 主文档第九章已列全字段、索引、外键、CHECK，本次不改动 |
| 客服业务 | `course_project`、`lecture_event`、`event_signup`、`faq`、`chat_session`、`chat_message` | 客服 | 主文档第一章已列完整 47 字段，本次不改动 |
| 客户研判 | `customer_source`、`customer_info`、`research_rule`、`product`、`research_result` | 客户研判 | 新增，字段见本章新增客户研判五表 |

客户研判五表为新增，与既有 11 表不存在同名表冲突。存量 `course_project`、`customer_profile` 等表保持原结构，不因本次合并增删字段。

#### 新增五表字段、索引与关联（字段设计口径）

以下字段依据 sgt.md 及《客户研判需求文档》整理，为设计口径；具体类型、默认值、索引、外键与 CHECK 待甲方《用户画像研判规则》和团队 DDL 约定确定后再冻结。时间字段沿用既有表 `DATETIME(3) UTC` 与 `row_version` 并发约定。

#### 甲方产品表 `product`

存甲方对外产品线（本次需求为两个产品），是画像研判的判定对象与规则归属。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| id | BIGINT | 否 | 自增 | 主键 |
| product_code | VARCHAR(32) | 否 | — | 产品唯一编码，唯一键 |
| product_name | VARCHAR(100) | 否 | — | 产品名称 |
| description | TEXT | 是 | NULL | 产品说明 |
| target_profile_summary | TEXT | 是 | NULL | 目标客户画像摘要（规则判定口径的说明） |
| status | VARCHAR(32) | 否 | 'active' | 状态：active 启用 / disabled 停用 |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间（UTC） |
| updated_at | DATETIME(3) | 否 | 当前时间，更新时自动刷新 | 更新时间（UTC） |
| row_version | INT | 否 | 1 | 并发版本号 |

- 唯一键 `uq_product_code(product_code)`；索引 `idx_product_status(status)`。

#### 客户信息来源表 `customer_source`

一次接入（一份文本、一份 PDF、一个 Excel 文件）对应一条来源记录；一个 Excel 文件可解析出多条客户。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| id | BIGINT | 否 | 自增 | 主键 |
| source_type | VARCHAR(16) | 否 | — | 来源类型：text / pdf / excel |
| raw_content | LONGTEXT | 是 | NULL | 归一化后的原始文本；文本类直接存，文件类存解析结果 |
| file_name | VARCHAR(255) | 是 | NULL | 原始文件名 |
| file_path | VARCHAR(255) | 是 | NULL | 文件存放路径（文件类来源） |
| status | VARCHAR(32) | 否 | 'pending' | 状态：pending 待解析 / parsed 已解析 / failed 解析失败 |
| created_by | BIGINT | 是 | NULL | 提交人（关联 `user_account.user_id`） |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间（UTC） |
| updated_at | DATETIME(3) | 否 | 当前时间，更新时自动刷新 | 更新时间（UTC） |

- 索引 `idx_source_type_status(source_type, status)`；`created_by` 可选外键 `fk_customer_source_creator → user_account(user_id)`，是否强制由公共负责人确认。

#### 客户关键字段表 `customer_info`

解析后的结构化客户字段，是画像研判的输入；一条来源可产生多条客户记录。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| id | BIGINT | 否 | 自增 | 主键 |
| source_id | BIGINT | 否 | — | 关联来源（外键 → `customer_source.id`） |
| customer_id | BIGINT | 是 | NULL | 归并后关联平台客户主档（外键 → `customer_profile.customer_id`），未归并时为空 |
| full_name | VARCHAR(100) | 是 | NULL | 姓名 |
| gender | VARCHAR(16) | 是 | NULL | 性别 |
| age | INT | 是 | NULL | 年龄 |
| education_level | VARCHAR(32) | 是 | NULL | 学历层次 |
| major | VARCHAR(100) | 是 | NULL | 专业 |
| work_years | INT | 是 | NULL | 工作年限 |
| industry | VARCHAR(64) | 是 | NULL | 行业 |
| position_title | VARCHAR(100) | 是 | NULL | 职位 |
| city | VARCHAR(64) | 是 | NULL | 所在城市 |
| income_level | VARCHAR(32) | 是 | NULL | 收入/薪资层级 |
| target_product_code | VARCHAR(32) | 是 | NULL | 意向产品编码（可空，关联 product.product_code） |
| phone_ciphertext | VARBINARY(512) | 是 | NULL | 加密保存的联系电话（沿用 customer_profile 加密约定） |
| phone_lookup_token | CHAR(64) | 是 | NULL | 标准化手机号的匹配标记，用于受控归并/判重 |
| contact_email | VARCHAR(254) | 是 | NULL | 联系邮箱 |
| raw_fields | JSON | 是 | NULL | 必要的白名单业务扩展字段，按保护规则脱敏；不存完整原文或明文联系方式 |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间（UTC） |
| updated_at | DATETIME(3) | 否 | 当前时间，更新时自动刷新 | 更新时间（UTC） |
| row_version | INT | 否 | 1 | 并发版本号 |

- 外键：`fk_customer_info_source(source_id) → customer_source(id)`；`fk_customer_info_customer(customer_id) → customer_profile(customer_id)`（可选，归并后回填）。
- 索引：`idx_info_source(source_id)`、`idx_info_phone_token(phone_lookup_token)`、`idx_info_customer(customer_id)`。

**字段命名与加密约定**：联系方式不存明文；`phone_ciphertext` 与 `phone_lookup_token` 与 `customer_profile` 同套加密/匹配方案，保证后续归并可复用同一 token，避免两套去重混用（见本章“字段与表关联冲突”）。

#### 研判规则表 `research_rule`

存《用户画像研判规则》各版本，支持更新与可维护性要求；按产品归属规则。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| id | BIGINT | 否 | 自增 | 主键 |
| product_id | BIGINT | 否 | — | 关联产品（外键 → `product.id`） |
| rule_version | VARCHAR(32) | 否 | — | 规则版本号 |
| rule_content | JSON | 否 | — | 结构化规则内容（命中/未命中条件） |
| rule_description | TEXT | 是 | NULL | 规则说明 |
| is_active | BOOLEAN | 否 | 0 | 是否生效；同产品仅一条生效版本由业务保证 |
| effective_from | DATETIME | 是 | NULL | 生效开始时间 |
| effective_to | DATETIME | 是 | NULL | 生效结束时间（可空） |
| created_by | BIGINT | 是 | NULL | 维护人（关联 `user_account.user_id`） |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间（UTC） |
| updated_at | DATETIME(3) | 否 | 当前时间，更新时自动刷新 | 更新时间（UTC） |
| row_version | INT | 否 | 1 | 并发版本号 |

- 外键：`fk_research_rule_product(product_id) → product(id)`。
- 索引：`idx_rule_product_active(product_id, is_active)`、`idx_rule_version(product_id, rule_version)`。
- 生效版本唯一性（同一 product 仅一条 active）建议由业务服务保证，是否加数据库唯一索引由数据库负责人确认。

#### 研判结果表 `research_result`

每条客户 × 每个产品一条结论，命中/未命中均落库，供复核与后续业务使用。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| id | BIGINT | 否 | 自增 | 主键 |
| source_id | BIGINT | 否 | — | 关联来源（外键 → `customer_source.id`） |
| customer_info_id | BIGINT | 否 | — | 关联客户关键字段（外键 → `customer_info.id`） |
| product_id | BIGINT | 否 | — | 关联产品（外键 → `product.id`） |
| rule_version | VARCHAR(32) | 否 | — | 判定所用规则版本 |
| matched | BOOLEAN | 否 | — | 是否命中该产品目标画像 |
| matched_fields | JSON | 是 | NULL | 命中依据字段 |
| unmatched_reasons | JSON | 是 | NULL | 未命中原因 |
| score | DECIMAL(5,2) | 是 | NULL | 规则评分（若规则含评分） |
| created_by | BIGINT | 是 | NULL | 研判人（关联 `user_account.user_id`） |
| created_at | DATETIME(3) | 否 | 当前时间 | 研判时间（UTC） |

- 外键：`fk_result_source(source_id) → customer_source(id)`、`fk_result_info(customer_info_id) → customer_info(id)`、`fk_result_product(product_id) → product(id)`。
- 索引：`idx_result_info(customer_info_id)`、`idx_result_product(product_id)`、`idx_result_matched(product_id, matched)`、`idx_result_source(source_id)`。

字段定位：结果信息索引采用`idx_result_info(customer_info_id)`。逐表时间／版本与数据保护的剩余事项统一见末章。


### 客户研判与跨模块ER关系

customer_info是一份来源的结构化快照，customer_profile是统一客户主档；两者的受控归并见第八章流程。研判角色使用employee.role_codes，不新增identity_type；产品和课程默认独立。未闭合的字段与引用事项统一见第十八章。

#### 三模块表间关系（方案）

```text
user_account ──1:N── customer_source (created_by，可选)
user_account ──1:N── research_rule (created_by，可选)
user_account ──1:N── research_result (created_by，可选)

customer_source 1:N customer_info (source_id)
customer_info   N:1 customer_profile (customer_id，可空，归并后回填)
customer_info   1:N research_result (customer_info_id，每产品一条)
product         1:N research_rule (product_id)
product         1:N research_result (product_id)

—— 既有关系（主文档已列，保持不变）——
user_account 1:0..1 employee / customer_profile / student_profile
org_department 1:N employee / customer_profile / student_profile
employee 1:N customer_profile (顾问)
chat_session 1:N chat_message (session_id)
lecture_event 1:N event_signup (event_id)
```

关键闭合：客户研判五表通过 `source_id` 串起「来源 → 字段 → 结果」，通过可空 `customer_info.customer_id` 与平台客户主档衔接，通过 `product` 承接两个产品的规则与结论。客服报名 `event_signup` 与客户研判无直接外键，联动通过业务层把报名留资作为 `customer_source` 文本来源接入（见第八章“客服与客户研判联动”）。

关联要求：research_result.source_id 必须与所引用 customer_info.source_id 一致，不能把不同来源的结果和客户信息拼接。

### 智能报告三张专属表（字段摘要，非完整DDL）

来源：`cyl合并后.md` 3.4。来源声称“完整字段、约束与索引见主文档第九章”，但合并前主文档不存在报告三表定义，来源本身也只给出字段名称。以下完整保留其 37 个字段名称及明确的唯一键/外键线索；类型、可空性、默认值、精度和具体索引并未提供，本文不补造。

- `report_config`（9 字段）：`report_config_id`、`report_code`（唯一）、`report_name`、`report_period`、`cron_expr`、`enabled`、`created_at`、`updated_at`、`row_version`。
- `report_record`（18 字段）：`report_record_id`、`report_config_id`（FK）、`report_code`、`idempotency_key`（唯一）、`start_time`、`end_time`、`timezone`、`data_snapshot_at`、`report_version`、`source_record_count`、`report_content`、`metric_json`、`status`、`fail_reason`、`generated_at`、`created_at`、`updated_at`、`row_version`。
- `report_metric`（10 字段）：`report_metric_id`、`report_record_id`（FK）、`metric_code`、`metric_name`、`metric_value`、`metric_text`、`metric_unit`、`calc_rule`、`period_type`、`created_at`。

来源的上述完整定义引用尚未闭合，待提供经审核 DDL 后补全；当前仅可作为字段名称清单。

| 表 | 已明确的关联 / 唯一性 | 尚缺的结构口径 |
| --- | --- | --- |
| report_config | report_config_id 主键语义；report_code 唯一 | 九字段类型、默认/可空、周期/cron/enabled 枚举及约束、五条种子具体值 |
| report_record | report_record_id 主键语义；report_config_id 关联 report_config；idempotency_key 唯一 | 十八字段类型、状态约束、外键删除策略、时间精度、快照/版本/幂等策略 |
| report_metric | report_metric_id 主键语义；report_record_id 关联 report_record | 十字段类型、metric_code 维度与唯一性、数值精度/单位及 calc_rule/period_type 口径 |

报告三表的 ORM、all.sql、`scripts/sql/bk/智能报告/report_module_ddl.sql` 是否一致未核验；不能仅凭字段数、文件名或循环引用认定一致或已建表。


### 报告表清单、只读上游与关联关系

#### 报告来源原统计（公共+客服+报告，未含研判）

| 类别 | 表 | 归属 |
| --- | --- | --- |
| 公共账号 | `user_account` | 公共模块 |
| 共享依赖 | `org_department`、`employee`、`customer_profile`、`student_profile` | 各业务模块 |
| 客服（6） | `course_project`、`lecture_event`、`event_signup`、`faq`、`chat_session`、`chat_message` | 客服模块 |
| 报告专属（3） | `report_config`、`report_record`、`report_metric` | 报告模块 |
| 报告只读上游（6） | `customer_followup`、`customer_judgement`（未落地）、`employee_daily_report`、`mental_health_profile`、`mental_warning`、`service_ticket` | 企业 / 客户研判 / 学生 / 投诉模块 |

本合并展开 **14 张相关表** 的完整字段（公共账号 5 + 客服 6 + 报告 3）；报告只读的 6 张上游表由对应业务模块维护，报告模块不持有其 ORM、不回写，本合并不展开其字段。

统计校正：上一轮 16 张规划相关表加报告专属三表，本轮四模块为 19 张直接相关表。报告另列六张只读上游表，按目前名称集合与19表不重名，另行统计；其中 customer_judgement 明确未落地且与研判方案不一致。以上为文档范围，不是全项目物理表清点，不等于已有25张表或已展开所有表的完整类型定义。报告来源“14张完整字段”只是来源声称，报告三表当前只有字段摘要。

#### 报告来源 ER 及上游消费关系

```text
user_account.employee_id ──► employee.employee_id
user_account.customer_id ──► customer_profile.customer_id
user_account.student_id ───► student_profile.student_id
employee.department_id ────► org_department.department_id
customer_profile.department_id ─► org_department.department_id
student_profile.department_id ──► org_department.department_id

event_signup.event_id ─────► lecture_event.id
chat_message.session_id ───► chat_session.session_id

report_record.report_config_id ─► report_config.report_config_id
report_metric.report_record_id ─► report_record.report_record_id

报告模块（只读，不建 FK）：
  customer_overview ◄── customer_profile、customer_followup、customer_judgement
  daily_report / weekly_report ◄── employee_daily_report
  mental_weekly ◄── mental_health_profile、mental_warning
  complaint_weekly ◄── service_ticket
```

报告共享字段、专属表及上游消费的剩余差异统一见第十八章；上方字段摘要和关系图用于定位设计对象。

### 企业 E4：15表依赖、公共结构、索引与关系

来源：`msj_jlj_原文无损合并.md` 的企业 E4：15表依赖、公共结构、索引与关系。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

#### 4.1 清单与归属

本地方案需要 **15 张关联表：1 张统一账号表、12 张企业/共享支持表、2 张学生共享主表**。这是依赖清单，不是要新建 15 张表；已有同名表复用。四类核心业务是客户、日报、投诉、成绩，其余表用于身份、关系、过程、知识及通知。

| 表 | 用途 | 企业模块责任 |
| --- | --- | --- |
| `user_account` | 统一登录账号、身份与业务主键映射 | 复用公共认证；不复制密码到员工表 |
| `org_department` | 部门层级、职能、主管 | 查询与授权基础，维护入口限企业配置人员 |
| `employee` | 员工资料、部门、业务角色、有效状态 | 复用/映射，角色维护必须受控 |
| `customer_profile` | 意向客户当前档案、负责人、状态 | 主要负责 |
| `customer_followup` | 多次跟进及下次跟进安排 | 主要负责 |
| `employee_daily_report` | 员工每天正式提交的日报 | 主要负责 |
| `student_profile` | 学生唯一主档 | 学生共享主表；不另建企业学生身份 |
| `student_staff_binding` | 学生与班主任、成绩人员、服务顾问关系 | 授权基础；复用公共数据 |
| `student_score` | 学生数值成绩与当前有效状态 | 主要负责，受教务权威来源约束 |
| `student_admin_service` | 学生行政申请与唯一请假事实源 | 学生提交、老师审批、学生结果共用；请假固定筛选 `apply_type=leave` |
| `service_ticket` | 学生投诉/建议主工单 | 企业处理，学生提交与确认，共用事实源 |
| `service_ticket_record` | 多轮沟通、分派、解决、确认过程 | 共用；区分内部与学生可见 |
| `knowledge_entry` | 新人 QA、制度原文和索引元数据 | 主要负责，不在本地重复存 Dify 向量 |
| `business_notification` | 站内通知、去重、投递与重试 | 共用；企业任务只消费归属自己的事件 |
| `operation_log` | 幂等回执、操作者、变更前后快照 | 共用；只能由后端写入 |

学生心理评估、心理预警、学业节点及申请进度表属于学生模块。企业需要协作时调用它的接口，不把心理原文加入通用 NL2SQL schema。正式报告复用报告模块，不在本清单新增报告表。

#### 4.2 公共结构约定

- 以 `scripts/sql/all.sql` 的字段为本地基线，MySQL、InnoDB、`utf8mb4`；主键/外键使用对应内部 `BIGINT`，姓名、手机号、工号不作为关联键。
- 时间瞬间存 UTC，接口时间带明确偏移；日报日期按 `Asia/Shanghai` 的机构工作日计算。
- 多数可变表含 `created_at`、`updated_at`、`row_version`；更新必须带 `expected_version`，条件匹配后版本加一。账号表没有 `row_version`，处理记录为追加记录，仅有 `created_at`，不强行假定所有表字段相同。
- 外键默认限制删除，业务删除采用客户归档、成绩/日报作废、部门/关系/知识停用；投诉过程与审计不通过通用接口物理删除。
- 手机号保存密文，查询使用服务端生成的带密钥匹配 token。模型不得自行生成密文或匹配 token；数据库密码、密码哈希、登录身份键和密钥不进入 NL2SQL schema 或模型提示词。
- `user_account` 一条记录对应一种身份。`admin` 身份三类业务外键均为空；其他身份只填写对应的员工、客户或学生外键。以当前 ORM 和 SQL 的约束为准，部分旧说明没有描述 `admin`，不据此删除当前管理员身份。

#### 4.3 关系、索引与约束

```mermaid
erDiagram
    org_department ||--o{ employee : department_id
    employee ||--o| user_account : employee_id
    employee ||--o{ customer_profile : employee_id
    customer_profile ||--o{ customer_followup : customer_id
    employee ||--o{ employee_daily_report : employee_id
    customer_profile o|--o{ student_profile : customer_id
    student_profile ||--o{ student_staff_binding : student_id
    employee ||--o{ student_staff_binding : employee_id
    student_profile ||--o{ student_score : student_id
    student_profile ||--o{ student_admin_service : student_id
    student_profile ||--o{ service_ticket : student_id
    service_ticket ||--o{ service_ticket_record : ticket_id
```

图中仅展示主要业务关系；通知、审计和知识的具体关联见字段说明。

| 表/关系 | 关键约束与索引 |
| --- | --- |
| 账号 | 用户名唯一；员工/客户/学生外键分别唯一；身份与关联一致 |
| 部门/员工 | 部门编码、工号唯一；登录来源+身份键唯一；层级禁止成环；目标主管字段 `org_department.employee_id → employee.employee_id` 为可空物理 FK，循环依赖顺序见附录 B |
| 客户 | 客户编号、外部 CRM ID 唯一；负责人+状态、部门+状态、手机号匹配 token 索引；`lost` 必须有流失原因；手机号 token 不设唯一，避免错误合并共用号码的客户 |
| 跟进 | 客户+发生时间+主键索引；待跟进状态+下次时间索引；追加内容不覆盖历史；`pending` 必须有下次时间 |
| 日报 | `(employee_id, report_date)` 唯一；提交部门+日期+状态索引；正式内容非空 |
| 学生 | 学号、外部教务 ID、独立 CRM 学生 ID 唯一；关联客户不自动授予客户账号读取学生档案的权限 |
| 学生员工关系 | 员工+关系类型+状态、学生+关系类型+状态索引；生效期有效；同一学生的有效主班主任冲突由事务校验处理，不能只依赖布尔字段 |
| 成绩 | `(student_id, course_code, term_code, assessment_code, attempt_no)` 唯一；`0 ≤ score_value ≤ max_score`，满分大于 0，考核次数至少 1 |
| 本地行政申请 | 学生+请求键唯一；审批人+状态+创建时间索引；请假结束晚于开始；批准/驳回需审批人及审批时间 |
| 工单 | 工单编号唯一；负责人+状态+解决期限索引；进入 `awaiting_student` 或 `closed` 必须有方案；评价 1～5 |
| 处理记录 | `record_key` 唯一；工单+时间+主键索引；员工、学生、服务操作者三选一；追加保存 |
| 知识 | 条目编码唯一；状态+访问部门+失效时间索引；发布需审核、起效时间及索引就绪；FAQ 有问题和答案，文档有正文或受控来源 |
| 通知 | `dedupe_key` 唯一；状态+下次重试时间索引；员工接收人与学生接收人二选一 |
| 审计 | `operation_key` 唯一；对象+时间、操作者+时间索引；员工、学生、服务操作者三选一 |

`business_notification` / `operation_log` 的 `entity_type + entity_id` 是受控逻辑引用，不是同时指向多张表的物理外键。对象类型由后端动作白名单决定。

完整字段字典见附录 A，逐表列出字段、类型、可空性、默认值、主键与说明。


### 企业来源附录A：完整15表字段字典与旧请假结构参考

来源：`msj_jlj_原文无损合并.md` 的企业来源附录A：完整15表字段字典与旧请假结构参考。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

以下为 15 张企业/公共表的目标字段字典，保留原设计基线但不代表实际数据库结构。`PK` 表示主键，`自增` 表示自动生成；可空性与条件必填由业务约束共同限制。双方所有共享主键、目标物理外键及组合唯一键以附录 B 为准，已有数据库是否符合需后续测试。

字典中的“外键”均为目标约束而非已建证明。目标必须包含可空物理 FK `org_department.employee_id → employee.employee_id` 与 `student_admin_service.reviewer_id → employee.employee_id`；迁移时核对实际结构并补齐，不能继续把它们同时描述成仅逻辑关联。部门/员工循环引用先建表后补约束，不关闭外键检查插入虚拟 ID。

#### A.1 `user_account`：统一登录账号

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `user_id` | BIGINT | 否 | `—` | PK；自增；统一用户主键 ID。 |
| `username` | VARCHAR(64) | 否 | `—` | 登录用户名，唯一。 |
| `password_hash` | VARCHAR(255) | 否 | `—` | 密码哈希，不得存储明文密码。 |
| `identity_type` | VARCHAR(20) | 否 | `—` | 目标身份：admin、employee、customer、student；身份与业务外键一致性按附录 B 的目标 CHECK 约束实现。 |
| `employee_id` | BIGINT | 是 | `NULL` | 对应员工表 employee.employee_id；非员工身份时为空。 |
| `customer_id` | BIGINT | 是 | `NULL` | 对应客户表 customer_profile.customer_id；非客户身份时为空。 |
| `student_id` | BIGINT | 是 | `NULL` | 对应学生表 student_profile.student_id；非学生身份时为空。 |
| `created_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 用户记录创建时间（UTC）。 |
| `updated_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 更新时自动刷新；用户记录最近更新时间（UTC）。 |

#### A.2 `org_department`：部门

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `department_id` | BIGINT | 否 | `—` | PK；自增；部门记录主键 ID，供员工、客户、学生及部门层级引用。 主键（PK）。 |
| `department_code` | VARCHAR(32) | 否 | `—` | 部门唯一业务编码。 |
| `department_name` | VARCHAR(100) | 否 | `—` | 部门名称。 |
| `parent_department_id` | BIGINT | 是 | `NULL` | 上级部门 ID，关联本表；顶级部门为空。 外键（FK）关联 org_department.department_id。 |
| `function_description` | TEXT | 是 | `NULL` | 部门职能与职责说明。 |
| `employee_id` | BIGINT | 是 | `NULL` | 部门主管员工 ID，关联 employee。 外键（FK）关联 employee.employee_id。 |
| `status` | VARCHAR(32) | 否 | `'active'` | 部门状态：active 启用、disabled 停用。 |
| `created_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 更新时自动刷新；记录最近更新时间，UTC |
| `row_version` | INT | 否 | `1` | 并发版本号；每次业务修改由后端递增 |

#### A.3 `employee`：员工

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `employee_id` | BIGINT | 否 | `—` | PK；自增；员工主键 ID，是所有员工业务关联的内部标识，不使用工号代替。 主键（PK）。 |
| `employee_no` | VARCHAR(32) | 否 | `—` | 员工唯一工号。 |
| `full_name` | VARCHAR(100) | 否 | `—` | 员工姓名，允许重名。 |
| `department_id` | BIGINT | 否 | `—` | 当前主部门 ID，关联 org_department。 外键（FK）关联 org_department.department_id。 |
| `position_title` | VARCHAR(100) | 是 | `NULL` | 员工岗位或职务名称。 |
| `login_provider` | VARCHAR(32) | 否 | `—` | 登录来源，如企业统一登录。 |
| `login_subject` | VARCHAR(128) | 否 | `—` | 登录来源提供的不可变账号标识。 |
| `role_codes` | JSON | 否 | `—` | 受控角色代码数组；权限由后端固定配置解释。 |
| `work_phone_ciphertext` | VARBINARY(512) | 是 | `NULL` | 加密保存的工作联系电话。 |
| `work_email` | VARCHAR(254) | 是 | `NULL` | 工作邮箱。 |
| `status` | VARCHAR(32) | 否 | `'active'` | 员工状态：active 启用、disabled 停用、left 离职。 |
| `joined_date` | DATE | 否 | `—` | 入职日期。 |
| `left_date` | DATE | 是 | `NULL` | 离职日期，未离职时为空。 |
| `external_employee_id` | VARCHAR(128) | 是 | `NULL` | 权威通讯录中的员工 ID。 |
| `created_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 更新时自动刷新；记录最近更新时间，UTC |
| `row_version` | INT | 否 | `1` | 并发版本号；每次业务修改由后端递增 |

#### A.4 `customer_profile`：客户档案

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `customer_id` | BIGINT | 否 | `—` | PK；自增；客户主键 ID，是跟进记录及关联学生使用的内部标识。 主键（PK）。 |
| `customer_no` | VARCHAR(32) | 否 | `—` | 客户唯一业务编号。 |
| `full_name` | VARCHAR(100) | 否 | `—` | 客户姓名，不作为唯一身份依据。 |
| `phone_ciphertext` | VARBINARY(512) | 是 | `NULL` | 加密保存的客户手机号。 |
| `phone_lookup_token` | CHAR(64) | 是 | `NULL` | 标准化手机号的带密钥匹配标记，用于提示重复候选。 |
| `education_level` | VARCHAR(32) | 是 | `NULL` | 客户学历层次。 |
| `target_country_code` | VARCHAR(8) | 是 | `NULL` | 意向留学国家编码。 |
| `source_channel` | VARCHAR(32) | 否 | `—` | 客户来源，如人工、客服留资或 CRM。 |
| `source_reference` | VARCHAR(128) | 是 | `NULL` | 来源留资或研判任务引用。 |
| `employee_id` | BIGINT | 是 | `NULL` | 当前顾问员工 ID，未分派时为空。 外键（FK）关联 employee.employee_id。 |
| `department_id` | BIGINT | 否 | `—` | 当前客户管理部门 ID。 外键（FK）关联 org_department.department_id。 |
| `status` | VARCHAR(32) | 否 | `'new'` | 客户状态：new、contacting、qualified、signed、lost。 |
| `status_changed_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 当前客户状态开始生效的时间。 |
| `lost_reason` | TEXT | 是 | `NULL` | 流失原因，状态变为 lost 时必须填写。 |
| `last_followup_at` | DATETIME(3) | 是 | `NULL` | 最近一次有效跟进时间，由业务服务维护。 |
| `authority_source` | VARCHAR(20) | 否 | `'local'` | 数据权威来源：local 本平台、crm 外部 CRM。 |
| `external_customer_id` | VARCHAR(128) | 是 | `NULL` | CRM 中的客户 ID。 |
| `external_updated_at` | DATETIME(3) | 是 | `NULL` | 最近确认的外部客户更新时间。 |
| `is_archived` | BOOLEAN | 否 | `0` | 是否已归档，默认 false；保留销售状态和历史，归档后不进入默认客户列表。 |
| `created_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 更新时自动刷新；记录最近更新时间，UTC |
| `row_version` | INT | 否 | `1` | 并发版本号；每次业务修改由后端递增 |

#### A.5 `customer_followup`：客户跟进

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `followup_id` | BIGINT | 否 | `—` | PK；自增；客户跟进记录主键 ID。 主键（PK）。 |
| `customer_id` | BIGINT | 否 | `—` | 本记录所属客户 ID。 外键（FK）关联 customer_profile.customer_id。 |
| `employee_id` | BIGINT | 否 | `—` | 实际执行跟进的员工 ID。 外键（FK）关联 employee.employee_id。 |
| `followup_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 客户沟通实际发生时间。 |
| `channel` | VARCHAR(32) | 否 | `—` | 跟进方式，如电话、面谈或线上沟通。 |
| `content` | TEXT | 否 | `—` | 完整跟进内容。 |
| `summary` | TEXT | 是 | `NULL` | 经员工确认的跟进摘要。 |
| `next_followup_at` | DATETIME(3) | 是 | `NULL` | 计划下一次跟进的时间。 |
| `followup_status` | VARCHAR(20) | 否 | `'none'` | 下一次跟进安排状态：none 未安排、pending 待跟进、done 已完成、cancelled 已取消。 |
| `created_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 更新时自动刷新；记录最近更新时间，UTC |
| `row_version` | INT | 否 | `1` | 并发版本号；每次业务修改由后端递增 |

#### A.6 `employee_daily_report`：员工日报

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `daily_report_id` | BIGINT | 否 | `—` | PK；自增；员工日报记录主键 ID。 主键（PK）。 |
| `employee_id` | BIGINT | 否 | `—` | 日报所属员工 ID。 外键（FK）关联 employee.employee_id。 |
| `report_date` | DATE | 否 | `—` | 日报对应机构工作日日期。 |
| `department_id_at_submit` | BIGINT | 否 | `—` | 最近提交时的部门快照。 外键（FK）关联 org_department.department_id。 |
| `submitted_content` | TEXT | 否 | `—` | 最近一次员工确认提交的正式内容，必须填写。 |
| `ai_summary` | TEXT | 是 | `NULL` | 与最近提交内容对应的辅助摘要。 |
| `status` | VARCHAR(32) | 否 | `'submitted'` | 日报状态：submitted 已提交、void 已作废。 |
| `submitted_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 最近正式提交时间。 |
| `created_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 更新时自动刷新；记录最近更新时间，UTC |
| `row_version` | INT | 否 | `1` | 并发版本号；每次业务修改由后端递增 |

#### A.7 `student_profile`：学生主档

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `student_id` | BIGINT | 否 | `—` | PK；自增；学生主键 ID，是成绩、请假、投诉及学生员工关系使用的内部标识。 主键（PK）。 |
| `student_no` | VARCHAR(32) | 否 | `—` | 学生唯一业务编号。 |
| `full_name` | VARCHAR(100) | 否 | `—` | 学生姓名，允许重名。 |
| `phone_ciphertext` | VARBINARY(512) | 是 | `NULL` | 加密保存的学生手机号。 |
| `customer_id` | BIGINT | 是 | `NULL` | 关联客户 ID，不自动授予客户账号访问学生数据的权限。 外键（FK）关联 customer_profile.customer_id。 |
| `department_id` | BIGINT | 否 | `—` | 学生教务或服务归属部门 ID。 外键（FK）关联 org_department.department_id。 |
| `login_provider` | VARCHAR(32) | 是 | `NULL` | 学生登录来源，尚未开通账号时为空。 |
| `login_subject` | VARCHAR(128) | 是 | `NULL` | 学生登录身份键，与登录来源同时填写。 |
| `status` | VARCHAR(32) | 否 | `—` | 学生服务或在读状态。 |
| `external_student_id` | VARCHAR(128) | 是 | `NULL` | 教务系统中的学生 ID。 |
| `crm_student_id` | VARCHAR(128) | 是 | `NULL` | CRM 学生独立标识；目标为非空值唯一，类型与学生文档一致；由后续统一迁移核对补齐。 |
| `is_archived` | BOOLEAN | 否 | `0` | 是否已归档，默认 false；归档不删除已有成绩、请假和投诉关联。 |
| `created_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 更新时自动刷新；记录最近更新时间，UTC |
| `row_version` | INT | 否 | `1` | 并发版本号；每次业务修改由后端递增 |

#### A.8 `student_staff_binding`：学生员工授权关系

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `binding_id` | BIGINT | 否 | `—` | PK；自增；学生员工关系记录主键 ID。 主键（PK）。 |
| `student_id` | BIGINT | 否 | `—` | 被服务或管理的学生 ID。 外键（FK）关联 student_profile.student_id。 |
| `employee_id` | BIGINT | 否 | `—` | 承担对应职责的员工 ID。 外键（FK）关联 employee.employee_id。 |
| `relation_type` | VARCHAR(32) | 否 | `—` | 关系类型：class_teacher 班主任、score_editor 成绩人员、service_advisor 服务顾问。 |
| `course_scope_code` | VARCHAR(64) | 是 | `NULL` | 成绩权限限定的课程编码，空值需角色允许相应课程范围。 |
| `is_primary` | BOOLEAN | 否 | `0` | 是否为此业务关系的主要负责人。 |
| `valid_from` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 关系开始生效时间。 |
| `valid_to` | DATETIME(3) | 是 | `NULL` | 关系失效时间，临时代理需要截止时间。 |
| `status` | VARCHAR(32) | 否 | `'active'` | 关系状态：active 有效、disabled 停用。 |
| `created_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 更新时自动刷新；记录最近更新时间，UTC |
| `row_version` | INT | 否 | `1` | 并发版本号；每次业务修改由后端递增 |

#### A.9 `student_score`：学生成绩

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `score_id` | BIGINT | 否 | `—` | PK；自增；学生成绩记录主键 ID。 主键（PK）。 |
| `student_id` | BIGINT | 否 | `—` | 成绩所属学生 ID。 外键（FK）关联 student_profile.student_id。 |
| `course_code` | VARCHAR(64) | 否 | `—` | 受控课程编码。 |
| `term_code` | VARCHAR(32) | 否 | `—` | 学期编码。 |
| `assessment_code` | VARCHAR(64) | 否 | `—` | 考试、作业或其他考核项目编码。 |
| `attempt_no` | INT | 否 | `1` | 考核尝试次数，首次为 1，补考递增。 |
| `score_value` | DECIMAL(8,2) | 否 | `—` | 学生实际得分，统一采用数值制，必须填写。 |
| `max_score` | DECIMAL(8,2) | 否 | `—` | 本次考核满分，必须填写且大于零。 |
| `employee_id` | BIGINT | 否 | `—` | 最近录入或更正成绩的员工 ID。 外键（FK）关联 employee.employee_id。 |
| `status` | VARCHAR(32) | 否 | `'valid'` | 成绩状态：valid 有效、void 作废。 |
| `created_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 更新时自动刷新；记录最近更新时间，UTC |
| `row_version` | INT | 否 | `1` | 并发版本号；每次业务修改由后端递增 |

#### A.10 `student_admin_service`：本地学生行政申请

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | BIGINT | 否 | `—` | PK；自增；主键 |
| `student_id` | BIGINT | 否 | `—` | 统一学生ID |
| `apply_type` | VARCHAR(20) | 否 | `—` | 申请类型 leave/academic |
| `apply_content` | TEXT | 否 | `—` | 申请理由/内容 |
| `approval_status` | VARCHAR(20) | 否 | `'pending'` | 审批状态 pending/approved/rejected/cancelled |
| `edu_related_data` | JSON | 是 | `—` | 考务关联扩展信息 |
| `leave_start_at` | DATETIME(6) | 是 | `—` | 请假开始时间（UTC） |
| `leave_end_at` | DATETIME(6) | 是 | `—` | 请假结束时间（UTC） |
| `reviewer_id` | BIGINT | 是 | `NULL` | 目标物理 FK → employee.employee_id；当前指定审批老师，实际审批操作者另存 operation_log.employee_id。 |
| `reviewed_at` | DATETIME(6) | 是 | `—` | 审批发生时间（UTC） |
| `approval_comment` | TEXT | 是 | `—` | 审批意见/驳回原因 |
| `request_key` | VARCHAR(128) | 否 | `—` | 请求幂等键 |
| `request_hash` | CHAR(64) | 否 | `—` | 规范化请求SHA-256 |
| `row_version` | INT | 否 | `1` | 乐观锁版本 |
| `created_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 创建时间（UTC） |
| `updated_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 更新时自动刷新；最后更新时间（UTC） |

#### A.11 `service_ticket`：投诉反馈工单

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `ticket_id` | BIGINT | 否 | `—` | PK；自增；投诉反馈工单主键 ID，供处理记录引用。 主键（PK）。 |
| `ticket_no` | VARCHAR(32) | 否 | `—` | 统一工单业务编号。 |
| `student_id` | BIGINT | 否 | `—` | 投诉或反馈对应学生 ID。 外键（FK）关联 student_profile.student_id。 |
| `ticket_type` | VARCHAR(20) | 否 | `'complaint'` | complaint 投诉或 suggestion 建议。 |
| `category_code` | VARCHAR(32) | 否 | `—` | 申请、签证、教学等受控分类编码。 |
| `content` | TEXT | 否 | `—` | 学生提交的原始内容。 |
| `ai_summary` | TEXT | 是 | `NULL` | 辅助摘要，不覆盖学生原文。 |
| `priority` | VARCHAR(20) | 否 | `'normal'` | 处理优先级。 |
| `employee_id` | BIGINT | 是 | `NULL` | 当前处理员工 ID，未分派时为空。 外键（FK）关联 employee.employee_id。 |
| `handling_department_id` | BIGINT | 否 | `—` | 当前处理部门 ID。 外键（FK）关联 org_department.department_id。 |
| `status` | VARCHAR(32) | 否 | `'open'` | 工单状态：open 待分派、assigned 已分派、processing 处理中、awaiting_student 待学生确认、closed 已关闭、reopened 已重开。 |
| `first_response_at` | DATETIME(3) | 是 | `NULL` | 首次有效人工回应时间，自动回执不计入。 |
| `response_due_at` | DATETIME(3) | 否 | `—` | 首次回应截止时间。 |
| `resolution_due_at` | DATETIME(3) | 否 | `—` | 当前轮次解决截止时间。 |
| `solution` | TEXT | 是 | `NULL` | 当前解决方案，进入待学生确认状态时必填。 |
| `resolved_at` | DATETIME(3) | 是 | `NULL` | 最近给出解决方案的时间。 |
| `closed_at` | DATETIME(3) | 是 | `NULL` | 当前有效关闭时间。 |
| `reopen_count` | INT | 否 | `0` | 重新打开次数，默认 0。 |
| `satisfaction_score` | TINYINT | 是 | `NULL` | 学生实际评价分数，建议 1—5。 |
| `created_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 更新时自动刷新；记录最近更新时间，UTC |
| `row_version` | INT | 否 | `1` | 并发版本号；每次业务修改由后端递增 |

#### A.12 `service_ticket_record`：工单处理记录

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `ticket_record_id` | BIGINT | 否 | `—` | PK；自增；投诉处理记录主键 ID。 主键（PK）。 |
| `ticket_id` | BIGINT | 否 | `—` | 本条业务记录所属工单 ID。 外键（FK）关联 service_ticket.ticket_id。 |
| `record_type` | VARCHAR(32) | 否 | `—` | 记录类型：分派、人工回应、备注、解决、确认、重开或升级。 |
| `employee_id` | BIGINT | 是 | `NULL` | 操作员工 ID，外键关联 employee.employee_id；员工操作时填写。 |
| `student_id` | BIGINT | 是 | `NULL` | 操作学生 ID，外键关联 student_profile.student_id；学生反馈时填写。 |
| `service_code` | VARCHAR(64) | 是 | `NULL` | 自动处理的受控服务编码；系统操作时填写，不作为员工或学生 ID。 |
| `content` | TEXT | 是 | `NULL` | 本次沟通、反馈或处理说明。 |
| `visibility` | VARCHAR(20) | 否 | `'internal'` | internal 内部可见或 student_visible 学生可见。 |
| `to_status` | VARCHAR(32) | 是 | `NULL` | 本次处理后工单状态。 |
| `cycle_no` | INT | 否 | `1` | 当前处理轮次，初次为 1，重开后递增。 |
| `record_key` | VARCHAR(160) | 否 | `—` | 唯一业务记录去重键。 |
| `created_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |

#### A.13 `knowledge_entry`：新人指南和制度知识

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `knowledge_id` | BIGINT | 否 | `—` | PK；自增；知识条目主键 ID。 主键（PK）。 |
| `entry_code` | VARCHAR(64) | 否 | `—` | 知识条目唯一编码。 |
| `title` | VARCHAR(200) | 否 | `—` | 知识标题。 |
| `entry_type` | VARCHAR(20) | 否 | `—` | faq 标准问答或 document 制度文档。 |
| `category_code` | VARCHAR(32) | 否 | `—` | 入职、制度或业务流程等分类编码。 |
| `question` | TEXT | 是 | `NULL` | FAQ 标准问题，faq 时必填。 |
| `answer` | TEXT | 是 | `NULL` | FAQ 标准答案，faq 时必填。 |
| `content_text` | LONGTEXT | 是 | `NULL` | 文档正文，document 时应有正文或受控来源。 |
| `source_reference` | VARCHAR(512) | 是 | `NULL` | 原文件、章节或受控资料来源定位。 |
| `employee_id` | BIGINT | 否 | `—` | 知识维护员工 ID。 外键（FK）关联 employee.employee_id。 |
| `access_department_id` | BIGINT | 是 | `NULL` | 限定访问部门；为空表示全体员工可见。 外键（FK）关联 org_department.department_id。 |
| `version_no` | INT | 否 | `1` | 当前内容版本号，内容变更时递增。 |
| `status` | VARCHAR(32) | 否 | `'draft'` | draft 草稿、published 已发布、disabled 停用。 |
| `reviewer_employee_id` | BIGINT | 是 | `NULL` | 审核该版本的员工 ID。 外键（FK）关联 employee.employee_id。 |
| `reviewed_at` | DATETIME(3) | 是 | `NULL` | 审核完成时间。 |
| `effective_from` | DATETIME(3) | 是 | `NULL` | 已发布知识开始生效的时间。 |
| `expires_at` | DATETIME(3) | 是 | `NULL` | 知识失效时间。 |
| `index_status` | VARCHAR(20) | 否 | `'pending'` | 索引状态：pending 待更新、ready 可检索、failed 失败。 |
| `external_document_id` | VARCHAR(128) | 是 | `NULL` | Dify 或外部索引中的文档 ID。 |
| `created_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 更新时自动刷新；记录最近更新时间，UTC |
| `row_version` | INT | 否 | `1` | 并发版本号；每次业务修改由后端递增 |

#### A.14 `business_notification`：业务通知

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `notification_id` | BIGINT | 否 | `—` | PK；自增；业务通知记录主键 ID。 主键（PK）。 |
| `entity_type` | VARCHAR(32) | 否 | `—` | 关联业务实体类型，如请假、投诉或跟进。 |
| `entity_id` | BIGINT | 否 | `—` | 关联业务记录 ID，由业务服务按实体类型校验。 |
| `event_code` | VARCHAR(64) | 否 | `—` | 业务通知原因，如待审批、审批结果或投诉解决。 |
| `employee_id` | BIGINT | 是 | `NULL` | 员工接收人 ID，与学生接收人二选一。 外键（FK）关联 employee.employee_id。 |
| `student_id` | BIGINT | 是 | `NULL` | 学生接收人 ID，与员工接收人二选一。 外键（FK）关联 student_profile.student_id。 |
| `channel` | VARCHAR(20) | 否 | `—` | 投递渠道，如站内或企业消息。 |
| `title` | VARCHAR(200) | 否 | `—` | 通知标题，只包含必要信息。 |
| `content` | TEXT | 否 | `—` | 通知内容，不包含敏感业务原文。 |
| `dedupe_key` | VARCHAR(160) | 否 | `—` | 包含业务事件、轮次、接收人及渠道的唯一通知键。 |
| `delivery_status` | VARCHAR(20) | 否 | `'pending'` | pending 待发送、sending 发送中、sent 已发送、failed 失败、dead_letter 终止重试。 |
| `attempt_count` | INT | 否 | `0` | 已尝试发送次数，初值 0。 |
| `next_retry_at` | DATETIME(3) | 是 | `NULL` | 下一次允许重试时间。 |
| `lease_until` | DATETIME(3) | 是 | `NULL` | 发送任务租约截止时间，用于恢复中断任务。 |
| `sent_at` | DATETIME(3) | 是 | `NULL` | 对应渠道确认接收消息的时间。 |
| `read_at` | DATETIME(3) | 是 | `NULL` | 真实已读时间，不支持回执时为空。 |
| `last_error_code` | VARCHAR(64) | 是 | `NULL` | 最近一次发送失败的脱敏错误码。 |
| `created_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 更新时自动刷新；记录最近更新时间，UTC |
| `row_version` | INT | 否 | `1` | 并发版本号；每次业务修改由后端递增 |

#### A.15 `operation_log`：业务操作与幂等回执

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `operation_log_id` | BIGINT | 否 | `—` | PK；自增；业务操作记录主键 ID。 主键（PK）。 |
| `operation_key` | CHAR(64) | 否 | `—` | 操作唯一键，由真实操作者、动作和请求幂等键确定，与新建对象 ID 无关。 |
| `employee_id` | BIGINT | 是 | `NULL` | 真实操作员工 ID，外键关联 employee.employee_id。 |
| `student_id` | BIGINT | 是 | `NULL` | 真实操作学生 ID，外键关联 student_profile.student_id。 |
| `service_code` | VARCHAR(64) | 是 | `NULL` | 执行自动操作的受控服务编码，不伪装成员工或学生身份。 |
| `action_code` | VARCHAR(64) | 否 | `—` | 预先定义的业务动作编码。 |
| `entity_type` | VARCHAR(32) | 否 | `—` | 被操作业务实体类型。 |
| `entity_id` | BIGINT | 是 | `NULL` | 关联对象 ID，新建未完成或失败时可为空。 |
| `request_key` | VARCHAR(128) | 否 | `—` | 逻辑业务请求幂等键，同一提交重试保持不变。 |
| `parameters_hash` | CHAR(64) | 否 | `—` | 规范化业务参数摘要，用于识别相同幂等键下的参数冲突。 |
| `before_data` | JSON | 是 | `NULL` | 变更前必要业务快照，敏感字段按规则保护。 |
| `after_data` | JSON | 是 | `NULL` | 变更后必要业务快照，保留审批及修订结果。 |
| `change_reason` | TEXT | 是 | `NULL` | 人工更正、移交、驳回、删除等业务原因。 |
| `operation_status` | VARCHAR(32) | 否 | `'processing'` | 操作状态：processing 处理中、succeeded 成功、failed 失败、pending_external 等待外部结果、unknown_external 外部结果待核实。 |
| `result_reference` | JSON | 是 | `NULL` | 受控操作回执和对象标识，用于重复请求返回原结果。 |
| `external_request_id` | VARCHAR(128) | 是 | `NULL` | 外部系统请求标识，用于查询写回结果和对账。 |
| `error_code` | VARCHAR(64) | 是 | `NULL` | 操作失败、冲突或待核实的脱敏错误码。 |
| `finished_at` | DATETIME(3) | 是 | `NULL` | 操作形成明确成功或失败结果的时间。 |
| `created_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 记录创建时间，UTC；连接必须设置 time_zone 为 +00:00 |
| `updated_at` | DATETIME(3) | 否 | `CURRENT_TIMESTAMP(3)` | 更新时自动刷新；记录最近更新时间，UTC |
| `row_version` | INT | 否 | `1` | 并发版本号；每次业务修改由后端递增 |

#### A.16 学生交接中的另一套请假结构（仅差异参考）

`student_leave_request` 不计入上述本地 15 张基线表，也不是本轮新增表。现有交接文档及归档企业 SQL 使用此结构：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `leave_request_id` | BIGINT | 自增主键，交接接口中 `apply_id` 对应此值 |
| `request_no` | VARCHAR(32) | 唯一申请编号 |
| `student_id` | BIGINT | 学生外键，必填 |
| `leave_type` | VARCHAR(32) | 请假类型，必填 |
| `start_at`、`end_at` | DATETIME(3) | 起止时间，必填，结束晚于开始 |
| `reason` | TEXT | 请假原因，必填 |
| `attachment_key` | VARCHAR(512) | 可空，受控附件定位 |
| `approver_employee_id` | BIGINT | 可空，当前审批老师 |
| `status` | VARCHAR(20) | 默认 `submitted`；`approved/rejected/withdrawn` |
| `submitted_at` | DATETIME(3) | 提交时间，默认当前时间 |
| `decision_employee_id` | BIGINT | 可空，实际决策老师；审批完成必填 |
| `decision_at` | DATETIME(3) | 可空，实际决策时间；审批完成必填 |
| `decision_comment` | TEXT | 可空，驳回时必填 |
| `created_at`、`updated_at` | DATETIME(3) | 创建/更新时间 |
| `row_version` | INT | 默认 1，条件更新递增 |

此结构仅作为旧契约及历史迁移依据，**不作为新的并行事实表**。后续按第 2.4 节统一到 `student_admin_service`；只有已有旧调用方时才实施版本适配，只有确有历史数据时才实施一次性迁移。本轮只修订方案文档，不改代码或数据库。


### 学生 S八：七张专属表73字段与公共关联

来源：`msj_jlj_原文无损合并.md` 的学生 S八：七张专属表73字段与公共关联。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

本节展开 **7 张学生专属表（5 张业务表 + 2 张会话表）** 的目标字段，公共表普通字段使用企业文档字段字典。下列字段及附录 B 的类型、主键、唯一键和外键共同构成目标结构；不能只建列而漏建组合唯一键或外键。均需后续迁移和数据库验证，不代表实际已建表。

#### 8.1 个人表总览

| 实际表名及中文注释                                     | 字段数 | 对应功能             |
| --------------------------------------------- | --- | ---------------- |
| mental_health_profile（学生心理评估历史表）              | 11  | 每轮辅助情绪评估与高风险判断追溯 |
| mental_warning（学生心理预警及人工处置表）                  | 13  | 高风险预警、老师接手、跟进和关闭 |
| student_academic_event（学生学业截止与考试节点镜像表）        | 14  | 教务同步、节点查询与改期处理   |
| student_academic_reminder（学生学业提醒设置与执行状态表）     | 10  | 设置、取消、重排与投递提醒    |
| student_application_progress（学生留学申请阶段最新进度镜像表） | 12  | CRM同步及本人多申请进度查询  |
| student_assistant_session（学生助手会话表）            | 5   | 会话归属与并发版本控制      |
| student_assistant_turn（学生助手对话轮次与回执表）          | 8   | 历史对话、幂等回执及模型结果追溯 |

#### 8.2 mental_health_profile（学生心理评估历史表）

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

#### 8.3 mental_warning（学生心理预警及人工处置表）

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


#### 8.4 student_academic_event（学生学业截止与考试节点镜像表）

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

#### 8.5 student_academic_reminder（学生学业提醒设置与执行状态表）

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

#### 8.6 student_application_progress（学生留学申请阶段最新进度镜像表）

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

#### 8.7 student_assistant_session（学生助手会话表）

对应功能：会话归属与并发版本控制。

| 英文字段名      | 字段中文名  | 类型          | 中文注释        | 对应功能/用途                 |
| ---------- | ------ | ----------- | ----------- | ----------------------- |
| session_id | 会话编号   | VARCHAR(64) | 会话唯一标识      | 学生会话唯一标识，不等同于公共登录 Token |
| student_id | 所属学生编号 | BIGINT      | 所属学生内部主键    | 关联学生，限定本人数据和跨表归属        |
| version    | 并发版本号  | INTEGER     | 会话并发版本号     | 会话或业务并发版本，防止并发覆盖        |
| created_at | 创建时间   | DATETIME    | 创建时间（UTC）   | 记录创建时点，用于排序与追溯          |
| updated_at | 最近修改时间 | DATETIME    | 最近更新时间（UTC） | 记录最近修改时点，用于新鲜度与追溯       |

#### 8.8 student_assistant_turn（学生助手对话轮次与回执表）

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

#### 8.9 公共表：仅列关联外键字段

##### 个人表指向公共表

| 个人表外键字段                                 | 公共表被关联字段（通常是主键）                   | 中文说明/对应功能     |
| --------------------------------------- | --------------------------------- | ------------- |
| mental_health_profile.student_id        | student_profile.student_id（学生档案表） | 评估属于哪名学生      |
| mental_warning.student_id               | student_profile.student_id（学生档案表） | 预警属于哪名学生      |
| mental_warning.follower_id              | employee.employee_id（员工/老师表）      | 哪位老师负责处理预警    |
| student_academic_event.student_id       | student_profile.student_id（学生档案表） | 考试或截止节点属于哪名学生 |
| student_application_progress.student_id | student_profile.student_id（学生档案表） | 申请进度属于哪名学生    |
| student_assistant_session.student_id    | student_profile.student_id（学生档案表） | 会话归属与隔离       |
| student_assistant_turn.student_id       | student_profile.student_id（学生档案表） | 本轮消息及回执归属     |

`student_academic_reminder` 通过 `(academic_event_id, student_id) → student_academic_event.(id, student_id)` 组合外键保证同一学生，不另建直连公共学生表的 FK。预警使用 `(profile_id, student_id) → mental_health_profile.(id, student_id)`；对话轮次统一使用 `(session_id, student_id) → student_assistant_session.(session_id, student_id)`，不再只按单列会话 ID 关联。三个目标组合键均需显式 UNIQUE，约束与类型见附录 B。

##### 复用业务所涉及的公共表关联字段

| 公共表（中文注释）                         | 关联外键字段 → 对应表字段                                                                                                                   | 对应功能                        |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| user_account（统一登录账号表）             | student_id → student_profile.student_id；employee_id → employee.employee_id                                                       | 登录身份关联                      |
| student_profile（学生档案表）            | department_id → org_department.department_id                                                                                     | 学生组织归属                      |
| student_staff_binding（学生与服务老师绑定表） | student_id → student_profile.student_id；employee_id → employee.employee_id                                                       | 定位负责老师                      |
| student_admin_service（学生行政事务申请表） | student_id → student_profile.student_id；reviewer_id → employee.employee_id | 请假归属与指定审批老师；目标均要求物理 FK |
| service_ticket（服务工单表）             | student_id → student_profile.student_id；employee_id → employee.employee_id；handling_department_id → org_department.department_id | 投诉所属学生、处理人和部门               |
| service_ticket_record（工单沟通与流转记录表） | ticket_id → service_ticket.ticket_id；student_id → student_profile.student_id；employee_id → employee.employee_id                  | 沟通对应的工单与操作者                 |
| business_notification（业务通知表）      | student_id → student_profile.student_id；employee_id → employee.employee_id                                                       | 学生/老师通知接收关系                 |
| operation_log（业务操作与幂等审计表）         | student_id → student_profile.student_id；employee_id → employee.employee_id                                                       | 真实操作者归属与审计                  |

目标约束：`student_admin_service.reviewer_id → employee.employee_id` 采用可空物理 FK，未分派为 NULL，不能存虚拟员工 ID；是否需增量补约束由后续数据库核对决定，不声称当前已存在。`course_project` 仅作只读项目依赖，不与个人表建立 FK。`org_department.employee_id` 的主管引用也统一规划物理 FK，部门/员工循环依赖的创建顺序见附录 B。

本节合计：个人表 7 张、个人字段 73 个；公共表仅列关联字段，不计入个人建表数量。


### 累计表范围与对象版本

六模块按表名去重的直接相关规划范围为36表（原19+企业学生22−共享5）；企业学生43条目标FK属于22表子范围。student_leave_request为停用结构／迁移参考，不计入目标事实表；course_project已包含在客服六表。报告customer_judgement仍为额外依赖，规划数不表示实存数。

提醒设置代次、预警API版本映射及各对象并发条件以第十六章联合契约为准。真实结构、版本和并行规格的剩余核对事项统一见第十八章。

## 十、文件完整性与联动交付核对

### 1. 保留范围

两份源文件的功能表、所有文件目录、文件用途、客服完整字段、索引外键、知识库及脚本资产均合并保留：公共文件见第七章“公共模块”，客服业务文件及待交付资产见第七章“客服模块”。共用的 main.py、config.py、database.py、core/dify.py、core/response.py 等只需一份实际实现，两处列出表示两个模块复用同一文件，不应复制成平行代码。

原文档中“当前未发现”的 DSL、知识库和脚本继续标记为待交付资产，未通过改写目录树把它们描述成已存在。此前快照与后续交付可能不同，检查项目时应以新核验结果更新状态，而不是静默删除文件清单。

### 2. 统一交付核对入口

公共、客服、研判、报告、企业和学生的剩余交付、接口接入、DDL、模型及跨模块验收事项已合并至第十八章，原分模块重复核对表移除。验收步骤和用例要求继续见第十三章、第十六章B.8；独立角色／接口清单的同步状态一并按末章核对。

## 十一、实施基线与版本核对

本节至第十五节吸收 allm.md 中的文件冲突处理、合并步骤、迁移回滚和兼容性安排，并修正未经核验的仓库选择、权限与约束结论。这里提供后续执行方案，不表示已经执行代码合并或数据迁移。

### 1. 文档主体与实施仓库

本文件继续作为公共基础能力与客服模块的主操作文档。D:/AI/StuProject 为本文系统路径，不因另一份方案使用不同电脑路径就废弃；allm.md 提到的 c:/Users/Windows/PycharmProjects/StuProject 作为另一份工作副本线索，不作为已经确定的合并基座。

实施前记录双方仓库、分支、提交号或交付包校验值、未提交改动和数据库版本。由实际文件差异与可运行结果选择目标分支或隔离工作目录，保留原目录和回退版本，不直接覆盖唯一工作副本。没有拿到双方实际版本前，不认定某方副本较新或已包含全部公共能力。

### 2. 实现状态核对入口

不同工作副本的路由、real客户端、消息事务、资产和数据库差异统一见第十八章；执行时须使用带版本与日期的证据更新状态。

### 三方基线与新增来源说明

本节来源用于说明设计基线，不将其他工作副本的实现描述视为已验证事实。

### 报告来源与本轮核对边界

新增来源为 `业务文档/09杂谈/操作文档个人版/cyl合并后.md`，来源正文标题为“allm.md”。本轮读取现有主文档和该文件；其引用的 cyl.md、DDL、代码、其他副本、桌面 Excel 及部署均未独立核验。来源的“当前未挂鉴权”“未落地”等继续标为来源状态，所称“相同22字段”“纯增量”“与all.sql一致”均为待核对判断。

前两轮公共/客服/研判的来源、历史差异及规划性质继续保留，不能回到仅含公共/客服/报告的三模块基线。后续实施应记录四模块实际版本、未提交改动、权限配置、上游对象及目标数据库版本。

### 新增来源的原始企业状态声明

来源：`msj_jlj_原文无损合并.md` 的新增来源的原始企业状态声明。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

#### 企业管理模块实施方案说明

> 日期：2026-10-16。状态：开发阶段协作方案，企业与学生模块均未完成落地测试或联合验收。  
> 本轮交付：仅修订本文件与同目录 `jlj.md`，不修改代码、SQL、Dify YAML、配置或数据库。  
> 最终口径：**NL2SQL 只读；增删改由普通大模型提取动作和关键字段，再调用预先编写的硬编码业务接口或服务。**
> 本次方案修订：统一公共 JWT 与唯一请假表 `student_admin_service`。学生模块维护请假、心理及老师接口；企业开发页面/编排及工单处理，不重复开发审批服务。双方采用完全相同的“附录 B：联合协作契约 V1”，共享字段、职责、状态、权限和主外键均以此为准。


### 新增来源的原始学生状态声明

来源：`msj_jlj_原文无损合并.md` 的新增来源的原始学生状态声明。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

#### 蒋立建个人操作文档

模块名字：学生智能助手  
负责人：蒋立建  
更新日期：2026-10-16  
系统目录：`StuProject/`（以实际工作区根目录为准）

本模块计划通过一个统一学生智能体提供请假、投诉建议、心理辅助关怀、学业提醒、申请进度、生活咨询及升学推荐，并与公共认证、企业老师端、教务、CRM 和通知任务对接。本文是开发阶段设计说明，不包含实现代码示例。

**阶段状态：学生、企业两个模块均在开发中，未完成落地测试或联合验收。**历史提交与测试描述不作为本方案已可运行的证据。本次仅修订本文件和同目录 `msj.md`；不修改代码、SQL、数据库、配置或接口导出文件。两份文档采用相同的“附录 B：联合协作契约 V1”，共享字段、权限、状态、职责和主外键以该契约为准，未经双方同步修订不得另起同义表或审批服务。


### 本轮来源与重复附录核对结果

本轮仅读取现主文档与用户指定的msj_jlj_原文无损合并.md；其内两份附录B正文在统一换行及去除首尾空行后逐字一致，合并为第十六章一份共同契约，正文内容完整保留，不重复生产两份可独立演变的契约。

来源“本轮只修订msj.md/jlj.md”“修改附录必须同时修改两份”描述其原协作过程，不扩大本次任务范围。本次只更新主操作文档，未改原来源或其引用的msj.md、jlj.md；后续若另行修改契约才需协调原维护方。来源引用代码、DDL、OpenAPI、数据或历史实现均未重新核验；“当前代码保持空值”等写法仅为来源叙述，不作为本次事实。


### 当前实施背景

实施与核验基准为`D:\AI\StuProject`；用户说明暂时没有真实业务数据、旧调用方，后端使用conda环境`SST`，本地记录Python 3.11.16，项目存在environment.yml及根.env。此背景不等于测试数据可删或数据库必为空；条件迁移仅在发现存量时适用。

当前权限目标见第二章；本地教务／CRM、faster-whisper与个人页通知见第八章，报告分类调度见第五章。历史问答中的已确认选择与已完成文档勘误不再作为问题记录保留。

### 权限来源覆盖与适用范围

以下均位于用户指定目录。来源中的工作副本状态、建议增表及技术实现不自动转为本目录事实；本轮只采纳明确权限/职责和范围规则。

| 文件 | 已核对章节/内容 | 本轮用于权限清单的依据及限制 |
| --- | --- | --- |
| 开发文档-Albert2.md | 1.4/1.4.1项目角色与权限原则、3.5安全、4.3—4.5各模块、8.1页面 | 访客/学生/员工/老师/部门管理/内容运营/系统管理员职责；多角色RBAC、本人/部门/负责学生、系统配置权限、敏感专门授权；页面合列“老师/管理人员”不扩大用户已定报告人群 |
| 开发文档_msj.md | 1.1角色边界、2共用链、3.1—3.5模块、5/6契约安全 | 授权客户/班级/工单、学生本人、按部门管理、独立任务身份、固定服务写入、心理报告不含个人明细；“管理员/管理层”合并表述不推导主管具有全部配置权 |
| 开发文档sgt.md | 5.3接口注意、第六章原则、第七章阶段0/2、第九章验收、第十章第10项 | 研判单条/批量/复核功能、本人/班级/部门范围、权限矩阵尚需补齐；没有最终analyst/reviewer动作分配或负责人姓名 |
| 开发文档_hzl.md | 第2章原则、第3章阶段0/2—5、第5章契约、第7章第10项 | 本人/班级/部门、严格心理授权、学生投诉和老师闭环、只读SQL；来源仍声明角色职责/范围未完整给出 |
| 开发文档_cyl.md | 企业助手/学生助手模块、智能报告模块、日报与部门数据说明 | 团队日报与五类管理报告用途、学生服务链；未给报告五动作逐角色矩阵，不能据报告功能描述补授主管配置 |
| 开发文档Albert.md | 3.5安全、4.3—4.5模块、8.1页面 | 只读NL2SQL、管理人员按部门日报、学生与老师闭环、系统管理员配置/规则/审计；页面是展示分组，不是老师自动取得报告权 |
| 开发文档_mrz.md | 第2章SQL校验、第3章场景、第4章模块、第7章前端 | 按角色白名单、学生本人、部门过滤；“员工不能访问预警表”用于普通员工，负责老师受控访问按更具体来源；所有场景NL2SQL及模型写SQL不替换主文档既有固定服务写入边界 |
| 开发流程.md | 阶段三鉴权与上下文、阶段四管理看板、阶段五越权/行级权限 | 按角色接口/表白名单、行级过滤及学生→班主任闭环；未给员工子角色精确权限，不推导新授权 |
| 总体讲解.md | 架构、通用工具、业务需求说明 | 无具体角色动作矩阵；“业务需求各自确认”不能填补缺失授权 |


## 十二、同名文件冲突处理与保留规则

以模块负责人审核业务语义为原则，先比较再合并；“负责人维护”不等于把整份文件无条件覆盖。文件版本、调用契约、有效修复及其他模块依赖都需要保留。不同目录中的 agent.py、README.md、__init__.py 按完整相对路径区分，不因同名改名或互相覆盖。

| 相对路径 | 主责与合并方式 | 必须保留/核对的内容 |
| --- | --- | --- |
| app/main.py | 公共入口由公共负责人汇总双方路由和生命周期改动 | auth 与 agent 按交付状态挂载；其他模块已用路由保留；缺失模块不能无条件 import；异常注册不重复 |
| app/config.py | 公共负责人合并配置字段，业务负责人确认场景含义 | JWT、权限路径、DB、日志及各业务 Dify 配置；同名不同含义不按字段取并集掩盖冲突；旧配置兼容需明确 |
| app/database.py | 逐项比较并保留唯一数据库入口 | 同一 Base/元数据、连接池、会话、UTC 约定及释放流程；不因合并启动自动建表 |
| app/access_control.yaml | 公共负责人审核身份权限，业务负责人核对权限清单 | 保留已授权且有效的其他业务项，修正报告范围等已知差异；不凭菜单可见性代替接口鉴权 |
| app/api/auth.py | 公共负责人确认登录和清单接口 | 三个公共接口契约、JWT 返回字段及已有调用方兼容 |
| app/core/auth.py | 公共负责人维护唯一身份认证依赖 | JWT 签名/有效期、真实账号查表及身份关联，不能只信任客户端身份 |
| app/core/authorization.py | 公共负责人维护接口权限组件 | 显式权限标识、拒绝路径和当前账号上下文；保持业务范围仍由业务层校验 |
| app/core/logger.py | 公共负责人合并已验证修复 | 日志输出及初始化幂等；删除未使用导入可保留，但不能据此判定整份版本更完整 |
| app/core/response.py | 公共负责人合并错误出口 | 企业及其他已用路径的 HTTP/参数校验处理，不丢已有修复；统一返回协议需要调用方验收 |
| app/core/dify.py | 公共负责人维护唯一 HTTP 传输层 | 同步/异步方法、应用 Key、超时、错误与 JSON 对象契约，客服业务解析仍在适配器 |
| app/services/auth_service.py | 公共负责人审核账号及 JWT 服务 | 密码哈希校验、签发/解析算法、有效期与真实用户 ID |
| app/models/user_account.py | 公共负责人主责，数据库负责人核对 | 九个字段及关联、类型精度、唯一键和身份 CHECK；模型与数据库差异单独记录 |
| app/schemas/auth.py | 公共负责人审核请求约束 | 登录字段、长度及既有错误约定 |
| app/clients/nl2sql_dify.py | 场景负责人确认后与公共传输层配套合并 | 保留实际业务输入/输出契约，不能因底层 HTTP 共用就覆盖场景解析；不自动扩大本次工作范围 |
| app/clients/report_dify.py | 报告场景负责人确认适配行为 | 报告输入、输出字段及错误转换，避免公共层改动破坏其他业务 |
| scripts/sql/all.sql | 数据库负责人逐表审核双方结构 | 不按表数选“更全”版本；保留字段、索引、约束和状态含义；运行库升级另用经审核的增量迁移 |
| .env | 仅在部署环境逐项映射配置，原配置保留受控备份 | 不把两份密钥机械拼接，不披露或提交真实值；同名值冲突需按目标环境选择 |
| environment.yml | 依赖负责人核对兼容后合并 | 依赖版本、运行环境及认证/HTTP/数据库驱动；同包不同版本需解决兼容，不能简单取并集 |
| .gitignore | 汇总并核对忽略规则 | 覆盖 .env、日志、缓存和本地运行数据；历史已跟踪文件不会因新规则自动停止跟踪，发现后单独处理 |

客服专属 api/agent.py、services/agent_service.py、services/dify_client.py、models/agent.py、schemas/agent.py 由客服负责人维护，与公共组件一起回归。第七章列出的 DSL、知识资料、映射 JSON、种子和联调脚本逐项进入交付清单；保留缺失与历史状态，不凭目录树认定文件齐全。

### 三模块共用文件的补充合并规则

来源：`sgtallm.md` 2.2。与本章原规则同时适用；“无同名冲突”仅指方案所列路径，不代表实际磁盘盘点结论。

客户研判新增文件与客服文件无同名冲突（`agent.*` vs `customer.*`、`customer_source` 等），冲突集中在三方共用的公共文件。处理规则如下：

| 相对路径 | 冲突类型 | 主责与合并方式 | 必须保留/核对的内容 |
| --- | --- | --- | --- |
| `app/main.py` | 三方共用 | 公共负责人汇总路由挂载与生命周期 | auth、agent、customer 三组路由按交付状态挂载；其他模块路由保留；异常注册不重复 |
| `app/config.py` | 三方共用 | 公共负责人合并配置字段 | JWT、权限、DB、日志、客服 Dify 配置 + 客户研判 Dify/规则配置；同名不同含义不取并集 |
| `app/database.py` | 三方共用 | 逐项比较，保留唯一数据库入口 | 同一 Base/元数据、连接池、会话、UTC 约定及释放；不自动建表 |
| `app/access_control.yaml` | 公共 + 客户研判 | 公共负责人审核权限映射 | 保留客服匿名开放不受影响；新增 `customer.*` 权限及员工角色细分；不新增 identity_type |
| `app/api/auth.py` | 三方共用 | 公共负责人确认契约 | 三个公共接口契约、JWT 返回字段及既有调用方兼容 |
| `app/core/*`（auth/authorization/logger/response/dify） | 三方共用 | 公共负责人维护唯一实现 | 签名/有效期、权限拒绝路径、日志幂等、错误出口、同步/异步 HTTP 契约 |
| `app/schemas/auth.py` | 三方共用 | 公共负责人审核 | 登录字段、长度及既有错误约定 |
| `scripts/sql/all.sql` | 三方共用 | 数据库负责人逐表审核 | 公共五表 + 客服六表 + 客户研判五表字段/索引/约束；运行库升级用增量迁移，不 DROP 重建 |
| `.env` | 三方共用 | 部署环境逐项映射，原配置受控备份 | 不拼接密钥、不披露真实值；同名冲突按目标环境选择 |
| `environment.yml` | 三方共用 | 依赖负责人核对兼容 | 认证/HTTP/数据库驱动；客户研判若引入 PDF/Excel 解析依赖需一并声明，不简单取并集 |

客服专属 `api/agent.py`、`services/agent_service.py`、`services/dify_client.py`、`models/agent.py`、`schemas/agent.py` 由客服负责人维护；客户研判专属 `api/customer.py`、`services/customer_service.py`、`services/parser.py`、`services/extractor.py`、`services/judge_service.py`、`models/customer_*.py`、`models/product.py`、`models/research_*.py`、`schemas/customer.py`、`clients/extract_dify.py` 由客户研判负责人维护。两者与公共组件一起回归。

### 报告命名与共用文件的合并规则

| 命名冲突 | 处理方式 |
| --- | --- |
| 客服 `agent` 前缀文件 vs 报告 `report` 前缀文件 | 分属不同文件名，无冲突；`app/api/agent.py` 与 `app/api/report.py`、`app/models/agent.py` 与 `app/models/report.py` 并列 |
| `dify/README.md`（客服） vs `dify/report/README.md`（报告） | 分属不同子目录，按完整相对路径区分；不因同名改名或覆盖 |
| `app/clients/report_dify.py`（报告） vs `app/clients/nl2sql_dify.py`（NL2SQL） | 都是场景适配器，复用公共 `core/dify.py`，各自维护业务解析 |
| `scripts/sql/all.sql`（全量） vs `report_module_ddl.sql`（报告） | 报告 DDL 是 all.sql 的抽取，保持一致；不做两份独立版本 |
| 多模块共用 `main.py` / `config.py` / `database.py` / `core/*.py` | 全项目只保留一份实际实现，各模块复用同一文件，不复制成平行代码 |

以上“无冲突”“DDL为all.sql抽取”是来源方案，实际需按完整路径及内容核对。report_auth.py 如作为报告策略依赖，仅编排公共认证与权限，不复制JWT算法或另建权限事实源；新增 report_metrics.py、report_anonymizer.py、report_tasks.py 等需与已有文件盘点后合并。config 和 access_control 同时保留研判与报告提案；main 不得因新增报告而漏掉 customer 路由，schemas/models/clients 同理。

### 企业学生共用路径与职责冲突规则

企业/学生两个目标目录共同涉及student_leave.py、student.py、StudentLeaveService、student_leave_repository.py及公共main/config/auth/authorization/dify/access_control。共享请假只保留学生维护的一份服务，老师路由不再建enterprise_student.py，企业表单与对话同进程直接委托；不同模块的enterprise_ticket和student_ticket按动作职责分工，但复用工单事实及锁/版本策略。

student_shared与enterprise ORM只能投影已有唯一Table元数据；不能重复映射同名事实表或启动自动建表。enterprise_authorization、student_auth、report_auth分别是模块策略入口，不能各自签发/解析第二套人员JWT。旧nl2sql_dify契约不被直接覆盖；新enterprise_nl2sql_dify单独新增，报告固定SQL与student-v1/local查询保持各自契约。


## 十三、分阶段合并步骤与验收

| 步骤 | 动作 | 完成标准与证据 |
| --- | --- | --- |
| 0. 锁定版本 | 取得双方实际版本，记录提交号、工作区改动、配置字段及数据库版本；选择隔离合并目标 | 清楚每份文件来源；保留可回退版本，不废弃原工作目录 |
| 1. 文件盘点 | 按第七、十二章逐路径核对公共、客服及辅助资产；分类为一致、双方修改、独有、缺失 | 形成差异及缺失清单；文件有来源、负责人及处理结论 |
| 2. 合并公共契约 | 核对认证、权限、响应、Dify HTTP、数据库会话和配置 | 公共组件只有一套；既有业务调用契约不被覆盖；必要配置有声明 |
| 3. 接入客服 | 合并真实客服实现、参数模型和 ORM，挂载 auth/agent；其他模块按实际可运行状态处理 | 服务启动无缺失 import，OpenAPI 可见三个公共与六个客服预期接口 |
| 4. 数据库准备 | 按字段、索引及关系核对目标库，判断是否需增量迁移和数据迁移 | 本文件 11 张相关表定义与实际差异清楚；无执行破坏性全量重建 |
| 5. 配置及运行环境 | 配置兼容依赖、真实 JWT 和 Dify 应用 Key，核对本地模型绑定 | 仅启用已配置功能，缺配置给出明确错误；真实值不入交付文档 |
| 6. 按变更验证 | 运行覆盖相关变更的公共认证、客服接口、模型适配及并发检查 | 第十章待接通项逐项有证据；不把其他副本的测试数量作为本次通过结果 |
| 7. 条件迁移与切换 | 仅在有独立数据或结构差异时执行第十四章；完成增量同步或短暂停写 | 记录数、关键业务值、关系和切换点验证一致；可回滚 |
| 8. 可选联动 | 业务明确需要后分别实施可选 JWT、线索、审计或通知增强 | 不改变既有匿名访问；每项有权限、幂等、事务与数据归属约定 |
| 9. 归档 | 记录合并提交、配置模板、迁移脚本版本及验收结果，更新本文件状态 | 已实现、已验证、待办清晰；原文档/原版本有可追溯记录 |

重点验收：

- 公共登录成功取得 JWT；受保护接口分别验证缺失、无效/过期 Token 和无权限请求；错误按约定返回。公共账号的业务关联正确，不能将 user_id 当作 employee_id/student_id。
- 客服六个接口不带 Token 仍可访问；请求/响应字段与已用前端兼容；课程仅上架，活动筛选和详情结果一致，FAQ 兜底符合约定。
- real 路径经过公共 Dify HTTP 工具，Workflow 失败或输出非法也能被识别；会话父子写入、用户消息保存、失败日志与兜底按选定事务规则验证。
- 同活动同手机号已有有效报名时不重复写入；取消后可重新报名。竞争最后一个名额时记录数及 signed_count 一致，失败不留部分写入。
- 日志、响应、数据库会话、配置及公共传输调整后，受影响的学生/报告等已启用调用方通过对应回归；不引入未交付模块的导入失败。
- 备份可恢复、迁移主外键无错连、账号可登录；通知或 Dify 等真实外部依赖只有完成调用验证才写为接通。

以上为执行检查项，本次文档完善未运行这些功能验收。验证按真实变更与失败范围展开，已通过且无新变化的检查不重复运行。

### 三模块合并原则与实施步骤（扩展方案）

1. **保留原有核心功能**：公共三个接口、客服六个接口的路径、请求/响应字段、匿名开放规则不变；客服六表与公共五表字段、索引、外键、CHECK 约束不变。
2. **向后兼容**：不新增 `user_account.identity_type` 取值、不修改既有 CHECK 约束、不改变已签发 JWT 的语义；客户研判权限通过既有身份 + `employee.role_codes` 细分接入。
3. **统一目录层级**：公共文件（main.py、config.py、database.py、core/*、schemas/auth.py、scripts/sql/all.sql 等）只保留一份，三方复用；客服与客户研判业务文件按 `api/`、`services/`、`models/`、`schemas/`、`clients/` 并列存放，不复制平行代码。
4. **冲突先比较再合并**：同名文件由主责负责人审核业务语义后合并，不无条件覆盖；不同目录中的同名文件按完整相对路径区分。
5. **数据迁移条件化**：客户研判五表为新增表，优先走增量建表；只有目标库已存在同名表或需要跨副本归并数据时才执行迁移，不执行含 DROP 的全量重建。

#### 新增研判的分阶段步骤

| 步骤 | 动作 | 完成标准与证据 |
| --- | --- | --- |
| 0. 锁定版本 | 记录三方仓库/分支、提交号、工作区改动、配置字段及数据库版本 | 每份文件有来源、负责人与处理结论；保留可回退版本 |
| 1. 文件盘点 | 按第七章统一目录树逐路径核对公共、客服、客户研判及待交付资产 | 形成一致/双方修改/独有/缺失清单 |
| 2. 合并公共契约 | 合并 main.py、config.py、database.py、access_control.yaml、core/*、schemas/auth.py | 公共组件只一套；客服匿名与公共受保护接口均不被破坏；新增 `customer.*` 权限有声明 |
| 3. 接入客户研判 | 合并 api/customer.py、services/customer_*.py、parser/extractor/judge、models 五表、schemas/customer.py | 服务启动无缺失 import，OpenAPI 可见 3 公共 + 6 客服 + 8 研判预期接口 |
| 4. 数据库准备 | 按第九章核对目标库，新增五表走增量建表 | 16 张相关表定义与实际差异清楚；无破坏性全量重建 |
| 5. 配置与环境 | 合并 JWT、Dify（客服 + 客户研判抽取）配置；真实 Key 不入文档 | 仅启用已配置功能，缺配置给出明确错误 |
| 6. 按变更验证 | 覆盖公共认证、客服接口、客户研判接口、并发与归并检查 | 本章客户研判验收项逐项有证据 |
| 7. 条件迁移 | 仅存在同名表/跨副本数据时执行第十四章客户研判迁移方案；否则不迁移存量 | 记录数、关系、切换点验证一致，可回滚 |
| 8. 归档 | 记录合并提交、配置模板、迁移脚本版本及验收结果 | 已实现/已验证/待办清晰 |


### 客户研判扩展验收清单（未执行）

- 公共登录成功取得 JWT；受保护接口分别拦截缺失、无效/过期 Token 与无权限请求，错误按约定返回。
- 客服六个接口不带 Token 仍可访问；请求/响应与现有前端兼容。
- 客户研判八个接口需登录并具备对应 `customer.*` 权限；研判/复核通过 `employee.role_codes` 区分，管理员不隐含拥有全部 `customer.*`。
- 客户信息接入后能按 text/pdf/excel 正确解析，关键字段提取完整；研判结果严格依据规则、命中/未命中均结构化落库，批量研判逐条汇总。
- 规则可版本化更新，旧版本保留，生效版本唯一；更新不影响已生成的 `research_result`（记录 rule_version）。
- 归并链路可追溯：`customer_source → customer_info → research_result`，`customer_info.customer_id` 回填正确，同号匹配仅提示候选不自动合并。
- 迁移可回滚：新增表建/删可逆，归并动作有对账与回退方案；存量 11 表结构与数据无变化。
- 日志、响应、数据库会话、配置与 Dify 公共传输调整后，客服、客户研判及既有业务（学生/报告等已启用调用方）通过对应回归，不引入未交付模块的导入失败。

以上为执行检查项，本次文档完善未运行这些功能验收。

补充验收：员工角色权限必须能通过公共依赖且拒绝未获授权员工；验证批量研判/规则维护授权缺口，规则并发发布、重复解析/研判、结果历史追溯、source_id 一致性、文件及原文访问范围。涉及主档归并后，不再采用“存量数据无变化”的验收条件，应验证仅有经授权的业务写入且可对账。

### 报告来源实施步骤及四模块校正

以下保留 `cyl合并后.md` 第五章的三模块步骤，作为报告接入子流程；不能替代本章既有研判实施清单。步骤中的接口数与表数是来源范围，后附当前统计。

| 步骤 | 动作 | 完成标准 |
| --- | --- | --- |
| 0. 锁定版本 | 记录三方仓库、分支、提交号、工作区改动、数据库版本 | 来源清晰、可回退 |
| 1. 文件盘点 | 按统一目录树逐路径核对，分类为一致 / 双方修改 / 独有 / 缺失 | 形成差异与缺失清单 |
| 2. 合并公共契约 | 核对认证、权限、响应、Dify HTTP、会话、配置 | 公共组件只一套，已有调用不被覆盖 |
| 3. 接入客服与报告 | 挂载 auth/agent/report 路由，合并 ORM、schema、服务 | 服务启动无缺失 import，OpenAPI 含 3+6+5 接口 |
| 4. 数据库准备 | 核对 14 张表定义与目标库差异，报告三表走增量 DDL + 种子 | 无破坏性全量重建 |
| 5. 权限收敛 | 不向全体employee授report.read；计算平台admin及有效manager的精确动作和范围，配置限平台admin | 管理员/主管按矩阵验收，其他员工拒绝；主管生成/配置均拒绝；范围承载方案仍待实现 |
| 6. 配置与运行环境 | 配置真实 JWT 与 Dify Key，报告路由补鉴权依赖 | 仅启用已配置功能 |
| 7. 按变更验证 | 公共认证、客服六接口、报告五接口、模型适配、并发检查 | 待接通项逐项有证据 |
| 8. 条件迁移 | 仅在有结构差异时执行增量迁移；报告三表为纯增量 | 记录数、关系、切换点一致，可回滚 |
| 9. 归档 | 记录合并提交、配置模板、迁移脚本版本与验收结果 | 已实现 / 已验证 / 待办清晰 |

四模块校正：后续目标包括 auth 3、agent 6、customer 8、report 5，共22个预期操作；直接相关表19张，其中研判5表及报告3表均须按实际状态核验。配置方法/路径/精确权限已由第五章补齐；22仍是方案计数，不是已注册数。报告访问人群、动作及管理员/主管范围均已确认，见第二章当前权限清单；后续实现范围承载、授权计算及上游适配，再合并实际配置/代码。

报告补充验收（本次未执行）：

1. 五接口逐项验证平台管理员/有效manager的允许分支、动作权限及部门范围，普通员工、匿名、客户、学生拒绝；配置拒绝仅有manager的员工；主管仅查看，生成/配置操作均拒绝；角色撤销、调部门及旧Token行为需验证。
2. 同幂等键同口径复用、不同口径冲突；并发只生成一份，失败重试、进程重启及超时后的状态可追踪。
3. 固定SQL只读真实上游，缺失customer_judgement/deal_amount不返回伪造成功指标；研判适配有去重、版本与客户关联规则。
4. 时间窗/时区、快照时点、规则/指标版本一致；正文数字与保存指标能对账。
5. 心理报告在传入Dify之前完成约定脱敏，正文/元数据/日志等路径符合允许输出范围。
6. 周期配置修改、定时触发与人工触发的幂等边界、多调度进程和任务恢复均有证据。
7. 三报告表、五条种子、ORM及两处DDL一致；增量迁移不覆盖已有报告与配置，备份可恢复。
8. 公共、客服和研判按实际改动范围回归；报告接入不使既有角色权限问题或客服待办消失。

### 企业 E12：实施顺序与全部验收目标

来源：`msj_jlj_原文无损合并.md` 的企业 E12：实施顺序与全部验收目标。下列为来源开发目标/历史说明，未核验实现；段内原章号按该来源对应部分理解，附录A并入第九章，附录B统一见第十六章。

本轮只修改本文件与 `jlj.md`。双方目前均未完成落地测试，以下阶段和附录 B 验收条目均为待办，不能标记为已通过。

| 阶段 | 内容 | 可检查结果 |
| --- | --- | --- |
| 1. 基础核对 | 真实表结构、可用既有硬编码服务、员工角色/绑定数据、旧请假数据与实际调用方 | 确认单表目标及是否需要历史迁移/版本适配；不直接执行破坏性重建 |
| 2. 固定业务能力 | 客户、日报、成绩、工单及授权仓储；补齐共享请假查询/审批、公共 JWT 与交接契约 | 无模型可完成学生提交→老师审批→学生结果查询；只写同一事实表，越权、状态及版本被拒绝 |
| 3. 模型动作提取 | Dify 提取 Workflow、预览、确认、动作白名单 | 提取字段后调用固定函数；模型无 SQL 写入能力；确认后不重新解释命令 |
| 4. 只读 NL2SQL | 独立 schema 契约、AST、受限关系、只读账号 | 查询语义正确；所有写语法、基表绕过、跨部门与跨学生查询被拒绝 |
| 5. 知识与语音 | QA/RAG 来源、版本、音频转写及确认 | 制度有来源；部门权限检索前生效；真实语音可完成录入/日报链路 |
| 6. 待办与前端 | 企业工作台、身份头、幂等头、任务投递 | 权限可见性与服务端一致；通知去重、重试、已读语义正确 |
| 7. 跨模块联调 | 已更新的请假目标契约、必要的旧版本适配/数据迁移、CRM/教务、报告只读数据 | 新接口口径一致，旧调用方按已明确的版本接入；不把模拟或导入 OpenAPI 当作真实联调成功 |

关键验收至少覆盖：

- 顾问不能读取/修改他人客户；主管不能跨部门读取日报；班主任不能审批非本人负责请假；教务不能修改未授权课程。
- 学生与老师的请假接口统一使用公共 JWT；旧学生自签登录令牌、学生身份访问审批接口、只有有效 JWT 但缺少班主任关系或指定审批人资格均不得通过。
- 学生提交与老师审批定位同一 `student_admin_service.id`，`apply_type=academic` 不进入请假列表或审批；学生只能查询本人结果。过期版本、重复审批、已撤回后审批及审批/撤回并发均返回冲突且不留下部分写入。
- 同一审批幂等键和相同参数只形成一次业务审批、一次成功审计与一条对应结果通知；同键换参数返回 409，失去权限后不能回放受限回执。实际审批人从审计可追溯，不依赖当前负责人推测。
- 如需旧契约适配，字段/状态转换双向明确，旧表 ID 不能误指向新表同号记录；历史数据迁移逐项核对状态、实际审批人和通知/审计引用，无旧数据时不做无意义迁移。
- 模型缺字段、目标重名或返回非法动作时不写库；模型输出 SQL 片段不能进入固定业务函数。
- 确认凭证跨用户、过期、参数篡改、版本过期均被拒绝；重复提交不重复生成客户、日报、成绩、跟进或通知。
- 成绩范围和唯一键有效；投诉给出方案后等学生确认，企业不代替学生评价。
- SQL 注入、多语句、CTE/子查询绕过、UNION/聚合越权、危险函数、无行数/耗时限制查询被拒绝或限制。
- Dify 缺配置、失败或超时不写库、不编造成功；外部写回结果不明时显示待核实。
- YAML 在目标 Dify 中真实导入、绑定模型/知识库并可调用；密钥只从服务端配置取得。

当前尚需后续环境核验的内容：真实数据库结构、既有企业固定服务是否齐全、真实 Dify 版本与模型、正式 QA/制度资料、CRM/教务权威接口，以及学生模块实际部署契约。本轮不将这些内容视为已经验证。


### 企业学生联合验收与六模块回归范围

第十六章B.8完整保留联合验收表，仍全部待执行。先确定真实结构、角色/绑定和公共权限，验证无模型的固定服务闭环，再接模型预览/确认、受控查询及任务；不能先用页面或DSL导入截图宣称业务接通。

联合22表/43FK/三个组合UNIQUE是两模块检查范围；其他客服/研判/报告约束也需按实际改动回归。尤其报告消费新增上游的版本、状态、脱敏口径，客服匿名、研判受保护以及报告管理员提案不能被企业/学生新接口中间件误改。文档一致性检查不能代替接口、数据库、并发与故障验收。


## 十四、条件式数据库迁移、切换与回滚

### 1. 先判断是否需要迁移

| 实际情况 | 处理方式 |
| --- | --- |
| 只有两份代码，没有独立业务数据，目标结构一致 | 不迁移数据，只合并代码和核对结构 |
| 目标为空库 | 可在明确确认空库和初始化范围后使用核对过的建表方案；完成必要主数据及种子验证 |
| 目标已有数据，结构存在差异 | 使用备份、差异报告及增量迁移；不能直接执行含 DROP/重建的 all.sql |
| 双方都有需要保留的数据 | 先制定身份/业务去重及逐表主键映射，再迁移；不以统一 ID 偏移替代关系核对 |

allm.md 中“先用 all.sql 建目标表”的做法仅适合确认的空目标库。对已有数据环境，先核验脚本内容与实际结构，生成保留现有数据的增量变更；本文件不提供可直接执行的破坏性操作。

### 2. 迁移前准备

保存源/目标数据库、配置和对应应用版本的受控备份，验证能恢复；记录行数、业务唯一键、主键范围、约束、时区及敏感字段加密/匹配方式。明确目标是否为空、停写时间、责任人、成功标准和回滚触发条件。没有独立数据的模块不做无意义的数据搬迁。

### 3. 身份与主外键映射

| 对象 | 正确处理 | 不应采用的简化 |
| --- | --- | --- |
| user_account.user_id | 处理用户名和账号关联冲突，建立源账号→目标账号映射，账号合并需核实同一身份 | 只对 user_id 加偏移就认为所有关系已迁移 |
| employee/customer_profile/student_profile | 分别根据可靠业务标识核实重复与唯一键，建立各自主键映射 | 账号 ID 的变化不代表三个业务 ID 必须同步加同一偏移 |
| org_department | 按编码及层级关系核对，先映射上级、部门及员工关联，再处理主管逻辑引用 | 直接按部门名称重合并或将源部门 ID 写入目标 |
| event_signup / lecture_event | 映射活动 ID 与报名外键，保留状态式去重及取消后再报名规则，复核名额和已报名数 | 仅按手机号合并报名，或导入后不复核计数 |
| chat_session / chat_message | 处理 session_id 碰撞并同步更新消息引用，保留历史与访客标识语义 | 用匿名访客 user_id 自动匹配统一账号，或改父表标识不改消息 |
| 其他已存在业务引用 | 盘点实际引用这些 ID 的成绩、工单、通知、审计等记录，按受控实体类型应用映射 | 只迁账号表却遗留业务引用，或盲目修改所有 entity_id |

user_account 的准确约束为：identity_type=admin 时 employee_id、customer_id、student_id 全为空；employee/customer/student 身份只填写其对应的一项，另外两项为空，且相应业务记录有效存在。不能概括成“所有身份都必须有一个外键非空”。

若需要变更电话加密或匹配密钥，必须由受控流程兼容旧密文并重新生成匹配值，不能直接混用两套 token 去重；没有可靠明文/解密及重建条件时，保留隔离数据并记录待处理，不凭号码猜测合并客户。

### 4. 凭据、数据验证与切换

密码哈希兼容性通过实际校验确认，不把新用户哈希配置一致作为旧哈希一定兼容的充分条件。若要求已签发 JWT 持续有效，需核对签名密钥、算法、sub 账号映射、有效期及验证逻辑；即使密钥相同，若 user_id 改变，旧 Token 的 sub 仍可能指错目标账号，必须重新登录或采用受控过渡方案，不能承诺自动兼容。

迁移在隔离环境或临时目标先验证：按数据来源比对记录数与业务汇总、检查主外键/唯一键/CHECK、抽样核对账号身份和业务归属、执行登录/权限及报名场景。不同数据库版本检查约束的能力不同，不能只查询元数据就认为历史记录全部通过校验。

正式切换前明确短暂停写或增量同步策略及最终同步点。双跑对比使用隔离通知和外部写入的只读/验证方式，避免两个实例同时发通知或创建外部业务。验证通过后切流，原库保留受控只读快照及回退信息。

### 5. 回滚

切换前失败时停止迁移并恢复到已验证的目标备份/隔离副本，原服务保持原状态。切换后如有新写入，先停止相关写流量、记录切换后的增量并决定回放/对账方案，再回退应用和数据库；不能直接恢复旧备份丢弃新报名、账号或消息。

备份恢复不撤销已发生的外部通知、CRM 写入或其他副作用；按稳定请求 ID 和业务回执对账，需要时人工补偿。记录失败原因、已完成迁移步骤和恢复结果后，再决定重试范围。

### 客户研判条件迁移

研判五表按本章空库／有数据分流原则处理：先盘点对象和数据，无同名对象时使用核对后的增量建表，已有对象则比对后增量对齐。跨副本逐实体映射，手机号token只作候选；回滚保留新增业务数据及可恢复备份。未冻结的具体映射与副作用核对见第十八章第073项。

### 智能报告增量结构、种子与回滚

来源 `cyl合并后.md` 第六章方案如下；“三表全新/纯增量”是前提，必须先盘点实际目标库。

| 情况 | 处理 |
| --- | --- |
| 公共账号 + 客服表（已有） | 保留现有数据与约束；目标有数据时用备份 + 差异报告 + 增量迁移，禁止直接执行含 DROP/重建的 all.sql |
| 报告三张专属表（全新） | **纯增量**：补建 `report_config` / `report_record` / `report_metric` + 五条配置种子；无存量数据搬迁，上游源表结构不变、数据不动 |
| 权限收敛 | 属授权配置/代码变更：平台admin及有效manager按精确动作和范围计算，与公共鉴权统一发布；报告范围承载若需结构变化则另行评审，不假定必然无需表迁移 |
| 空目标库 | 可用核对后的 all.sql 建表 + 必要种子；有数据的库不得全量重建 |
| 身份/外键映射 | 账号、员工、客户、学生分别按可靠业务标识去重并建立主键映射，不简单加 ID 偏移；客服 `session_id` 碰撞需同步更新消息引用 |
| 回滚 | 切换前失败恢复已验证备份；切换后先停写、记录增量再回退，不回滚已发生的外部通知/CRM 写入 |

补充限制：目标若已有报告表、配置或历史报告，先比较实际结构与数据，再制定增量方案，不直接重跑初始化或覆盖五条种子。`init_report_tables.py` 内容未读取，不将其当作安全迁移工具。跨副本迁移还须处理 report_config 的业务编码、report_record 的配置外键/幂等键、report_metric 的记录外键以及已有研判实体映射。

回退先停止相关调度/生成写入，保存切换后的报告、指标、配置及外部调用记录，再按备份和增量对账恢复；不能因为报告只读上游就认为没有自身新增业务数据或外部模型副作用。权限收紧虽然不改表，仍需与代码/前端同步发布和回退。

### 请假单表、共享外键与任务迁移的条件

来源企业E2.4、E10、附录A.16与联合B.3规定：只在核实旧student_leave_request数据或调用方存在时做迁移/版本适配，不默认建第二张事实表或双写。旧ID到student_admin_service.id单独映射，转换submitted/withdrawn→pending/cancelled，指定审批人与实际决策人分别保留，通知/审计引用同步映射；缺失实际审批历史应明确缺失，不能用当前reviewer_id猜测。

共有15表与学生7表均先盘点已有对象，不全量重建；按B.3顺序处理部门/员工循环、可空负责人、三个复合FK和目标UNIQUE。不能关闭外键检查写入0占位/孤儿数据，不能按姓名或统一ID偏移合并。所有新增约束、列精度、会话排序规则、crm_student_id唯一性均要比较实际差异后增量实施。

停写和回滚除保存业务增量外，还需处理任务租约、已投递消息、提醒设置代次和外部CRM/教务未知回执；恢复旧库不能撤销已发通知或外部写入。配置更新、客户端切换和源代码版本配套回退。来源初始化/本地MySQL/演示账号脚本仅为路径线索，本次不执行。


## 十五、向后兼容与可选联动

### 1. 兼容性要求

| 项目 | 保留规则 | 必须核验 |
| --- | --- | --- |
| 公共三个接口 | 已用路径、登录返回和当前账号语义 | 错误格式若统一改变需更新调用方，不宣称现有行为已自动变化 |
| 客服六个接口 | 请求/响应字段、匿名开放与已有动作语义 | 现有前端不带 JWT 仍可咨询和报名 |
| JWT | 目标身份不混淆，旧凭据处理有明确策略 | 密钥/算法/有效期和用户 ID 映射；不能仅靠共享密钥保证旧 Token 正确 |
| Dify | 公共传输接口与客服场景结果契约兼容 | 实际 DSL、模型/知识绑定、应用 Key、输出字段及目标部署版本 |
| 数据库 | 保留字段含义、状态、唯一键与关系 | 存量数据、时间精度和时区；源文件描述不足时先核实 |
| 其他模块 | 保留有效实现和已有公共调用 | 按其交付状态挂载，不因两模块合并删掉已有能力 |

### 2. 可选功能增强（不作为现有能力）

| 增强点 | 前提及设计约束 | 处理方式 |
| --- | --- | --- |
| 公开对话可选识别登录用户 | 保持匿名功能；有效 JWT 只能建立经服务端核验的关联，不信任前端 user_id | 需先约定访客与账号的独立映射方式，不直接覆盖历史 chat_session.user_id；无效 Token 不附带已登录身份或读取账号私密信息 |
| 报名留资成为客户线索 | 需明确收集用途、负责人、客户归属、字段映射及幂等 | 调共享客户创建/匹配服务，以 source_reference 追溯报名；电话 token 仅用于受控匹配及候选提示，不自动把所有同号客户合并 |
| 报名审计 | 受控操作者标识、稳定业务事件和重试规则明确 | 可复用 operation_log，但不能把匿名访客伪装成员工/学生；现有审计操作者约束不适配时须先设计真实服务/访客记账方案 |
| 报名通知顾问 | 顾问分派和事件归属已确定，通知表/发送器契约一致 | 使用稳定去重键；本地报名、线索、审计及通知事实按明确事务/异步事件边界处理，不重复消费 |
| 将公开报名改为受保护接口 | 属于访问规则变更，需产品明确选择及前端兼容方案 | customer 下已有 event_signup.create，不代表 visitor 已被定义或获得权限；若引入 visitor，须新增可信身份/凭据及明确授权，不能只挂 require_permission 就宣称支持 |

以上增强逐项确定范围后实施，本次文档完善不自动启用。后续代码合并优先完成既有功能和已确定公共契约，建议联动与当前可运行功能分开验收。

### 客户研判兼容性与注意事项（扩展）

| 项目 | 保留规则 | 必须核验 |
| --- | --- | --- |
| 公共三个接口 | 路径、登录返回、当前账号语义不变 | 错误格式若统一改变需同步调用方 |
| 客服六个接口 | 请求/响应字段、匿名开放、动作语义不变 | 现有前端不带 JWT 仍可咨询和报名 |
| `user_account` 及关联表 | identity_type、CHECK、唯一键、外键不变 | 不新增身份取值；客户研判权限走 YAML + role_codes |
| 客服六表 | 字段、索引、外键、状态式去重不变 | `event_signup` 不引入新唯一约束 |
| JWT | 算法、密钥、有效期、sub 账号映射不变 | 旧 Token 语义不因新增权限改变 |
| Dify | 公共 HTTP 工具契约、客服场景结果契约不变 | 客户研判抽取为独立应用/Key，不影响客服应用 |

研判固定规则、联系方式保护、匿名边界及产品／课程独立等现行规则见对应业务章节；剩余字段冻结、资产交付和真实兼容核验统一见第十八章。

### 报告兼容性与注意事项

- 公共三接口（登录 / 公开清单 / 当前权限）路径与返回不变。
- 客服六接口继续匿名开放，不带 JWT 仍可咨询与报名，请求/响应字段与已用前端兼容。
- 报告五接口维持异步生成 + 幂等语义；`report.*` 权限收紧不破坏已生成报告数据，但若已有前端调用需核对鉴权切换。
- 已签发 JWT 兼容性取决于签名密钥、算法与 user_id 映射；若 user_id 变化，旧 Token 的 sub 可能指错账号，需重新登录或受控过渡。

#### 来源注意事项

1. **公开与受保护边界**：客服匿名；报告仅平台管理员和有效部门主管可访问，动作及范围按第二章。不向全体员工开放，不因客服匿名而公开报告。
2. **页面可见性 ≠ 接口授权**：后端五报告路由仍须逐个挂 `require_permission`，不能只靠前端隐藏。
3. **报告只读上游**：报告模块不建上游表 ORM、不回写，只按 `all.sql` 列名用固定 SQL 读，避免跨模块越权定义。
4. **同名文件不覆盖**：`agent`/`report` 前缀文件与各 `README.md` 按完整相对路径区分。
5. **「已实现」不等于已验收**：报告路由鉴权、心理周报取数/脱敏、投诉口径、定时生成、客服 real 链路、报名行锁等状态以核对结果为准，不沿用其它工作副本的「已实现」结论。
6. **真实值不入文档**：数据库口令、JWT 密钥、Dify API Key 只写配置名，不写真实值。

合并限制：从全体employee的旧report.read收紧为平台管理员与有效部门主管的精确动作/范围，是授权行为变更，不能仅凭接口响应未变声称完全兼容；本轮未改真实配置或代码。五报告接口中的异步/幂等语义为来源设计，实际能力待核验。报告只读上游不等于可跨越业务数据范围，管理员也需遵守已确认的心理报告聚合与输出范围。

### 企业学生兼容性与既有模块边界

开发目标以统一公共JWT与单表契约为准，但只有确认没有真实旧调用方/数据后，才能不做兼容；若存在，按已定版本逐项字段/状态/主键映射，不能直接用新状态覆盖旧响应或把旧ID误指新记录。旧学生actor_type/actor_id自签登录令牌不再作为目标人员认证，STUDENT_ACTION_SECRET仅用于业务确认/会话，不能充当JWT密钥。

企业与学生HTTP200信封、幂等键、分页、确认Token和通知可读策略仅为对应目标接口，不能追溯宣称公共及其他模块已经实现，也不能无授权地改变客服匿名契约。企业新独立NL2SQL不强制替换旧场景客户端，学生group预留适配不等于公共模块已提供student-v1服务。跨模块主档电话加密和匹配密钥必须统一受控升级。


## 十六、企业与学生联合协作契约 V1（来源附录B完整合并）

来源两份附录B逐字一致，以下完整保留一份正文（230行来源含章标题；共同契约归一SHA-256：`4f47a4cafb8176241e6aa85255b1fd72008119fe4f5c78ed6ecff3f966f6d73b`）。本章是开发目标，不是已实施的全局公共规则；文中的“本轮”“同目录”等指原来源，实际执行范围及冲突以本主文档前文说明为准。

> 版本：enterprise-student-v1；日期：2026-10-16；状态：开发目标，全部待测试。  
> 本附录在同目录 jlj.md 与 msj.md 保持逐字一致。正文为各模块功能说明，共享结构与接口以本附录为准；修改本附录必须同时修改两份文档。本轮仅对齐文档，不证明代码或数据库已实现这些约束。

### B.1 唯一职责与运行入口

| 能力 | 唯一维护方与入口 | 另一方如何配合 |
| --- | --- | --- |
| 公共登录、账号、JWT、公共权限 | 公共能力；人员请求复用 get_current_account | 不复制签发/验票逻辑，不信任前端身份字段 |
| 学生请假四个方法 | 学生维护 app/api/student_leave.py | 企业不重复注册 /api/v1/student/leave |
| 老师请假、预警、学生通知 10 个方法及同步 3 个方法 | 学生维护 app/api/student.py | 企业开发工作台和调用编排，不创建重复 enterprise_student 路由 |
| 请假固定服务 | 学生维护 StudentLeaveService 与 student_leave_repository.py | 学生聊天、企业表单/对话均委托；同进程直接调用，跨进程走既定 API |
| 投诉学生动作 | 学生维护提交、补充、确认、重开、评价 | 不实现企业分派/处理逻辑；公共表与状态不另起副本 |
| 投诉企业动作 | 企业维护分派、跟进、给方案的 enterprise_ticket 固定服务 | 学生读取同一 service_ticket 与 service_ticket_record |
| 共享表结构与初始化 | 双方按本附录形成唯一公共迁移；公共 ORM 元数据不重复声明 | 模块不得各自建同义事实表、重建公共数据或自动建表 |
| 通知生产与投递 | 业务动作所属固定服务生产；学生任务只消费 student.，企业任务只消费 enterprise. | 企业服务可为学生收件人生产 student. 事件，但不能由两个任务同时投递 |

人员与模型都不能直接提交 SQL 写库。普通模型只提取受控动作及字段，固定服务验证权限、状态、版本并写入；NL2SQL 仅在企业受控只读查询使用。学生 local 查询为固定查询，group 模式 student-v1 需要单独响应适配，不把 SQL 模板当作业务数据。

### B.2 主键、字段类型与别名

全部数字主键及对应外键统一为有符号 BIGINT，不混用 UNSIGNED、字符串、员工工号或外部 ID。普通数据库类型可在 ORM 中表现为 Integer/BigInteger，但目标 MySQL 列类型必须匹配。唯一例外是会话键：两端 session_id 均为 VARCHAR(64)、utf8mb4、utf8mb4_bin。

| 表名 | 物理主键 | 主键类型 |
| --- | --- | --- |
| `user_account` | `user_id` | BIGINT，自增 |
| `org_department` | `department_id` | BIGINT，自增 |
| `employee` | `employee_id` | BIGINT，自增 |
| `customer_profile` | `customer_id` | BIGINT，自增 |
| `customer_followup` | `followup_id` | BIGINT，自增 |
| `employee_daily_report` | `daily_report_id` | BIGINT，自增 |
| `student_profile` | `student_id` | BIGINT，自增 |
| `student_staff_binding` | `binding_id` | BIGINT，自增 |
| `student_score` | `score_id` | BIGINT，自增 |
| `student_admin_service` | `id` | BIGINT，自增 |
| `service_ticket` | `ticket_id` | BIGINT，自增 |
| `service_ticket_record` | `ticket_record_id` | BIGINT，自增 |
| `knowledge_entry` | `knowledge_id` | BIGINT，自增 |
| `business_notification` | `notification_id` | BIGINT，自增 |
| `operation_log` | `operation_log_id` | BIGINT，自增 |
| `mental_health_profile` | `id` | BIGINT，自增 |
| `mental_warning` | `id` | BIGINT，自增 |
| `student_academic_event` | `id` | BIGINT，自增 |
| `student_academic_reminder` | `id` | BIGINT，自增 |
| `student_application_progress` | `id` | BIGINT，自增 |
| `student_assistant_session` | `session_id` | VARCHAR(64)，非自增 |
| `student_assistant_turn` | `id` | BIGINT，自增 |

目标共 22 张企业/公共/学生关联表；course_project 是额外只读项目依赖，不与上述学生表建立 FK，不纳入本附录建表职责。API 别名不更改物理主键：

| API 或动作字段 | 唯一对应字段/转换 |
| --- | --- |
| apply_id | student_admin_service.id；不能映射到已停用的 leave_request_id |
| warning_id | mental_warning.id；预警 API 的 row_version 对应物理 version |
| academic_event_id | student_academic_event.id；提醒表同名列是引用字段，不是节点表主键名 |
| reminder_id | student_academic_reminder.id |
| ticket_id / notification_id | service_ticket.ticket_id / business_notification.notification_id |
| student_id / employee_id | student_profile.student_id / employee.employee_id；不等同于 user_account.user_id |
| leave_content | 提交请求转为 student_admin_service.apply_content；详情/查询统一输出 apply_content |
| leave_type | 提交后存 edu_related_data.leave_type，响应仅投影该受控键，不输出完整内部 JSON |
| decision / comment | decision=approved/rejected 转 approval_status；comment 转 approval_comment；reviewed_at 取服务端时间 |
| complaint_content / feedback_type | 学生模型动作字段，先转 HTTP/服务参数 content / ticket_type，再写 service_ticket 同名列 |
| expected_version | 请求条件；请假/工单比对 row_version，预警比对 version；API 统一使用 row_version 表示业务版本 |

student_profile.external_student_id 是教务外部编号，crm_student_id 是 CRM 外部编号，均为可空 VARCHAR(128)，非空值分别唯一。它们不是本地外键，外部同步先按可信映射定位内部 student_id，不按姓名匹配。

### B.3 目标物理外键完整关联清单

下表全部是目标物理 FK，不是“已建立”声明。来源列与目标列依 B.2 同型；可空列仅在非 NULL 时检查。全部 ON DELETE RESTRICT / ON UPDATE RESTRICT，业务采用作废、停用或归档，禁止级联删除历史。

| 编号 | 来源表及引用字段 | 目标表及被引用字段 |
| --- | --- | --- |
| FK01 | `user_account.employee_id` | `employee.employee_id` |
| FK02 | `user_account.customer_id` | `customer_profile.customer_id` |
| FK03 | `user_account.student_id` | `student_profile.student_id` |
| FK04 | `org_department.parent_department_id` | `org_department.department_id` |
| FK05 | `org_department.employee_id` | `employee.employee_id` |
| FK06 | `employee.department_id` | `org_department.department_id` |
| FK07 | `customer_profile.employee_id` | `employee.employee_id` |
| FK08 | `customer_profile.department_id` | `org_department.department_id` |
| FK09 | `customer_followup.customer_id` | `customer_profile.customer_id` |
| FK10 | `customer_followup.employee_id` | `employee.employee_id` |
| FK11 | `employee_daily_report.employee_id` | `employee.employee_id` |
| FK12 | `employee_daily_report.department_id_at_submit` | `org_department.department_id` |
| FK13 | `student_profile.customer_id` | `customer_profile.customer_id` |
| FK14 | `student_profile.department_id` | `org_department.department_id` |
| FK15 | `student_staff_binding.student_id` | `student_profile.student_id` |
| FK16 | `student_staff_binding.employee_id` | `employee.employee_id` |
| FK17 | `student_score.student_id` | `student_profile.student_id` |
| FK18 | `student_score.employee_id` | `employee.employee_id` |
| FK19 | `student_admin_service.student_id` | `student_profile.student_id` |
| FK20 | `student_admin_service.reviewer_id` | `employee.employee_id` |
| FK21 | `service_ticket.student_id` | `student_profile.student_id` |
| FK22 | `service_ticket.employee_id` | `employee.employee_id` |
| FK23 | `service_ticket.handling_department_id` | `org_department.department_id` |
| FK24 | `service_ticket_record.ticket_id` | `service_ticket.ticket_id` |
| FK25 | `service_ticket_record.student_id` | `student_profile.student_id` |
| FK26 | `service_ticket_record.employee_id` | `employee.employee_id` |
| FK27 | `knowledge_entry.employee_id` | `employee.employee_id` |
| FK28 | `knowledge_entry.reviewer_employee_id` | `employee.employee_id` |
| FK29 | `knowledge_entry.access_department_id` | `org_department.department_id` |
| FK30 | `business_notification.employee_id` | `employee.employee_id` |
| FK31 | `business_notification.student_id` | `student_profile.student_id` |
| FK32 | `operation_log.employee_id` | `employee.employee_id` |
| FK33 | `operation_log.student_id` | `student_profile.student_id` |
| FK34 | `mental_health_profile.student_id` | `student_profile.student_id` |
| FK35 | `mental_warning.student_id` | `student_profile.student_id` |
| FK36 | `mental_warning.follower_id` | `employee.employee_id` |
| FK37 | `student_academic_event.student_id` | `student_profile.student_id` |
| FK38 | `student_application_progress.student_id` | `student_profile.student_id` |
| FK39 | `student_assistant_session.student_id` | `student_profile.student_id` |
| FK40 | `student_assistant_turn.student_id` | `student_profile.student_id` |
| FK41 | `mental_warning.(profile_id, student_id)` | `mental_health_profile.(id, student_id)` |
| FK42 | `student_academic_reminder.(academic_event_id, student_id)` | `student_academic_event.(id, student_id)` |
| FK43 | `student_assistant_turn.(session_id, student_id)` | `student_assistant_session.(session_id, student_id)` |

约束落地要求：

- reviewer_id、部门主管 employee_id 均为可空物理 FK；未分派/未设置时用 NULL，不用 0 或不存在的员工 ID。实际审批人保存在 operation_log.employee_id，不能用后来变更的 reviewer_id 推断历史。
- 复合 FK 必须有目标 UNIQUE：mental_health_profile(id, student_id)、student_academic_event(id, student_id)、student_assistant_session(session_id, student_id)。对应来源按同样顺序建索引；外键列类型、会话字符集和排序规则逐一一致。
- student_academic_reminder.student_id 通过复合 FK 传递关联学生，不另建直连学生表 FK；学生会话轮次同时有直接学生 FK 和复合会话 FK，确保不能把甲学生的消息挂在乙学生会话下。
- 业务唯一键至少包括：user_account 的 username 及三个身份外键分别唯一；日报(employee_id, report_date)；成绩(student_id, course_code, term_code, assessment_code, attempt_no)；请假(student_id, request_key)；工单 ticket_no；处理记录 record_key；通知 dedupe_key；审计 operation_key；聊天轮次(student_id, request_key)；提醒(student_id, academic_event_id, lead_minutes)。外部镜像分别按(student_id, source_system, external_event_id)和(student_id, source_system, external_application_id, stage_code)去重。
- 表创建顺序：先 org_department（主管列留 NULL），再 employee；双方表存在后建立主管回指 FK，再设置主管。其余先建被引用表，再建子表及复合约束；引用前校验记录存在，不关闭外键检查写入孤儿数据。初始化先有组织、员工、学生，再有账号/绑定/业务记录。
- 同一学生只能有一个当前有效主班主任。绑定新增、停用、主负责人切换与审批并发时锁定相同学生主记录并复核绑定；不能用 UNIQUE(student_id,is_primary) 误阻止多条非主关系。
- user_account 一个账号只对应一种 identity_type；employee/customer/student 分别只填写对应外键，admin 三类外键为空。service_code 是受控系统身份字符串，不是员工 FK。
- business_notification 接收人 employee_id/student_id 二选一；operation_log 与 service_ticket_record 的 employee_id/student_id/service_code 三选一。service_ticket_record.student_id 表示学生操作者且必须等于工单所属学生，不是任意抄写对象 ID。
- business_notification 和 operation_log 的 entity_type+entity_id 是逻辑多态引用，无法声明跨多表 FK。类型仅允许受控业务映射：student_admin_service→id、service_ticket→ticket_id、mental_warning→id、student_academic_reminder→id，以及企业已登记的数字主键实体；固定服务在同事务核验。会话字符串 ID 不写入 BIGINT entity_id。

### B.4 身份、权限、配置和统一返回

人员 Authorization: Bearer <公共JWT>，固定经 JWT.sub→user_account.user_id→业务外键定位。有效 JWT 后仍检查 employee.status=active、有效部门、role_codes、有效绑定、记录负责人和对象版本。老师审批必须具有 teacher、class_teacher 有效绑定且 reviewer_id 为本人；预警同理要求 follower_id 为本人。主管或系统管理员身份不自动获得审批或心理原文权限。

| 主体/功能组 | 目标公共权限 | 额外数据范围 |
| --- | --- | --- |
| 学生请假 | student.admin_service.create、student.admin_service.read_own、student.admin_service.withdraw_own | 本人学生档案与本人申请 |
| 学生工单 | service_ticket.create、service_ticket.read_own、student.ticket.reply_own、student.ticket.confirm_own、student.ticket.rate_own | 仅本人；只读 student_visible 沟通 |
| 学生心理/学业/提醒/进度 | student.mental.create_own、student.academic.read_own、student.reminder.manage_own、student.progress.read_own | 仅本人；不获得人工预警内部备注 |
| 学生通知/智能体 | student.notification.read_own、student.chat、student.action.confirm | 本人通知、会话及确认凭证 |
| 老师请假/心理/通知 | student.admin_service.review、student.warning.read、student.warning.handle、student.notification.read | 有效 teacher 和对应班主任/负责人关系；通知仅本人接收 |
| 企业工单 | enterprise.ticket.read、enterprise.ticket.assign、enterprise.ticket.handle | manager 限本部门分派，teacher 限有 class_teacher/service_advisor 关系且为当前处理人 |
| 上架项目只读 | course_project.read | 仅已上架项目，不授予报名/订单写权限 |

身份权限在 access_control.yaml 显式配置，细粒度角色与范围由所属模块固定服务检查。同步接口不用个人 JWT，统一校验 Bearer STUDENT_SYNC_TOKEN，映射 service_code=student_sync、scopes=[student:sync]；缺失/错误返回 code=401，身份有效但缺 scope 返回403，不降级成学生/老师身份。

所有学生、老师和企业业务方法统一 HTTP 200 + {code,message,data}；0 成功，400 参数，401 身份，403 动作权限，404 对象不可见/不存在，409 状态/版本/幂等冲突，500 内部错误，503 依赖不可用。公共登录维持公共约定；网络/代理失败仍须处理非200。列表 limit=1..100、offset≥0，返回 items/total/limit/offset，total 同样限定权限范围。

写入、聊天、确认均带 Idempotency-Key（8～128位可见ASCII）；真实操作者+动作+原始请求键计算 operation_key，同参数重试回放回执，不同参数409。已有数值版本业务对象修改带 expected_version；提醒使用 B.7 的 expected_event_version + expected_updated_at，会话并发使用后端 conversation_token 绑定的 session.version；通知已读例外。回放前重验当前身份/范围，不因重复请求再次调用模型或投递通知。

所有运行密钥只从 StuProject/.env 经 app/config.py 加载。学生专用配置也在此声明：DIFY_API_BASE、DIFY_API_TIMEOUT_SECONDS、STUDENT_DIFY_KEY、STUDENT_SYNC_TOKEN、STUDENT_ACTION_SECRET、STUDENT_QUERY_BACKEND、STUDENT_KNOWLEDGE_FILE 和需要的教务/CRM/通知适配配置；企业保留 ENTERPRISE_* 应用 Key。STUDENT_ACTION_SECRET 只签业务确认/会话凭证，不替代登录 JWT。停止另行加载 .env.student.local、STUDENT_DIFY_BASE；模块辅助配置可以做类型分组，但不能维护第二套加载来源。Dify 全部通过 app/core/dify.py；学生一个应用、企业多个应用使用各自 Key。运行配置不提交，.env.example 只有占位值。

### B.5 请假与预警对接字段及固定服务

学生模块唯一注册学生请假 POST/GET /api/v1/student/leave、GET/DELETE /api/v1/student/leave/{apply_id}；老师三方法为 GET /api/v1/internal/student/leave、GET /api/v1/internal/student/leave/{apply_id}、POST /api/v1/internal/student/leave/{apply_id}/decision。

- 提交字段为 leave_content、leave_type、leave_start_at、leave_end_at，可选 generate_ai_summary。服务绑定本人 student_id、apply_type=leave、approval_status=pending，按有效主班主任设置 reviewer_id；缺老师时保存 NULL 并标记待分派，不授权任意老师领取。
- 两侧列表筛选均为 approval_status=pending/approved/rejected/cancelled，可省略；永远限定 apply_type=leave。详情统一 data 字段：apply_id、student_id、apply_type、apply_content、leave_type、approval_status、leave_start_at、leave_end_at、reviewer_id、reviewed_at、approval_comment、row_version、created_at、updated_at；未审批的结果列允许 NULL，不输出 request_hash 或全量 edu_related_data。
- 老师审批 body 为 expected_version、decision、comment；decision=approved/rejected，驳回意见必填，最多2000字。固定条件包含 id、apply_type、reviewer_id、pending、row_version，更新影响一行才成功；版本加一，同时写 reviewed_at、approval_comment、实际员工审计和学生结果通知。
- 成功 data 返回 apply_id、approval_status、row_version、reviewed_at、reviewer_id。学生撤回仅本人 pending→cancelled，审批仅 pending→approved/rejected，撤回和审批使用同一并发保护；终态不能再审批。
- 学生持有待分派申请也可查本人记录，老师只读本人指定且班主任关系有效的申请。申请实际审批员工取成功审计，不新增或使用 decision_employee_id 替代审计。
- 预警 API 统一返回 warning_id、student_id、follower_id、follower_status、row_version 及授权允许字段，warning_id=id、row_version=version。ack 将 pending→processing，follow 保持 processing，close 仅 processing→closed 且已接手、有处理结果。三个动作均带 expected_version、note（必填，最多2000字），不得向学生普通查询输出风险依据/人工备注。

### B.6 投诉工单跨模块状态与事务

学生 HTTP 提交 content、ticket_type=complaint/suggestion、category_code；所属 student_id 来自身份，handling_department_id 来自学生归属部门，企业服务不得相信请求自行改变归属。字段缺失或无法确定有效部门时返回错误，不造外键 ID。

| 动作/负责方 | 允许前态 | 后态及必要字段 |
| --- | --- | --- |
| 学生提交 | 无 | open；employee_id=NULL、reopen_count=0，设 response_due_at/resolution_due_at，追加创建记录 |
| 企业主管分派 | open/reopened/assigned/processing | 分派有效同部门 teacher 且有该学生服务关系，设 employee_id，转 assigned；保留审计，不重置已有首次回应 |
| 企业老师跟进 | assigned/processing | processing，追加处理记录；只有实际学生可见人工回应才首次设置 first_response_at，内部备注不算 |
| 企业老师给方案 | assigned/processing | awaiting_student；solution必填、resolved_at=服务端时间，追加 student_visible 解决记录 |
| 学生确认已解决 | awaiting_student | closed；closed_at=服务端时间，学生不能代写企业方案 |
| 学生确认未解决 | awaiting_student | reopened；原因必填，reopen_count+1，清空当前 solution/resolved_at/closed_at，重算本轮期限并提示重新分派 |
| 学生补充 | open/assigned/processing/awaiting_student/reopened | 状态不变，追加 student_visible 回复；不能通过补充接口关闭或重开 |
| 学生评价 | closed | 状态不变，satisfaction_score=1..5，版本校验并审计 |

工单请求字段统一如下，所有请求还携带幂等头：

| 方法与路径 | body 字段 |
| --- | --- |
| POST /api/v1/enterprise/tickets/{ticket_id}/assign | expected_version、employee_id、reason；目标老师同处理部门并有有效 class_teacher/service_advisor 关系 |
| POST /api/v1/enterprise/tickets/{ticket_id}/followups | expected_version、content、visibility；visibility 只允许当前动作政策允许的 internal/student_visible |
| POST /api/v1/enterprise/tickets/{ticket_id}/resolve | expected_version、solution；服务强制学生可见，不接受代学生关闭 |
| POST /api/v1/student/tickets/{ticket_id}/reply | expected_version、content；服务强制 student_visible |
| POST /api/v1/student/tickets/{ticket_id}/confirm | expected_version、resolved（布尔）、comment；resolved=false 时 comment 必填 |
| POST /api/v1/student/tickets/{ticket_id}/rating | expected_version、satisfaction_score（1..5） |

所有修改校验权限/状态/expected_version，row_version+1。service_ticket_record.cycle_no=reopen_count+1，to_status 取动作后真实状态，record_key 由已核验的操作生成；可见性 internal/student_visible 由动作策略决定，学生只能创建/读取 student_visible。企业与学生写服务共用同一行锁/条件更新策略。

每个动作的工单更新、必要记录、实际操作者审计、通知与幂等回执同事务；失败整体回滚。学生确认不能设置处理人，企业不能代学生确认、重开或评价。详情/列表返回 ticket_id、student_id、ticket_type、category_code、content、status、employee_id、handling_department_id、solution、resolved_at、closed_at、reopen_count、satisfaction_score、row_version 及所需受控时间字段；学生记录接口以 visibility 过滤，禁止全量透传内部快照。

### B.7 通知引用、事件命名与提醒代次

业务服务按下表生产事件，投递任务只按 event_code 前缀分工，事件生产方与投递方可以不同：

| event_code | entity_type / entity_id | 接收人/生产方 | 唯一投递任务 |
| --- | --- | --- | --- |
| student.leave.submitted | student_admin_service / id | 指定老师 / 学生请假服务；未分派时延后生成 | StudentTasks |
| student.leave.approved / student.leave.rejected | student_admin_service / id | 申请学生 / 唯一请假审批服务 | StudentTasks |
| student.leave.cancelled | student_admin_service / id | 如有指定老师 / 学生撤回服务 | StudentTasks |
| enterprise.ticket.assigned | service_ticket / ticket_id | 新处理员工 / 企业分派服务 | EnterpriseTasks |
| student.ticket.reply | service_ticket / ticket_id | 学生 / 企业实际学生可见人工回复服务 | StudentTasks |
| student.ticket.awaiting_student | service_ticket / ticket_id | 学生 / 企业给方案服务 | StudentTasks |
| student.ticket.closed / student.ticket.reopened | service_ticket / ticket_id | 如有当前处理员工 / 学生确认服务 | StudentTasks |
| student.warning.created | mental_warning / id | 指定处理老师 / 学生预警服务 | StudentTasks |
| student.academic.reminder | student_academic_reminder / id | 提醒所属学生 / 学生提醒服务 | StudentTasks |

普通去重键由 event_code、entity_type、entity_id、变更后业务版本、recipient_type、recipient_id、channel 组成，后端生成且不超过 dedupe_key 的160字符；超长时对规范化元组做SHA-256摘要并保留事件前缀。同一事件/版本/接收人/渠道只入队一次。实体是工单时填 ticket_id、是申请时填申请 id，不填 student_id 冒充业务对象 ID。

提醒表无 row_version，不增加同义字段：以 event_version + updated_at(DATETIME(6)，UTC) 作为设置代次，仅设置/取消/节点重排更新该时间；投递状态、租约和重试不能改变设置代次。恢复/修改已有提醒及 DELETE 取消请求携带 expected_event_version 和 expected_updated_at（UTC、保留6位微秒），服务在事务内条件匹配；首次创建无旧代次，以提醒业务唯一键处理并发创建，冲突返回409。提醒通知 dedupe_key 中的“业务版本”替换为该代次，发送前重新构造当前键对比，并检查节点版本、有效状态与提醒未取消；旧代次消息不标记新代次已发送。节点表改期/取消递增 event_version 并重排任务。

站内通知仅对应收件人且delivery_status=sent时可读；本期sent表示通过有效收件人检查、成功发布为个人页可查询，浏览器在线或打开不是前提，read_at独立记录。业务变更与入队同事务，站内发布租约/重试独立处理；发布失败不重复审批，不将pending入队视作可读。所有查询/未读数/已读接口限定当前登录本人，不接外部渠道。

### B.8 联合验收（以下全部待执行）

| 检查项 | 通过条件 |
| --- | --- |
| 元数据与真实 DDL | 22张表的目标主键、43条FK、类型/符号位、session字符集/排序规则和三个组合UNIQUE逐项一致；不存在指向非唯一列的FK |
| 外键数据 | 无孤儿记录；跨学生评估/提醒/会话关联被复合FK拒绝；可空负责人不使用0占位 |
| 路由与服务 | 每个方法+路径只注册一次；只有一个请假服务；企业调用目标与学生响应字段一致 |
| 身份与范围 | 公共JWT、老师角色/绑定/负责人、学生本人范围、同步凭据均按契约；跨用户/跨部门和错凭据拒绝 |
| 请假闭环 | 同一申请学生提交→老师审批→学生查结果；撤回/审批竞态只有一方成功；状态、版本、审计、结果通知一致 |
| 投诉闭环 | 同一工单分派→回应→给方案→学生确认/重开/评价；状态/轮次/可见性/接收人正确 |
| 幂等与事务 | 重试不重复业务/审计/消息，同键不同参数409；模拟中途失败不留下半条业务 |
| 通知与提醒 | student./enterprise.不重复领取，实体ID与目标表相符；旧代次不发送/不覆盖新提醒，外部回执明确 |
| 配置与模型 | 只从根.env加载，独立应用Key，统一HTTP传输；模型超时/缺字段不写库，SQL生成仅用于授权只读查询 |
| 联合状态 | 两侧字段/角色/状态表及本附录逐字一致；完成真实数据库、接口与页面联调后才能标记“已落地” |

文档一致性检查只能证明契约在文字层面对齐；真实物理约束、接口可调用及业务闭环必须在编码后按上述清单验证。

## 十七、六模块功能完整性与联动性审查

审查日期：2026-10-16；整理日期：2026-10-17。六模块主要功能及企业／学生核心流程已有设计覆盖，尚不能认定全部功能与联动完整。账号开通、本地维护、学生查询、研判归属与历史、报告消费及异常接管等设计缺口已与历次问题按主题归并至文件末尾，不再另列D系列问题表或重复展开。

### 1. 已在文档层面衔接的核心链路

以下表示文字契约已明确，不代表实际服务、数据库、页面或任务已经运行通过。

| 链路 | 已明确的衔接内容 | 对应限制 |
| --- | --- | --- |
| 公共认证→受保护业务 | JWT.sub→真实user_account→业务外键；动作、角色与对象范围继续由固定服务校验 | 身份有效不等于拥有全部业务权限；客服六接口仍匿名公开。 |
| 学生请假→老师审批→学生结果 | 唯一student_admin_service事实表、apply_id映射、唯一StudentLeaveService、审批/撤回状态、版本及审计一致 | 无负责人及人员变动场景仍按第十八章第052项补齐。 |
| 学生投诉→企业处理→学生确认/重开/评价 | 共用service_ticket/service_ticket_record，双方按动作分工，企业不能代学生关闭或评价 | 时限及协作提醒仍按第十八章第054项补齐。 |
| 学业节点改期→提醒重排→站内发布 | 节点event_version、提醒设置代次、投递前复核、旧代次不覆盖新代次 | 本地节点的维护契约仍按第十八章第048项补齐。 |
| 业务变更→审计/通知入队→任务发布→本人读取 | 同事务保存业务与必要回执；按student./enterprise.前缀分工；sent、read_at和业务办结分开 | 发布成功不等于已读，已读不等于已经处理业务。 |
| 自然语言写动作→预览确认→固定服务 | 普通模型只提取动作和字段；确认时重验参数、权限、状态及版本，不再次调用模型 | 模型不生成可执行写SQL，不自行审批或发布。 |
| 自然语言只读查询→授权关系→AST校验→受限执行 | 企业独立通用NL2SQL契约，只读、行列授权、参数绑定和受限连接 | 不强制替换学生固定查询或报告固定指标SQL。 |

### 2. 可选联动与使用边界

- 客服报名→客户线索、研判来源→客户主档的自动或半自动转化，正文目前列为可选增强。未启用不能直接计为必需功能遗漏，也不能声称已形成完整获客转化链；若纳入范围，应补用途、确认、归属、候选匹配、幂等和事务约定。
- product与course_project当前默认独立，不强行补外键；若需要研判产品向课程推荐联动，应先明确映射业务规则，不能把同名/同类别视作可靠主外键关系。

## 十八、合并后的冲突与未确认事项

本章是全文唯一的问题清单，按主题去重后共74项，序号001—074。历次旧清单、状态复核和重复展开已移除；已确认的业务选择、已完成的文档勘误不再列项。

“待确认设计”表示规则或承载方式尚未冻结；“待实施核验”表示目标已明确，但仍有实现差距或缺少验证证据；条件性事项仅在启用对应能力或发现存量时适用。本文整理不代表已经修改代码、配置、DDL、数据库或部署服务。

### 001. 公共权限计算与员工动作授权

状态：待实施核验。

公共依赖目前按identity_type计算并精确匹配权限，不展开通配符，也未接通role_codes。access_control.yaml仍有全体employee的report.read、customer工单权限及平台admin权限缺项。需一并对齐配置、公共入口、模块动作和对象范围，明确依赖执行顺序，避免提前误拒主管或向全体员工放行；页面能力清单与接口校验须由同一服务端规则生成。

### 002. 员工角色注册、兼任与研判逐动作接入

状态：待设计／实施核验。

业务角色及研判、报告动作分配已有结论，不再询问。剩余工作是统一注册企业六类角色与analyst/reviewer，落实兼任时的逐动作范围计算，避免不同角色的数据范围和写能力任意拼接；按独立customer.judge.batch及规则读／维护分工对齐真实路由、YAML和服务。平台admin、员工admin和manager须分别验证，角色或部门变更实时生效。

### 003. 学生专用权限与旧customer工单授权对齐

状态：待实施核验。

需为学生目标接口显式接入工单、撤回、心理、聊天、确认等相应权限及受保护course_project.read，并撤销非学生customer的泛工单创建／读取能力。实际请求必须绑定本人student_id并校验对象归属；客服公开课程及六个匿名接口保持原契约。

### 004. 同步服务身份、scope与凭据管理

状态：待设计／实施核验。

未来启用外部同步时，STUDENT_SYNC_TOKEN须映射可信student:sync上下文，明确安全比较、最小scope、来源和学生范围、轮换及错误处理。三个同步来源共用静态凭据的隔离方式尚未冻结；个人JWT不能替代同步凭据，internal路径也不能匿名或在认证失败后降级。本地员工维护不以此服务身份替代人员授权。

### 005. 账号、主档与关系开通流程

状态：待确认设计。

需明确员工／学生主档、登录账号、角色及绑定分别由谁创建和维护，采用受控初始化还是管理功能，如何关联业务主键、配置有效关系、记录变更。应能从新员工／学生完成主档→账号→角色关系→授权入口，不由前端自报身份主键；不据此默认新增公开注册。

### 006. 报告公司级／部门级范围承载

状态：待确认设计／实施核验。

访问人群和动作已确定；仍缺生成参数或可信范围推导、持久化归属、各部门定时生成、范围与幂等／缓存关系，以及历史报告在人员调部门后的读取政策。取数、聚合、模型输入、记录、列表、详情与缓存必须保持同一范围，不能靠事后过滤元数据把公司报告变成部门报告；具体字段或范围模型尚未冻结。

### 007. 研判及报告操作者与审计承载

状态：待确认设计／实施核验。

研判三表created_by可空及外键／删除策略尚未冻结，需明确可信人员、历史记录与服务操作者的记账方式。报告人工和调度来源缺完整审计关联；共享operation_log的员工／学生／service_code三选一不能直接承载无employee_id的平台管理员。不得伪造员工或将真人管理员冒充服务，普通运行日志不能代替业务追溯。

### 008. 字符串会话与共享审计实体映射

状态：待确认设计。

共享operation_log.entity_id为BIGINT，客服访客和学生session_id可能是字符串，且访客不满足现有actor约束。若接入共用审计，需定义受控实体与操作者映射，不能强转会话ID或伪装访客为员工／服务；客服审计增强保持可选。

### 009. 统一错误信封与实际HTTP出口

状态：待设计／实施核验。

企业／学生采用HTTP200加业务code的目标尚未覆盖真实公共异常组件；其他模块存在实际HTTP状态和框架校验格式差异。需冻结适用路由范围，覆盖业务异常、HTTPException、Pydantic校验、鉴权、依赖失败及代理非200路径，并验证调用方；不得把业务401／403／409直接等同实际HTTP状态或自动改动其他模块协议。

### 010. 写入幂等、确认凭证期限及成功回放

状态：待确认设计／实施核验。

企业／学生8至128 ASCII幂等键、预览／会话签名与公共登录JWT的用途已有区分；仍需冻结凭证期限、签名绑定的账号／参数／版本／范围、过期后安全查询成功回执及重试窗口。企业建议5分钟不能作为所有模块定值；确认与回放都须重验身份和范围，不重复推理或执行。新契约不追溯施加给匿名客服。

### 011. 目标版本、真实路由与来源实现状态

状态：待核验。

以D:\AI\StuProject为基准后，仍需记录实际分支／提交或交付包校验、未提交改动及数据库版本，盘点唯一路由、Table、服务、DSL和真实依赖。allm、个人文档和联合方案的“已实现”“已提交”、79项回归或草稿导入不能互相证明本目录状态，需目标版本、OpenAPI及真实联合运行证据。

### 012. 真实表、接口与约束范围盘点

状态：待核验。

六模块36张直接相关规划表、企业学生22表／43条目标FK及历史11／14／16／19／31表属于不同范围，当前统计规则不再待确认。剩余工作是按实际对象核对已建表、接口操作、索引、FK、CHECK及ORM，不能由数量或目录宣称已落地，customer_judgement等额外缺失依赖须单列。

### 013. 共享账号／部门字段、排序规则与时间精度

状态：待设计／核验。

账号注释遗漏admin、ORM DateTime与DDL DATETIME(3)的差异仍需在实际版本对齐。企业目标把org_department.employee_id从逻辑引用改为可空物理FK，新增前须核对孤儿、字段类型及循环依赖；新摘要省略utf8mb4_bin不能据此改排序规则。customer_profile同为22字段不足以证明一致，需逐字段、类型、约束和唯一性对照。

### 014. 学生完整DDL与联合物理约束

状态：待冻结／实施核验。

学生七表73字段未给齐可空、默认、CHECK和索引；需冻结单一DDL／ORM，核对全部43条目标FK。预警、提醒、会话的三条复合FK须有顺序、类型、排序规则匹配的组合UNIQUE及索引，验证跨学生引用被拒绝。部门主管、审批人等物理FK是开发目标，不能用目标摘要覆盖旧约束或对36表全量重建。

### 015. JWT运行配置缺项

状态：待实施核验。

静态核对时AUTH_SECRET_KEY虽已声明，根.env及检查进程均未设置；签发要求至少32字节，AUTH_TOKEN_EXPIRE_MINUTES默认120。实施时须在本机生成专用随机值并验证加载、签发和解析，不复用Dify或业务签名密钥，不在文档／聊天记录真实值；其他运行进程是否注入仍须核实。

### 016. 旧NL2SQL配置属性缺失

状态：待实施核验。

旧客户端读取DIFY_NL2SQL_API_KEY／DIFY_NL2SQL_OUTPUT_KEY，Settings未声明，根.env仅有旧DIFY_API_KEY／DIFY_SQL_OUTPUT_KEY。访问未声明属性会阻断or回退，需补齐场景字段并核对旧契约；企业独立NL2SQL不得因此混用Key。

### 017. 学生统一应用及业务凭据配置迁移

状态：待实施核验。

Settings和StudentLeaveDifySettings均读根.env，但统一STUDENT_DIFY_KEY、STUDENT_ACTION_SECRET、STUDENT_SYNC_TOKEN及ENTERPRISE_CONFIRM_SECRET等尚未声明／配置。旧请假STUDENT_DIFY_LEAVE_KEY/TIMEOUT/VERSION及成绩STUDENT_SCORE_DIFY_BASE/KEY不能自动替换为统一应用。需按启用功能补齐配置与适配器、审查旧DSL／调用方迁移；不恢复第二登录或.env.student.local，不把配置示例当可运行系统。

### 018. Dify运行版本、应用发布与模型绑定

状态：待部署核验。

用户确认本地Dify为1.11.4、目录D:\docker\dify-1.11.4\docker，但Compose API／Web标签为1.12.1；当时Docker引擎不可达，运行态未核实。需核对实际镜像／版本及各业务应用导入、发布、Key、模型和知识绑定。根.env中报告Key非空不证明应用可用；报告来源deepseek-v4-pro只作为型号线索，供应商可用性与真实绑定须核验。

### 019. 各场景Dify输入输出协议及企业知识应用

状态：待冻结／交付核验。

QA／RAG单应用分支与一份ENTERPRISE_KNOWLEDGE_DIFY_API_KEY已确定；仍需整合两份来源DSL并验证输入输出、知识绑定和发布。学生／研判Schema及研判Workflow或Chat API尚未完整冻结，不能套用客服query、企业query_result或报告report_text。企业提取、只读SQL、知识、摘要等场景须分别交付适配器，公共HTTP只负责传输。

### 020. 数据库配置与只读连接隔离

状态：待实施核验。

根.env有DB_*，但Settings仍有可静默使用的硬编码密码默认值；企业ENTERPRISE_READ_DB_USER/PASSWORD未声明。需明确写库与受限只读连接、移除不安全默认并核对数据库实际授权。企业／报告须遵守行列范围及禁止回写，不能用无ORM、固定SQL或Prompt证明只读隔离。

### 021. 电话加密、检索token与密钥迁移

状态：待确认设计／实施核验。

企业新增ENTERPRISE_PHONE_ENCRYPTION_KEY／LOOKUP_SECRET目标尚未与主档／研判统一。需冻结电话标准化、算法、密钥版本、token计算和受控迁移／旧密文兼容方式，不得各模块生成不兼容检索值；无可靠明文时需保留隔离及待处理记录。

### 022. 原文、文件、邮箱及联系方式保护

状态：待确认设计。

结构化电话加密不覆盖customer_source.raw_content、原文件、customer_info.raw_fields和contact_email。需明确允许保存的原文／文件字段、脱敏或加密、访问授权、受控存储及保留期限；扩展字段仅保存必要白名单且不得绕过原文保护，日志不得输出完整原文。期限与原件保留策略仍未决定。

### 023. 研判产品到课程的可选映射

状态：待确认设计。

product与course_project保持独立的决定不再待问；若启用研判产品引导课程，仍需确认业务映射、产品编码／类别、未知或停用产品处理及接口筛选契约。当前课程接口只明确category，不可认定已支持产品筛选；新增外键须另行评审。

### 024. 研判文本／PDF／Excel接入与抽取交付

状态：待确认设计／交付核验。

需冻结上传请求类型、文件大小／格式、存储路径与读取授权、解析依赖及版本、输出字段、模型输入输出和失败处理；补齐extract_dify.py、可选DSL及配置契约。文件清单不能证明解析能力、应用或依赖已交付。

### 025. 未归并研判资料的顾问／部门归属

状态：待确认设计。

customer_info.customer_id可空，customer_source.created_by可能是analyst而非负责顾问。未归并时仍缺可信任务／顾问／部门范围及分派依据，需明确接入、解析、批量和读取授权，以及归并／转派后的范围变化；不能因归属不明默认全员可读或只按提交人充当业务负责人。

### 026. 重复解析、批量事务与部分失败

状态：待确认设计／实施核验。

反复解析可能产生多条customer_info；需明确覆盖或追加、批次和执行占位、失败状态、逐条提交边界、部分成功、重试及去重规则，并保留历史输入依据。公共get_db不负责自动提交，批量接口与单条重试不能造成重复有效结果。

### 027. 规则版本唯一性与并发生效发布

状态：待确认设计／实施核验。

规则有效期与is_active的共同判定已在正文明确；剩余是冻结不可变版本、(product_id,rule_version)唯一性、发布事务／锁及单产品单有效版本的并发保证。普通索引不足以唯一定位历史规则，简单唯一(product_id,is_active)会误限多个非生效历史版本；须验证无有效或多有效版本时停止正常裁决。

### 028. 实际产品规则、准入与评分验收

状态：待确认业务规则／核验。

关键字段缺失需补资料／人工复核，无有效规则、停用产品或规则格式错误不得生成正常命中／未命中，这些处理原则已有依据。仍需负责人提供实际产品准入规则、评分阈值、必要字段和样本，冻结规则版本并分别验收固定裁决与模型抽取质量；95%只是需求目标，不能据Prompt宣称达标或由模型猜结论。

### 029. 研判逐表时间精度与并发字段

状态：待确认设计／核验。

五表概述称统一DATETIME(3)、UTC及row_version，但customer_source／research_result未列row_version，规则有效时间为DATETIME。需逐表冻结精度、存储时区、版本及并发需求，并对照DDL／ORM；不自行补列或声称已统一。

### 030. 研判结果历史、执行版本与幂等键

状态：待确认设计。

“每客户×每产品一条”与重试、批量、规则更新及旧结果不变要求尚未闭合。需明确执行批次、结果覆盖或追加、历史输入快照、产品／规则版本唯一关联和幂等键，再冻结索引；不得直接设客户×产品永久唯一或覆盖旧结论。

### 031. 研判结果双来源引用一致性

状态：待确认设计／实施核验。

research_result.source_id与customer_info_id分别有引用，不能保证同源。需冻结组合约束或固定服务校验，并验证结果不会引用甲来源和乙来源结构化信息；历史、批量和重试路径均应一致。

### 032. 意向产品编码引用与生命周期

状态：待确认设计。

customer_info.target_product_code声称关联product.product_code，但外键清单未闭合。需确定逻辑／物理引用、索引、未知编码、停用及删除策略，不把文字关联当已建FK。

### 033. 来源到客户主档的类型化引用与归并

状态：待确认设计／实施核验。

需冻结source_reference所指customer_info或research_result的实体类型、长度、稳定标识与幂等，逐项核对主档必填字段及真实字段映射。手机号token仅用于候选匹配，仍须受控确认、归属和事务后回填；不得把同号当身份认证或直接覆盖主档。raw_fields扩展字段白名单仍需与保护策略一并冻结。

### 034. 匿名客服、研判与主档的可选业务联动

状态：待确认是否启用／设计。

客服留资／报名转线索、研判来源建主档及私有结果反哺公开推荐均为可选增强。若启用，需确定用途、可信内部操作者／服务、负责人、关联确认、披露白名单、幂等与对账事务；访客标识不能调用受保护能力，内部结论不能直接交匿名会话。结构不变不等于获授权联动永不写主档。

### 035. 报告五接口完整Schema与路径匹配

状态：待交付／实施核验。

configs GET／PUT路径及精确权限已补齐，不再列为未知；仍需完整请求／响应Schema、真实路由注册、权限依赖及错误路径。验证/report/list不被/report/{report_record_id}捕获，配置读写和管理员／主管动作范围按当前矩阵验收。

### 036. 报告三表完整定义与单一DDL基线

状态：待冻结／核验。

主文档仅保留9+18+10共37个字段名；cyl.md虽补充类型／约束线索，仍需逐项核对report_module_ddl.sql、all.sql、ORM及目标数据库，冻结可空、默认、索引、约束与种子。三表“全新无冲突”未经对象盘点，不得直接初始化或通过循环引用声称完整字段已存在。

### 037. 报告研判与经营数据的上游消费契约

状态：待确认设计／核验。

报告customer_judgement与目标research_result尚未适配，后者经customer_info可空关联主档；需冻结客户关联、产品／来源／版本选择及去重粒度。customer_profile.deal_amount无既有字段和权威业务来源，需决定排除／标不可用或另定金额来源、币种和精度。六只读上游须逐表列出真实字段、状态、时间列及可用版本，缺依赖不能伪造零值成功。

### 038. 五类报告指标字典、时间窗与缺失值

状态：待确认设计。

需为每项指标明确来源、筛选、公式、单位、去重、分母、版本、默认自然／滚动周期、默认最近完整周期及显式时间窗校验，具体涵盖日报修订／作废、客户新增／流失、重复研判、投诉各轮处理及满意度分母。当前已有Asia/Shanghai业务时区、UTC存储目标和[start,end)边界，不再待问；触发17:00不等于统计窗口。分母0、缺上游／历史须标不可计算，迟到数据与跨周期比较采用同一口径。

### 039. 多源快照一致性与复算范围

状态：待确认设计／实施核验。

data_snapshot_at和source_record_count不能保证跨表一致。需冻结统计截点、事务隔离或快照策略、取数期间修改／迟到更新处理、历史输入保留及可复算范围，并用真实数据对账。

### 040. 报告生成幂等键与并发复用

状态：待确认设计／实施核验。

需明确幂等键生成方、传参位置、账号／范围、时间窗、指标及配置版本参与项，同键同口径复用、不同口径冲突、并发唯一约束和失败重试规则。仅有report_code及可选时间窗的请求说明不足以实现这些保证。

### 041. 报告异步任务持久化、四状态与恢复

状态：已确认设计／待实施核验。

四状态机冻结为 `pending → running → success|failed`，禁止任何路径无限停留在 pending 或 running。新增独立任务表 `report_task` 作为持久化队列，与三张结果表分离：`report_task_id`（PK）、`report_record_id`（FK → report_record）、`report_code`、`idempotency_key`、`status`、`lease_owner`、`lease_expires_at`、`attempt_count`、`last_error`、`created_at`、`updated_at`、`row_version`；report_record 只保存结果，任务执行态与结果态不互相代替。worker 用独立数据库会话，先以乐观锁把 pending 原子置为 running 并写入租约；租约默认 5 分钟（可配置），超时未完成回退 pending，attempt_count 递增，超过 3 次置 failed。启动与周期心跳扫描无租约或租约过期的 pending/running 任务重新入队；同幂等键同口径复用既有 report_record，同键不同口径 409，重试不得重复调用模型产生两份成功正文。`last_error`／`fail_reason` 一律脱敏，不含 SQL 参数、连接串、Key 或原文。立即返回 pending 仅表示已受理，不表示可靠交付。

### 042. 报告分类调度、种子更新与启用条件

状态：待实施核验（目标已冻结）。

冻结五类调度：`daily_report` 每天 17:00，`customer_overview`／`weekly_report`／`mental_weekly`／`complaint_weekly` 每周五 17:00，时区统一 Asia/Shanghai，按 IANA 时区解析，不依赖系统默认时区。cron 统一采用 all.sql 既有含秒六字段方言，周五映射为 weekday=5（实施时核对调度库的 0/1 起始约定后固定），不在示例混用 POSIX 五字段。多进程防重复用 report_task 的租约抢占；每次触发生成 `report_code＋时间窗＋attempt` 调度幂等键，同一窗口不重复入队。漏跑补偿：心跳扫描最近一次成功截点后应生成而缺失的窗口并补生成，补生成同样走幂等与租约。all.sql 旧种子日报 18:30／周报 09:00 由受控增量 UPDATE 校正为 17:00／周五并保留五类 report_code，不 DROP／重建。`target_enabled=true` 只表示要求交付定时能力，`execution_enabled=false` 表示示例不执行；仅当上游就绪、指标口径冻结、权限／审计挂载、报告应用已发布可用后由平台管理员置 true 启用。

### 043. 报告配置修改、冗余编码与历史版本

状态：已确认设计。

`report_code` 为稳定业务编码，唯一、非空、创建后不可变；配置修改只更新可调字段（cron_expr、enabled、row_version 等），不产生新 report_code。report_record 保留 `report_config_id` 物理外键，同时冗余 `report_code` 与 `report_version` 用于不依赖外键的追溯；生成时强校验 report_record.report_code 与 report_config.report_code 一致，不一致拒绝落库。`report_version` 冻结为任务受理时 report_config.row_version 的快照，任务与历史正文只依据该冻结版本解释。配置删除采用逻辑停用（enabled=false），不物理删除仍被 report_record 引用的配置；物理删除仅当无任何历史报告引用时允许。已生成报告（正文、指标、编码、版本）只读，后续配置修改只影响新生成任务。

### 044. 报告指标JSON、明细与正文一致性

状态：已确认设计／待实施核验。

`metric_json` 是生成时冻结指标的整体快照（权威），`report_metric` 是其逐条明细，二者由同一份冻结指标在同事务内写入。`metric_code` 采用每类报告预定义的受控字典且全局唯一，`report_metric` 唯一键为 (report_record_id, metric_code)；数值统一 DECIMAL 固定精度，单位存 `metric_unit`，口径存 `calc_rule`，周期存 `period_type`。模型正文 `report_content` 只可引用 metric_json 中已存在的数字，写入前固定服务抽取正文数字与冻结指标逐项对账，不一致或出现输入外数字即置 failed；失败或重试不留下互相矛盾的 JSON、明细与正文，三者同事务原子提交，任何一步失败整体回滚，不存在半成品 success。

### 045. 心理报告匿名聚合与小样本边界

状态：已确认设计／待实施核验。

心理周报只允许按时间周期聚合；部门维度仅在单部门有效学生数达到阈值时才可下钻，否则并入“其他／未分组”。小样本阈值冻结为 k=5：任一分组有效学生数低于 5 时不在报告中展示该分组明细，合并或标注“样本不足，不予展示”，不提供更细的班级、个人、老师维度下钻。字段白名单仅限评估次数、风险等级分布计数、预警总数／处置状态计数及获准周期趋势计数；学生 ID、姓名、联系方式、聊天原文、情绪值、个人预警原因等可追踪标识一律不进入报告链路。原始取数先聚合再进入 metrics、Dify 输入、正文、列表和日志，日志不记录未聚合明细；报告只保留聚合结果，不保留聚合用原始明细。读取仍限平台管理员与部门主管按报告范围。删除姓名或 think 内容不等同匿名，以白名单字段＋k=5 阈值为准。

### 046. 报告Dify真实调用、失败处理与数字校验

状态：待实施核验（目标已冻结）。

协议冻结为 `POST /workflows/run`、`response_mode=blocking`、inputs 含 `report_code` 及 `metrics` JSON 文本，输出读 `data.outputs[REPORT_DIFY_OUTPUT_KEY]`（默认 report_text）并要求 `data.status=succeeded`；超时用公共 DIFY_API_TIMEOUT_SECONDS。任一失败（HTTP 非 200、status≠succeeded、输出缺失／非字符串、JSON 解析失败、超时）置 failed 并写脱敏 fail_reason，重试走 report_task 幂等，不重复调用模型产生多份成功正文。写入前固定服务抽取正文数字与 metric_json 逐项对账，不一致即 failed；“不编数字”的 Prompt 不作为正确性证明。验收以“已发布应用＋真实模型绑定＋一次真实成功生成＋数字／指标对账通过”为准，非空 Key 或目录存在不算验收。

### 047. 企业即时日报摘要与正式报告职责接入

状态：待实施核验（目标已冻结）。

企业 `daily-report` 摘要（ENTERPRISE_SUMMARY_DIFY_API_KEY／enterprise_daily_summary.yml）只负责本人日报的内容级即时摘要，写入 `employee_daily_report.ai_summary`，不新建正式报告表；正式报告 daily_report／weekly_report 由报告模块用固定 SQL 统计数量级指标，或受控复用 ai_summary，不重复调用摘要模型。企业摘要只处理提交者本人已提交日报，不读取未提交草稿；报告侧只读提交后正式内容字段。两条链路各自验证固定 SQL 与真实适配器，不互相替代。人工生成与定时生成复用同一报告生成链路、固定服务、幂等与审计，定时调度仅换触发源，不绕过身份上下文与授权范围；报告不重建识别或摘要智能体，场景客户端由业务负责人维护。

### 048. 本地教务／CRM维护方法与数据契约

状态：已确认设计／待实施核验。

本地为课程／成绩／学业节点／申请进度的权威来源，`source_system` 固定填本地编码（如 `local`），不伪造第三方 external ID。`source_updated_at` 表示来源最近更新时间（本地即本地写入时间）；`synced_at` 保留为未来外部同步可选列，本地方案当前不适用（NULL）；节点改期／停用递增 `event_version`。维护方法冻结：课程走本地受控课程主数据（course_code）；成绩录入 `POST /scores`、更正 `PUT /scores/{id}`、作废 `DELETE /scores/{id}`（软作废 status=void），授权范围见第 050 项；学业节点增／改／停用 `student_academic_event`（event_type=exam/ddl），改期或停用递增 event_version 并联动重排提醒；申请进度由顾问增／更新 `student_application_progress`（stage_code、status、source_updated_at）。逐动作权限：教务 academic 以有效 score_editor 绑定维护成绩与学业节点，班主任只读负责学生，顾问／主管维护客户与申请进度，每次写入重验绑定、版本与状态。链路闭合：教务改期 → 学生本人 `GET /student/academic` → 按 event_version 重排提醒；顾问维护阶段 → 学生本人 `GET /student/progress`。未来外部写回仍走 STUDENT_SYNC_TOKEN／student:sync 可选分支，不作为本地权威维护前置。

### 049. 学生本人课程／成绩读取入口

状态：已确认设计。

新增学生本人只读接口 `GET /api/v1/student/courses` 与 `GET /api/v1/student/scores`，公共 JWT 绑定 student_id，仅本人。返回本人有效课程编码／课程名／学期／考核／得分／满分／状态，分页与排序由固定服务实现；有效成绩（status=valid）默认展示，作废成绩（status=void）不进入默认列表但保留更正痕迹用于审计，学生响应不返回 employee_id 等内部录入字段。课程来源为本地权威课程主数据（course_code），与招生 course_project 完全分离，不混用。实现走固定查询／仓储，不调用老师写入接口，不接受模型生成 SQL；chat 场景涉及本人课程／成绩时由后端复用同一固定查询后返回，不新增智能体写路径。查询仅本人真实结果，隔离他人及内部录入字段。

### 050. 成绩写入的显式课程授权

状态：待实施核验（目标已冻结）。

成绩写入（create／update／void）冻结为：操作者为有效 academic 角色，且存在 status=active、valid_from≤now<valid_to 的 score_editor 绑定并覆盖目标 student_id；`course_scope_code` 为空（NULL）时不推定全课程写权，本期默认拒绝（除非另有显式全课程授权配置，当前不启用）；有值时目标 course_code 必须等于绑定 course_scope_code。逐项校验角色、绑定有效性、授权学生、目标课程，任一不符（含空值、失效绑定、跨课程、跨学生）拒绝，`external_readonly` 时拒绝全部写入。写入同时校验唯一键 (student_id, course_code, term_code, assessment_code, attempt_no) 及 0≤score_value≤max_score、max_score>0。验收须覆盖空 course_scope_code、失效绑定、跨课程、跨学生四类负例全部拒绝，正例通过。

### 051. 请假单表切换与实际审批历史

状态：待设计／条件性实施核验。

student_admin_service及唯一StudentLeaveService是目标；若发现旧student_leave_request调用／数据，需独立主键和submitted／withdrawn等状态映射，不双写。reviewer_id是当前指定人，不能机械替代历史decision_employee_id；真实审批人须由成功审计保留，历史缺失不推断。

### 052. 无负责人、人员失效与转派接管

状态：待确认设计。

请假reviewer_id和预警follower_id可空，仍缺初次无人匹配、负责人离职／绑定失效、主班主任切换及工单失去负责人的完整接管流程。需明确受控发现、补分派／移交、重试／督办入口、锁顺序、原因与前后负责人审计及通知；不得任意老师自行领取或改当前负责人抹去历史操作者。

### 053. 工单处理人的有效绑定范围

状态：待确认设计／实施核验。

企业E5突出service_advisor，E6/B.4/B.6允许class_teacher或service_advisor，需逐动作冻结允许关系，并始终核验同部门teacher、有效学生关系及当前负责人；任意一条绑定不能自动取得全部工单处理能力。

### 054. 投诉回应／解决时限与协作发现机制

状态：待确认设计。

需定义类型／优先级对应的response_due_at／resolution_due_at、计时起点、自然或工作时间、重开后时限和超时督办。新工单待分派、学生补充到处理人等环节须明确由通知、待办或受控列表承接、收件人及可见范围；报告必须使用同一时限和轮次口径。

### 055. 投诉轮次、首次回应与报告统计实现

状态：待实施核验。

正文已区分首次有效回应、每轮给方案及最终closed，重开清空当前字段不抹历史。仍需落实cycle_no历史记录、真实取数与对账，自动回执／内部备注不计首次回应；awaiting_student不得算最终关闭，无法还原的历史时长标不可计算，满意度等分母按指标字典冻结。

### 056. 日报修订的提交部门快照与历史读取

状态：待确认设计。

department_id_at_submit写“最近提交”，主管又按提交部门读取，调部门后修订可能改变归属。需冻结修订是否重置快照、历史读取、报告采用哪次提交／哪个部门及作废处理，防止修订无意转移旧数据授权和统计归属。

### 057. 站内通知发布、任务前缀与本人接口

状态：待实施核验。

in_app、sent表示本人页面可查以及StudentTasks／EnterpriseTasks按event_code前缀消费均已确定。仍需实现列表／未读／详情／已读鉴权、有效收件人校验、事务入队、任务领取／租约与重试。生产与投递模块可以不同，企业产生student事件也只能由StudentTasks投递；不得双发，已发布不等于已读或办结。

### 058. 跟进提醒频率、去重轮次与通知范围

状态：待确认设计／实施核验。

扫描到期事实时业务版本可能不变，需冻结企业跟进／待办提醒的轮次、频率、重新安排及去重键，避免反复发送或永不再提醒。待办按可处理事实、通知按收件人分别授权；角色变化后的敏感正文和回执须重新校验，已读不能代替业务处理。

### 059. 学业提醒设置代次、精度与对象版本映射

状态：待确认设计／实施核验。

updated_at仅表示提醒设置代次，投递状态不更新该字段的规则已有结论；仍需验证ORM自动更新时间和任务条件更新，冻结同微秒快速设置的单调推进／冲突策略及JSON精度。工单／请假row_version、预警version→API row_version、节点event_version、会话version及提醒expected_event_version+expected_updated_at须分别实现，不能统一强加同名物理列。

### 060. 外部同步等时冲突、迟到变更与来源优先级

状态：待确认设计。

未来启用同步时，需定义source_updated_at相等但内容不同、迟到删除／改期、source_system冲突、重试及事务策略。失败不得刷新synced_at，外部ID不能按姓名猜；当前本地维护的版本语义须先与本地契约对齐。

### 061. 心理跟进历史与可信源事件去重

状态：待确认设计／实施核验。

mental_warning只列handling_result／version，尚未明确多次follow note由审计或受控记录承载及其读取／保留策略，不能覆盖历史备注。需冻结聊天和直接monitor的source_event_id／workflow_run_id映射、唯一性与预警去重，可信事件ID不由模型生成。history_data新记录NULL等来源叙述未经过实际实现验证。

### 062. 学生会话首次创建、并发轮次与模型回放

状态：待确认设计／实施核验。

conversation_token绑定session.version及(student_id,request_key)回执，但建会话／轮次执行占位、并发模型请求、失败恢复与成功回放顺序尚未闭合。需防止重试重复调用模型或创建重复会话；客服会话体系不自动套用学生规则。

### 063. 企业独立NL2SQL参数与受限执行契约

状态：待确认设计／实施核验。

enterprise_nl2sql独立于旧generate_sql(question)，仍需冻结sql_template+params占位符与后端规范化绑定值／类型的对应校验。模型不能决定新的参数值；真实执行需验证AST、只读连接、行列白名单和数据范围。公共HTTP共用不能替代业务契约，也不强制迁移学生固定查询或报告固定SQL。

### 064. 学生group查询提供方与student-v1响应

状态：待确认设计／交付核验。

学生预留student-v1查询，但公共模块尚无对应HTTP／服务提供契约。需继续使用local固定查询或明确新增受控适配，冻结真实rows结果、授权和失败处理；企业SQL候选或旧自然语言客户端不能直接当已执行查询结果。

### 065. 本地faster-whisper音频入口与资源限制

状态：待设计／实施核验。

本地ASR选择已确定，仍需受保护上传入口、格式／大小／时长校验、账号与资源限额、适配器、依赖和离线模型准备、转写展示核对及真实中文音频测试。ASR_*只是未加入Settings的规划变量，small+CPU/int8是初始示例；不得当作已安装／可运行，不需要旧语音Dify Key，确认写入阶段不重复推理。

### 066. 内容维护、发布及多消费端版本同步

状态：待确认设计。

内容运营由员工admin承担已确定；仍需补齐FAQ、课程／活动、学生资料等维护入口、权限、审核／发布／生效／停用及版本追溯。关系库FAQ、客服Dify知识库、学生knowledge.json等须明确更新传播和失效版本剔除；企业内部制度与访客／学生资料不得混用可见范围。

### 067. 报名取消办理及取消后重报闭环

状态：待确认范围／设计。

现有六客服接口未列取消入口，而正文承诺取消后重报。需确定本期是否提供取消；若提供，冻结受控入口、操作者核实、重复取消、signed_count回退、满额活动恢复和重报规则。匿名报名不授予仅凭任意报名ID取消他人记录的能力；若人工办理亦须说明路径。

### 068. 客服路由真实挂载

状态：待实施核验。

来源main.py中的agent挂载仍为注释示例；需核对目标代码和OpenAPI，验证六接口以/api/v1前缀可匿名调用。新目录或联动图列出agent不能证明已注册。

### 069. 客服real客户端、配置及应用协议

状态：待实施核验。

allm称real已实现，hzl及静态代码显示RealDifyClient.__init__抛NotImplementedError，DIFY_CLIENT／DIFY_AGENT_API_KEY未声明／配置，get_dify_client直接读缺失属性。还存在/chat-messages注释与/workflows/run方案差异；需按实际发布应用冻结Workflow／Chatflow协议、实现客户端和公共传输，真实验证intent／reply／动作映射及失败兜底，不能只把模式改为real。

### 070. 客服会话flush、消息提交顺序与失败保留

状态：待实施核验。

来源要求会话先落库、用户消息先提交及Dify失败兜底，代码快照则在模型返回后统一提交，未见对应保障。需核验父子写入／flush顺序、模型失败时用户消息保留、日志、兜底回复及事务边界，不将设计流程写成实现保证。

### 071. 客服报名状态、行锁与最后名额竞争

状态：待实施核验。

当前仅见有效报名查重，未见完整行锁／名额并发保证。需验证活动状态和容量、状态式去重、同手机号重试、竞争最后名额、人数与报名记录同事务，以及取消后重报；不引入阻止重报的永久活动×手机号唯一约束。

### 072. 客服及研判DSL、知识库、种子和联调资产

状态：待交付核验。

源总览列出的客服DSL、四类知识资料、种子及上传／测试脚本在旧目标目录未发现，研判抽取DSL亦属可选／待交付。需按第七章完整路径逐项盘点提交或交付包、内容校验、导入绑定与实际执行结果；目录树不能证明资产存在。

### 073. 初始化、条件迁移、增量回滚与外部副作用

状态：待条件性设计／核验。

当前无真实业务数据／旧调用方，不将迁移作为实施前置；若实际发现存量，须审查初始化脚本是否DROP／重建／覆盖种子，采用可审计增量。逐实体映射账号、主档、来源／信息／产品／规则／结果、文件及报告配置／记录／指标，不统一ID偏移。回滚先停写、保留新增数据、备份验证和对账；无引用仍可能有业务数据，不能直接删表。需核实实际外部写入／通知并定义稳定回执、幂等及补偿，不因旧来源声称无副作用而免检。

### 074. JWT认证兼容与授权变更验证

状态：待实施核验。

后续新增授权或跨副本切换须分别验证签名算法／密钥／有效期／sub映射与运行时权限。旧JWT可解析不等于账号仍有旧权限，user_id变化可能误指他人，需重新登录或受控过渡；当前无旧调用方不代表实际发现存量后可以忽略这些条件。
