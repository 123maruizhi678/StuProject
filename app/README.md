# StuProject 应用模块说明

`app/` 是 StuProject 的 Python 后端应用包，基于 FastAPI、SQLAlchemy、MySQL 和可选的 Dify 工作流。此目录包含应用入口、认证与权限组件、通用响应/日志工具、数据库连接、报告 ORM 模型以及 NL2SQL 服务。

## 目录结构

```text
app/
├── api/                 # HTTP 路由
│   ├── auth.py          # 登录、公开访问清单、当前用户访问清单
│   └── student_leave.py # 学生请假接口（路由工厂）
├── clients/             # 外部 API 适配器
│   ├── nl2sql_dify.py   # NL2SQL Workflow 请求/响应适配
│   └── student_leave_dify.py # 请假 Workflow 请求和结果校验
├── core/                # 通用基础工具
│   ├── auth.py          # Bearer Token 当前用户依赖
│   ├── authorization.py # YAML 权限加载和访问判断
│   ├── dify.py          # Dify HTTP 通用传输层
│   ├── logger.py        # 日志初始化及 logger 获取
│   └── response.py      # 统一响应与全局异常处理
├── models/              # SQLAlchemy ORM 模型
│   ├── report.py        # 报告配置、报告记录、报告指标
│   ├── student_leave.py # 学生请假相关表映射
│   └── user_account.py  # 统一登录账号
├── schemas/             # 请求/响应数据结构
│   ├── auth.py          # 登录请求校验
│   └── student_leave.py # 请假输入和 Dify 输出校验
├── repositories/        # 学生请假数据访问
├── services/            # 业务服务
│   ├── auth_service.py  # 密码验证和 JWT
│   ├── nl2sql_service.py# NL2SQL 查询执行
│   └── student_leave_service.py # 请假事务和业务规则
├── tasks/               # 后台任务包（当前目录中尚无具体任务模块）
├── access_control.yaml  # 身份权限、页面与模块策略
├── config.py            # .env 设置
├── database.py          # SQLAlchemy 引擎和会话
└── main.py              # FastAPI 应用入口
```

## 启动方式

在项目根目录（`app/` 的上一级）创建并配置 `.env`，然后启动：

```powershell
conda activate SST
uvicorn app.main:app --host 0.0.0.0 --port 12345 --reload
```

应用文档通常在 `/docs`。当前 `main.py` 导入了认证路由对象 `auth_router`，但尚未调用 `app.include_router(auth_router, ...)`；学生请假路由也定义了路由工厂，但还没有在主入口组装。因此这两组端点都需先注册才能对外提供。若要以 `/api/v1/auth/...` 对外提供，需要在 `main.py` 添加挂载，例如：

```python
app.include_router(auth_router, prefix="/api/v1")
```

挂载后，`api/auth.py` 自身的 `/auth` 前缀与 `/public-access`、`/login`、`/me/access` 路径组合为相应完整路径。

## 通用工具调用方法

### 1. 统一响应和异常：`core/response.py`

业务接口可用 `success()`、`fail()` 生成 `{code, message, data}` 信封；业务层可抛出 `BusinessException`，由 `register_exception_handlers(app)` 统一转换为响应。

```python
from app.core.response import BusinessException, fail, success

return success({"id": 12}, message="查询成功")
return fail(code=400, message="参数不正确")
raise BusinessException("记录不存在", code=404)
```

`main.py` 已调用 `register_exception_handlers(app)`。当前异常处理器将业务异常和未处理异常以 HTTP 200 返回，业务状态放在响应体 `code` 中；客户端需检查 `code`，不能只看 HTTP 状态。

### 2. 日志：`core/logger.py`

`init_logger(to_console=True, to_file=True)` 初始化根日志记录器（重复调用不会重复初始化）；`get_logger(name)` 获取模块 logger，首次调用会自动初始化。日志写控制台和按日期命名的文件，目录由 `LOG_DIR` 设置。

```python
from app.core.logger import get_logger

logger = get_logger(__name__)
logger.info("开始处理请求")
logger.exception("处理失败")  # 在异常处理上下文中记录异常堆栈
```

### 3. 数据库会话：`database.py`

`get_db()` 是 FastAPI 依赖，每个请求创建并关闭一个 SQLAlchemy `Session`；遇到异常会先回滚。`dispose_db()` 释放连接池，适合应用关闭时调用。`Base` 是 ORM 模型基类，`engine` 是同步 MySQL 引擎。

```python
from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session
from app.database import get_db


def read_items(db: Annotated[Session, Depends(get_db)]):
    ...
```

数据库表不会由 `database.py` 自动创建；请使用项目数据库初始化/迁移脚本。

### 4. 认证服务：`services/auth_service.py` 与 `core/auth.py`

