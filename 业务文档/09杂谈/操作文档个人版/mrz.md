# 马睿智个人操作文档

模块名字：公共登录与权限入口（公共基础能力）  
负责人：马睿智  
更新日期：2026-10-16  
系统目录：`D:\AI\StuProject`

本模块为各业务提供登录认证、接口鉴权、日志生成、统一返回格式及本地 Dify HTTP 请求封装。以下说明区分当前代码能力与建议补充项；本次只修改文档，未变更后端实现。

## 一、模块功能以及对应的接口和对应的数据库表

公共能力分为对外 HTTP 接口和供后端业务调用的 Python 公共方法。日志、返回格式和 Dify 请求封装当前通过公共方法复用，没有单独新增面向前端的 HTTP 接口。

| 功能 | 对应接口 / 公共方法 | 对应数据库表或资源 | 说明 |
| --- | --- | --- | --- |
| 账号登录 | `POST /api/v1/auth/login` | `user_account` | 查询账号、验证密码哈希，成功后签发 JWT Token |
| 公开访问清单 | `GET /api/v1/auth/public-access` | 权限配置，不查询专属业务表 | 返回未登录用户可见页面、模块的元数据 |
| 当前用户权限清单 | `GET /api/v1/auth/me/access` | `user_account`、权限配置 | 返回本人身份、权限标识、可见页面和模块，不是全部业务 API 清单 |
| 身份认证 | `get_current_account()` | `user_account` | 校验 Bearer JWT 的签名和有效期，查询当前账号 |
| 接口权限校验 | `require_permission(permission)` | `user_account.identity_type`、`app/access_control.yaml` | 根据用户表中的身份划分映射权限，判断是否允许调用对应接口 |
| 日志生成 | `init_logger()`、`get_logger(name)` | 本地 `app/logs/` 或配置目录 | 输出时间、级别、模块、行号及内容，支持记录异常堆栈 |
| 统一返回格式 | `success()`、`fail()`、`ResponseModel` | 无专属表 | 统一构造 `code/message/data` 响应 |
| 全局异常处理 | `BusinessException`、`register_exception_handlers(app)` | 日志文件；无专属表 | 收敛业务异常及未处理异常；HTTP/校验异常的统一目前有范围限制 |
| 本地 Dify HTTP 请求 | `DifyHttpClient.post_json_sync()`、`post_json()` | 本地 Dify 服务；无专属表 | 提供同步/异步 JSON POST、应用 API Key 请求头、超时、HTTP 状态检查和 JSON 对象解析 |

## 二、用户角色和接口鉴权

### 1. 鉴权规则

根据用户表中划分的身份及其对应权限，决定用户能否调用某个接口。具体流程为：

1. 用户提交账号密码，后端查询 `user_account` 并验证 `password_hash`。
2. 登录成功后返回 Token；后续请求携带 `Authorization: Bearer <access_token>`。
3. 公共认证依赖验证 Token，通过 `user_id` 重新查询用户表，取得真实 `identity_type` 和关联业务 ID。
4. 当前实现用用户表中的 `identity_type` 到 `app/access_control.yaml` 查找权限集合。
5. 业务接口声明需要的权限，例如 `student.admin_service.create`；公共鉴权检查用户是否具备该权限，具备才允许继续执行。
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

业务接入示例：

```python
from fastapi import Depends
from app.core.authorization import require_permission

# 在对应业务接口的参数中使用：
# account = Depends(require_permission("student.admin_service.create"))
# 通过后，业务服务仍需校验 account.student_id 及记录归属。
```

关联表：本模块直接使用 `user_account`；其中 `employee_id`、`customer_id`、`student_id` 分别关联 `employee`、`customer_profile`、`student_profile`。业务表的维护归各业务模块。

## 三、日志生成

各业务通过 `get_logger(__name__)` 获取同一套日志工具，按需记录启动、处理结果、外部调用失败和异常信息。

```python
from app.core.logger import get_logger

logger = get_logger(__name__)
logger.info("开始处理业务请求")
# 在异常处理块中调用 logger.exception("业务处理失败") 记录堆栈。
```

日志默认输出到控制台和 `app/logs/YYYY-MM-DD.log`，路径及等级由 `LOG_DIR`、`LOG_LEVEL` 配置。格式包含时间、级别、模块名称、行号、消息。当前文件名在进程加载时按日期生成，代码使用普通 FileHandler，尚未实现持续运行时跨天自动切换和自动清理历史文件，不将这两项写作已完成。

