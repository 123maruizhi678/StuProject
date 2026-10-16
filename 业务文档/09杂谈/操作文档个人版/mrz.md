# 马睿智个人操作文档

模块名字：公共登录与权限入口（公共基础能力）  
负责人：马睿智  
更新日期：2026-10-16  
系统目录：`D:\AI\StuProject`

本模块为各业务提供登录认证、接口鉴权、日志生成、统一返回格式及本地 Dify HTTP 请求封装。以下说明区分当前代码能力与建议补充项；本次只修改文档，未变更后端实现。

## 一、模块功能以及对应的接口和对应的数据库表

本模块提供三个对外 HTTP 接口，以及供每个业务接口复用的 JWT 认证、鉴权中间件、日志、统一返回和本地 Dify HTTP 请求工具。身份认证采用 JWT；每个受保护的业务接口分别声明所需权限并接入公共鉴权中间件，通过后才能执行具体业务。

### 1. 对外 HTTP 功能接口

| 功能 | 接口 | 调用用户 / 认证要求 | 对应数据库表或资源 | 功能说明 |
| --- | --- | --- | --- | --- |
| JWT 登录 | `POST /api/v1/auth/login` | 允许未登录用户提交账号密码 | `user_account` | 校验用户名及密码哈希，签发有有效期的 JWT；返回 `access_token`、`token_type`、`expires_in` |
| 公开访问清单 | `GET /api/v1/auth/public-access` | 无需 JWT | `app/access_control.yaml` | 返回允许匿名访问的页面和模块信息 |
| 当前用户权限清单 | `GET /api/v1/auth/me/access` | 必须携带有效 Bearer JWT | `user_account`、`app/access_control.yaml` | 通过 JWT 确认当前账号，读取用户表身份并映射权限，返回本人的身份、权限、可访问页面和模块；不代替各业务接口的权限校验 |

### 2. 供各业务接口调用的公共功能

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

## 二、用户角色和接口鉴权

### 1. JWT 身份认证与逐接口鉴权

身份认证统一采用 JWT。权限校验由每个受保护接口调用公共鉴权中间件，依据用户表中的身份及对应权限，判断是否允许执行该接口。当前 FastAPI 代码通过 Depends(require_permission(...)) 接入公共鉴权组件，下文统称“鉴权中间件”；它在执行接口业务前完成认证和权限检查。具体流程为：

1. 用户提交账号密码，后端查询 `user_account` 并验证 `password_hash`。
2. 登录成功后签发带有效期的 JWT，返回 access_token、token_type 和 expires_in；后续请求携带 `Authorization: Bearer <access_token>`。
3. 每个受保护接口先调用鉴权中间件；中间件复用公共认证依赖，校验 JWT 签名及有效期，通过 Token 的 sub 取得 user_id，再查询用户表，取得真实 identity_type 和关联业务 ID。JWT 用于确认身份，接口权限以服务端当前用户记录和权限配置为准。
4. 当前实现用用户表中的 `identity_type` 到 `app/access_control.yaml` 查找权限集合。
5. 每个业务接口调用 require_permission(permission)，明确声明自己需要的权限，例如 student.admin_service.create；中间件检查该用户是否具备权限，通过后才执行接口。没有有效 JWT 时按 401 未认证处理；已认证但没有所需权限时按 403 禁止访问处理。响应信封及 HTTP 状态按第四节约定处理。
6. 业务模块继续检查本人/部门/学生关系、当前分派和状态等业务条件，限制可操作的具体记录。

**当前实现说明：** `user_account` 保存身份和关联 ID，没有独立的 `permissions` 字段，也没有在当前公共鉴权中查询独立用户权限关系表。因此准确口径是“用户表确定身份，权限配置确定该身份可以调用哪些接口”。若后续改为每个账号单独分配接口权限，需要增加相应数据模型和查询逻辑，不能描述成当前已经支持。

权限由服务端用户记录和配置决定，不接受前端自报身份。前端隐藏菜单仅用于展示；直接请求业务 API 时仍须鉴权。接口注册和调用由业务模块负责，公共鉴权负责允许或拒绝访问。