- `hash_password(password)`：生成密码哈希，创建账号时保存哈希，不保存明文。
- `verify_password(password, password_hash)`：核对密码。
- `authenticate(db, username, password)`：验证账号并返回 `UserAccount`，失败时返回 `None`。
- `create_access_token(account)`：签发 JWT，返回 `(token, expires_in_seconds)`。
- `decode_access_token(token)`：验证 JWT 并返回账号 ID；无效时返回 `None`。
- `get_current_account`：FastAPI 依赖，从 Bearer Token 认证当前账号。

```python
from typing import Annotated
from fastapi import Depends
from app.core.auth import get_current_account
from app.models.user_account import UserAccount


def private_endpoint(
    account: Annotated[UserAccount, Depends(get_current_account)],
):
    return {"user_id": account.user_id}
```

### 5. 访问权限：`core/authorization.py`

`load_access_control()` 读取并缓存 YAML；`permissions_for(identity_type)` 获取身份的权限集合；`require_permission(permission)` 返回 FastAPI 依赖，用于保护接口；`public_access()` 返回公开页面/模块；`access_for(identity_type, user_id)` 按角色权限筛选页面和模块。

```python
from typing import Annotated
from fastapi import Depends
from app.core.authorization import require_permission
from app.models.user_account import UserAccount


def list_reports(
    account: Annotated[
        UserAccount,
        Depends(require_permission("report.read")),
    ],
):
    ...
```

对应权限标识必须先配置在 `access_control.yaml` 的角色 `permissions` 中。返回前端的页面/模块可见性不能替代后端 API 权限校验和数据归属检查。

### 6. Dify HTTP 通用层与业务适配器

`core/dify.py` 中的 `DifyHttpClient` 只负责 HTTP 传输：将调用方提供的 JSON 请求体 POST 到指定路径，加入 Bearer API Key，设置超时，检查 HTTP 状态并返回 JSON 对象。它不选择应用、不生成业务请求体，也不解析 Workflow/Chat 的业务输出。

客户端提供同步和异步方法：

- `post_json_sync(path, api_key=..., payload=..., timeout=None)`：供同步业务链路使用。
- `post_json(path, api_key=..., payload=..., timeout=None)`：供异步业务链路使用。
- `transport` / `async_transport`：可注入 HTTPX transport，便于隔离测试。

```python
from app.core.dify import DifyHttpClient

http = DifyHttpClient("http://127.0.0.1/v1", timeout=60)
response = await http.post_json(
    "/workflows/run",
    api_key="从服务端设置读取",
    payload={
        "inputs": {"question": "统计本月新增客户数量"},
        "response_mode": "blocking",
        "user": "staff-123",
    },
)
```

Dify 的 API 路径、请求字段和响应字段由业务适配器负责：

- `clients/nl2sql_dify.py` 的 `NL2SQLDifyClient.generate_sql()` 构造 `question` 输入，确认 Workflow 成功并提取 SQL 字段。
- `clients/student_leave_dify.py` 的 `StudentLeaveDifyClient.analyze_leave()` 构造请假字段，校验 `status`、`result` 结构和运行版本，并将底层 HTTP 错误转换为请假接口的安全错误响应。
- `services/nl2sql_service.py` 执行 NL2SQL 专属策略和查询；`services/student_leave_service.py` 负责请假业务与数据库事务。

新增模型厂商时也遵循这个边界：若通过 Dify 调用，复用 HTTP 传输层并为业务/应用编写适配器；若直接调用厂商 API，则共享可复用的 HTTP 基础能力，但为该厂商单独实现鉴权、请求和响应适配器。

### 大模型密钥放置位置

Dify 有两类不同的密钥，不能混为一类：

1. **Dify 应用 API Key**：StuProject 服务端调用某个已发布 Dify 应用时使用。放在项目根目录 `D:\AI\StuProject\.env`；所有 Dify 应用 Key 统一从此文件读取。配置名示例：

   ```env
   DIFY_API_BASE=http://127.0.0.1/v1
   DIFY_NL2SQL_API_KEY=填写NL2SQL应用专用Key
   DIFY_NL2SQL_OUTPUT_KEY=sql
   STUDENT_DIFY_LEAVE_KEY=填写请假Workflow专用Key
   STUDENT_DIFY_LEAVE_TIMEOUT=60
   STUDENT_DIFY_LEAVE_VERSION=student-leave-v1
   ```

   NL2SQL 也兼容旧变量 `DIFY_API_KEY` 和 `DIFY_SQL_OUTPUT_KEY`。不同 Dify 应用应使用各自的应用 Key；不要把真实密钥提交到 Git、放进 DSL 或返回给浏览器。请假设置也只读取项目根目录 `.env`；`DIFY_API_BASE` 是共用固定地址 `http://127.0.0.1/v1`，不为单个应用单独设置。

2. **模型供应商 API Key**：例如 OpenAI、Anthropic 或其他模型供应商的凭据，如果由 Dify 工作流调用模型，仍由 Dify 工作区模型供应商配置使用；StuProject 的 `.env` 保存的是调用 Dify 应用的 Key，两者用途不同。Dify 工作流内部选择模型也在 Dify 中配置。