公共模块提供日志工具，各业务负责调用工具记录具体业务事件。文本运行日志与数据库 `operation_log` 中的业务审计不同；账号密码、Token、Dify API Key 不写入日志，业务原文按需脱敏。

## 四、统一返回格式及异常处理

各业务 HTTP 接口通过 `success()`、`fail()` 返回统一结构：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

`code` 为业务状态码，`message` 为说明，`data` 为结果数据；成功为 0，常用失败码包括 400 参数错误、401 未登录、403 无权限、404 不存在、409 冲突、500 内部错误。

```python
from app.core.response import success, BusinessException

# 成功：return success({"id": 1})
# 失败：raise BusinessException("记录不存在", code=404)
```

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

```python
from app.config import settings
from app.core.dify import DifyHttpClient

async def invoke_business_workflow(app_key: str, inputs: dict, caller_id: str):
    client = DifyHttpClient(
        settings.DIFY_API_BASE,
        timeout=settings.DIFY_API_TIMEOUT_SECONDS,
    )
    raw = await client.post_json(
        "/workflows/run",
        api_key=app_key,
        payload={
            "inputs": inputs,
            "response_mode": "blocking",
            "user": caller_id,
        },
    )
    return raw  # 业务适配器继续校验执行状态和输出字段。
```

同步业务使用 `post_json_sync()`，异步业务使用 `await post_json()`。Key 从后端配置读取，不由浏览器提交，也不写入文档。上例为公共工具调用示例，具体 inputs 和输出字段由每个业务定义；caller_id 由可信认证上下文生成。

当前工具只封装 JSON POST；SSE 流式输出、文件上传、自动重试、连接池长期复用、熔断和 HTTP 失败到业务错误码的统一映射尚未提供。各业务如需要这些能力，应明确需求后扩展；工作流返回 HTTP 200 仍可能执行失败，必须由业务适配器检查，不能只依据 HTTP 成功判断模型调用成功。

## 六、其他可以复用的通用功能

| 通用功能 | 当前情况 | 使用方式 / 分工 |
| --- | --- | --- |
| 数据库连接和请求级会话 | 已有 `engine`、`SessionLocal`、`Base`、`get_db()`、`dispose_db()` | 各业务共用连接池和 ORM 基类；请求异常回滚并关闭会话，提交事务仍由业务服务明确执行；不自动建表 |
| 统一配置管理 | 已有 `app/config.py` | 从项目根目录 `.env` 读取数据库、日志、认证和 Dify 配置；各业务新增配置项时统一声明，不复制配置文件 |
| 密码哈希与 Token 管理 | 已有密码哈希、校验和 JWT 签发/解析 | 账号创建时复用 `hash_password()`；受保护接口复用认证依赖；当前未提供独立注册、找回密码、刷新 Token 或退出登录接口 |
| Pydantic 请求校验与公共响应模型 | 已有基础设施 | 各业务在 schemas 定义自身字段，公共层提供 ResponseModel 和统一错误出口；全路径校验错误格式仍待补齐 |
| 请求追踪 ID 和调用耗时 | 建议补充，未作为已完成能力 | 给请求、业务日志、Dify 调用建立统一关联，便于排查问题 |
| 公共健康检查与依赖探测 | 可进一步完善 | 可区分服务存活与数据库/Dify 可用性，避免仅因根路径返回成功就判断依赖正常 |
| 日志自动滚动与保留策略 | 建议补充 | 补齐跨天切换、文件大小限制及历史清理 |

NL2SQL 可作为跨模块复用的业务服务，但它包含 SQL 生成、查询执行及权限范围策略，不属于“只发送 HTTP”的 Dify 公共传输层。通知、工单审计、幂等和业务状态机也需业务规则，不将其自动纳入本人的已完成公共功能。

## 七、架构目录

以下只列当前公共能力涉及的文件夹，不列文件：

```text
D:/AI/StuProject/
├── app/
│   ├── api/
│   ├── core/
│   ├── services/
│   ├── models/
│   ├── schemas/
│   ├── clients/
│   └── logs/
└── scripts/
    └── sql/
```

`api/` 承载登录和访问清单接口，`core/` 承载日志、响应、认证鉴权及 Dify HTTP 工具，`services/` 承载认证服务，`models/` 承载用户表映射，`schemas/` 承载请求/响应结构，`clients/` 供各业务放置 Dify 应用适配器，`logs/` 保存运行日志，`scripts/sql/` 保存数据库脚本。

交付各业务的公共接入方式为：业务接口接入身份及权限依赖，业务处理使用公共数据库会话和日志，模型调用复用 HTTP 工具，再由业务服务解析结果并用统一返回工具响应。