### 2. 当前用户身份及权限

| 用户身份 | 用户表取值 | 当前 YAML 权限 | 范围说明 |
| --- | --- | --- | --- |
| 管理员 | `admin` | `admin.dashboard` | 当前只有管理员看板权限，不自动拥有全部业务接口权限 |
| 员工 | `employee` | `dashboard.employee`、`student.profile.read`、`student.admin_service.review`、`service_ticket.read`、`service_ticket.handle`、`report.read` | 业务仍须检查员工角色、部门、学生关系和分派范围；这些标识不表示所有接口都已接入校验 |
| 客户 | `customer` | `dashboard.customer`、`course_project.read`、`event_signup.create`、`service_ticket.create`、`service_ticket.read_own` | 客户本人的业务范围；不等同于学生身份 |
| 学生 | `student` | `dashboard.student`、`student.profile.read_own`、`student.admin_service.create`、`student.admin_service.read_own`、`student.notification.read_own` | 本人学生业务范围，不能审批请假或查看其他学生数据 |
| 匿名用户 | 无有效登录身份 | 无登录权限集合 | 仅公开清单、登录和业务明确公开的接口 |

以上是当前配置事实，最终每个业务接口允许哪些身份，由业务负责人给出权限清单后统一配置。现有 `employee` 下的 `report.read` 与报告方案“仅管理层访问”的要求存在差异，需按最终业务授权调整。员工业务角色中的顾问、主管、老师、教务等不能仅凭统一 `employee` 身份区分，需由业务服务结合员工角色和关系校验。

### 3. 公共接口访问权限

| 接口 | 允许用户 | 操作说明 |
| --- | --- | --- |
| `GET /api/v1/auth/public-access` | 所有用户，含未登录用户 | 获取公开页面/模块信息 |
| `POST /api/v1/auth/login` | 所有用户提交凭据 | 有效账号密码才能取得 Token |
| `GET /api/v1/auth/me/access` | 已通过认证且身份已配置的用户 | 仅返回当前账号权限，不允许指定其他用户查询 |

### 4. 每个接口接入鉴权中间件的方式
 
各接口分别声明所需权限，不复用一个“登录成功即可访问所有业务”的规则。登录和公开清单等明确公开的接口无需挂载受保护接口的权限依赖。业务需要新增权限时，由负责人提供权限标识、允许角色和数据范围，公共模块统一维护权限映射；业务负责人将鉴权依赖接入每个对应接口。

关联表：本模块直接使用 `user_account`；其中 `employee_id`、`customer_id`、`student_id` 分别关联 `employee`、`customer_profile`、`student_profile`。业务表的维护归各业务模块。

## 三、日志生成

各业务获取公共日志工具，按需记录启动、处理结果、外部调用失败和异常信息。

日志默认输出到控制台和 app/logs/ 下的日期命名日志文件，路径及等级由 LOG_DIR、LOG_LEVEL 配置。格式包含时间、级别、模块名称、行号和消息。当前日志文件名按进程加载时的日期确定。

公共模块提供日志工具，各业务负责调用工具记录具体业务事件。文本运行日志与数据库 `operation_log` 中的业务审计不同；账号密码、Token、Dify API Key 不写入日志，业务原文按需脱敏。

## 四、统一返回格式及异常处理

各业务 HTTP 接口通过统一返回工具组织响应，固定包含 code、message、data 三个字段。

`code` 为业务状态码，`message` 为说明，`data` 为结果数据；成功为 0，常用失败码包括 400 参数错误、401 未登录、403 无权限、404 不存在、409 冲突、500 内部错误。

应用入口注册全局异常处理后，业务异常被转换为统一信封；未处理异常记录日志并返回通用内部错误。当前业务异常及未处理异常使用 HTTP 200 搭配业务码；HTTPException、参数校验异常仅企业路径进行了统一信封处理，其他路径仍可能返回框架格式，部分业务也显式使用实际 HTTP 错误状态。因此各模块“所有响应都统一”目前尚未完全落实，需要进一步统一异常出口和协议约定。