如果未来某项功能绕过 Dify、由 StuProject 直接调用模型厂商 API，才在服务端 `.env` 增加相应厂商变量（例如 `OPENAI_API_KEY`），并在后端配置和厂商适配器中读取；仍不要把 Key 放进前端。
### 7. NL2SQL 查询：`services/nl2sql_service.py`

`nl2sql_query(question, read_only=True)` 是异步通用业务入口：调用 Dify `nl2sql` Workflow 生成 SQL，再在线程池中使用当前数据库引擎执行，返回统一信封；成功数据含 `sql` 和 `rows`。

```python
from app.services.nl2sql_service import nl2sql_query

result = await nl2sql_query("统计各月份订单数")
```

`read_only=True` 时当前实现只检查 SQL 去除首尾空白后是否以 `SELECT` 开头。这不是完整 SQL 安全解析或数据库权限隔离；生产使用还应限制数据库账号权限和查询范围，并避免将敏感数据暴露给不可信请求。
## HTTP 接口

`api/auth.py` 定义认证路由（需要先按“启动方式”挂载）：

| 方法 | 路径（挂载 `/api/v1` 后） | 功能 |
| --- | --- | --- |
| GET | `/api/v1/auth/public-access` | 返回无需登录的页面/模块清单。 |
| POST | `/api/v1/auth/login` | 校验用户名密码并签发 Bearer Token。 |
| GET | `/api/v1/auth/me/access` | 认证当前用户并返回其身份、权限、可访问页面/模块。 |

登录请求体示例：

```json
{"username": "账号", "password": "密码"}
```

受保护请求头：`Authorization: Bearer <access_token>`。`schemas/auth.py` 将用户名限制为 1–64 个字符，密码限制为 1–256 个字符。

## 配置说明

应用从项目根目录 `.env` 读取配置。`config.py` 当前声明项如下：

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | 日志等级。 |
| `LOG_DIR` | 空 | 日志目录；空值时使用 `app/logs`。 |
| `DB_HOST` | `localhost` | MySQL 地址。 |
| `DB_PORT` | `3306` | MySQL 端口。 |
| `DB_USER` | `root` | 数据库用户名。 |
| `DB_PASSWORD` | `12345` | 数据库密码，部署时应改为安全凭据。 |
| `DB_NAME` | `education_agent` | 数据库名称。 |
| `DB_ECHO` | `false` | 是否输出 SQLAlchemy SQL 日志。 |
| `DIFY_API_BASE` | `http://127.0.0.1/v1` | Dify API 基础地址。 |
| `DIFY_API_KEY` | 空 | 旧版 NL2SQL 通用密钥兼容项；新部署建议配置场景密钥。 |
| `DIFY_SQL_OUTPUT_KEY` | `sql` | 旧版通用密钥对应的 NL2SQL 输出字段兼容项。 |
| `DIFY_API_TIMEOUT_SECONDS` | `60` | Dify HTTP 请求超时秒数。 |
| `DIFY_NL2SQL_API_KEY` | 空 | NL2SQL Workflow 专用 API Key；为空时回退旧版 `DIFY_API_KEY`。 |
| `DIFY_NL2SQL_OUTPUT_KEY` | 空（回退 `DIFY_SQL_OUTPUT_KEY`，默认 `sql`） | NL2SQL Workflow 的 SQL 输出变量名。 |

认证及访问策略代码还读取 `AUTH_SECRET_KEY`、`AUTH_TOKEN_EXPIRE_MINUTES`、`ACCESS_CONTROL_FILE`，但这些字段目前未在 `config.py` 的 `Settings` 中声明。使用对应认证/授权路径前需补齐配置定义并在 `.env` 设置强随机密钥和有效策略文件路径。

## 主要数据模型

`models/user_account.py` 定义统一账号 ORM `UserAccount`，身份类型对应 `admin`、`employee`、`customer`、`student`，账号可关联相应的员工、客户或学生记录。

`models/report.py` 定义报告模块三张表：

- `ReportConfig`：报告类型、周期、调度配置和启用状态。
- `ReportRecord`：报告生成记录、时间范围、状态、内容和指标快照。
- `ReportMetric`：可追溯/复算的指标明细。

模型只负责 ORM 映射；建表应由对应 SQL/迁移脚本执行。`REPORT_TABLES` 可供初始化脚本显式选择报告模块表。

## 当前实现范围与注意事项

- `api/` 当前有认证路由；报告、学生、客户等业务路由在 `main.py` 中仍是注释示例或尚未包含在当前目录。
- `tasks/` 当前只有包初始化文件，没有可直接调度的业务任务。
- `access_control.yaml` 的菜单和页面规则是访问清单元数据；所有受保护 API 仍应使用服务端依赖鉴权。
- `.env` 含秘密信息，不应提交到版本库；不要把数据库密码或 Dify 密钥复制到 README 或日志。