本地 Dify 原始响应先交由业务适配器解析，再由业务接口调用 `success()` 返回；公共 HTTP 工具不直接把模型响应变成业务成功结果。

## 五、调用本地 Dify 大模型：公共 HTTP 请求能力

各业务都有自己的 Dify 应用及模型能力。本模块只提供从后端到本地 Dify 的 HTTP 请求封装。各业务负责人负责自己的模型选择、Prompt、工作流/对话应用、知识库、业务输入和结果解释。

| 分工 | 公共模块负责 | 业务模块负责人负责 |
| --- | --- | --- |
| 地址与连接 | 接收 Dify API 基础地址，拼接请求路径 | 确认使用的本地 Dify 服务和应用类型 |
| 应用凭据 | 使用传入的应用 Key 设置 `Authorization: Bearer ...` | 为业务应用配置独立 Key，交由服务端配置读取 |
| HTTP 请求 | 同步/异步 JSON POST、超时、HTTP 错误检查、JSON 对象解析 | 选择 `/workflows/run` 或 `/chat-messages`，组装对应请求体 |
| 模型能力 | 提供 HTTP 传输工具 | 模型、工作流、Prompt、知识库及业务策略 |
| 返回结果 | 返回 Dify 原始 JSON 对象，底层异常交调用方处理 | 检查工作流业务状态，提取输出、校验结构，并转换成业务结果 |
| 后续动作 | 不承担各业务的数据写入或审批判断 | 调用业务服务执行落库、审批、通知和状态变更 |

### 调用方式

本地 Dify 基础地址默认从 `DIFY_API_BASE` 读取，当前默认值为 `http://127.0.0.1/v1`。各应用使用各自的 API Key；调用地址为后端可访问的 Dify 地址，模型供应商的配置由各业务在 Dify 中维护。

同步业务调用同步 HTTP 方法，异步业务调用异步 HTTP 方法。应用 Key 从后端配置读取，不由浏览器提交，也不写入文档。具体输入和输出字段由各业务定义，调用用户标识由可信认证上下文生成。

当前工具只封装 JSON POST；SSE 流式输出、文件上传、自动重试、连接池长期复用、熔断和 HTTP 失败到业务错误码的统一映射尚未提供。各业务如需要这些能力，应明确需求后扩展；工作流返回 HTTP 200 仍可能执行失败，必须由业务适配器检查，不能只依据 HTTP 成功判断模型调用成功。

## 六、纳入本模块的其他通用功能

数据库会话、统一配置、密码与 Token 管理、请求参数校验与公共响应模型均纳入本模块公共能力，已同步列入第一节功能接口表。

| 通用功能 | 当前情况 | 使用方式 / 分工 |
| --- | --- | --- |
| 数据库连接和请求级会话 | 已有 `engine`、`SessionLocal`、`Base`、`get_db()`、`dispose_db()` | 各业务共用连接池和 ORM 基类；请求异常回滚并关闭会话，提交事务仍由业务服务明确执行；不自动建表 |
| 统一配置管理 | 已有 `app/config.py` | 从项目根目录 `.env` 读取数据库、日志、认证和 Dify 配置；各业务新增配置项时统一声明，不复制配置文件 |
| 密码哈希与 Token 管理 | 已有密码哈希、校验和 JWT 签发/解析 | 账号创建时复用 `hash_password()`；受保护接口复用认证依赖；当前未提供独立注册、找回密码、刷新 Token 或退出登录接口 |
| Pydantic 请求校验与公共响应模型 | 已有基础设施 | 各业务在 schemas 定义自身字段，公共层提供 ResponseModel 和统一错误出口；全路径校验错误格式仍待补齐 |

NL2SQL 可作为跨模块复用的业务服务，但它包含 SQL 生成、查询执行及权限范围策略，不属于“只发送 HTTP”的 Dify 公共传输层。通知、工单审计、幂等和业务状态机也需业务规则，不将其自动纳入本人的已完成公共功能。

## 七、架构目录（文件名及功能作用）

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

