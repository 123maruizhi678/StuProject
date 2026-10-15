# StuProject

StuProject 是基于 Python 3.11、FastAPI 和 MySQL 的后端项目。当前代码包含应用入口、数据库连接与会话管理、日志、Dify 客户端和 NL2SQL 服务；业务路由仍在逐步接入。

## 项目结构

- app/main.py：FastAPI 应用入口、生命周期、CORS、异常处理和路由注册。
- app/config.py：从项目根目录的 .env 加载配置。
- app/database.py：SQLAlchemy MySQL 引擎、请求级数据库会话和连接池释放。
- app/api/：HTTP 路由；目前包含认证路由。
- app/core/：认证、权限校验、日志、Dify 客户端和统一异常处理。
- app/models/：ORM 模型；包含统一账号 user_account。
- app/schemas/：API 请求/响应结构。
- app/services/：业务服务；包含认证和 NL2SQL。
- app/tasks/：后台任务包，目前没有具体任务。
- app/logs/：本地日志目录，已加入 Git 忽略。
- app/access_control.yaml：身份权限及前端页面、模块访问规则。
- scripts/sql/all.sql：数据库建表脚本。脚本会删除并重建清单中的表，运行前需备份数据。

## 认证与授权

认证使用 Bearer Token。用户账号必须已存在于 MySQL 的 user_account 表中。

### 获取公开页面

    GET /api/v1/auth/public-access

此接口无需登录，返回标记为 public 或 requires_auth=false 的页面元数据，可供前端在登录前识别公开页面。

### 登录

    POST /api/v1/auth/login

请求 JSON：

    {"username": "账号", "password": "密码"}

成功后返回 access_token、token_type 和 expires_in。调用受保护接口时，在请求头中传入：

    Authorization: Bearer <access_token>

### 获取当前用户可访问的页面与模块

    GET /api/v1/auth/me/access

接口根据数据库中 user_account.identity_type 读取身份，并按照 app/access_control.yaml 返回：

- identity_type：管理员、员工、客户或学生身份。
- permissions：允许调用的权限标识。
- pages：当前账号可访问的页面元数据，包含公开页面。
- modules：前端可展示的功能模块元数据。

配置中的 public 页面不需要登录；设置 requires_auth 的页面需要登录；页面可通过 permission 或 permission_any 指定进一步的权限要求。模块通过 required_any / required_all 权限条件决定是否返回。页面 ID、路由和模块元数据不会自动创建前端路由或页面。

当前仓库没有前端目录或前端框架配置，因此本次只实现后端访问清单接口和配置，不创建前端业务页面或框架专属文件。前端可使用返回的 pages/modules 构建菜单和路由守卫。

前端隐藏菜单或拦截页面跳转不能替代后端鉴权。每个受保护的业务 API 都必须校验权限；访问个人记录时还必须验证数据归属。

### 保护业务 API

在业务路由上声明权限标识：

    from typing import Annotated
    from fastapi import Depends
    from app.core.authorization import require_permission
    from app.models.user_account import UserAccount

    @router.get("/students")
    def list_students(
        account: Annotated[UserAccount, Depends(require_permission("student.profile.read"))],
    ):
        ...

权限标识应先加入 app/access_control.yaml 对应身份的 permissions，再由 API 路由引用。当前 admin 角色仅配置 admin.dashboard；管理员业务接口权限需按接口逐项授权。当前项目尚未接入学生、客户、员工等业务路由。

## 配置

在项目根目录 .env 中配置：

- DB_HOST、DB_PORT、DB_USER、DB_PASSWORD、DB_NAME：MySQL 连接。
- AUTH_SECRET_KEY：JWT 签名密钥，至少 32 字节；必须保密，不要提交 .env。
- AUTH_TOKEN_EXPIRE_MINUTES：令牌有效期，默认 60 分钟。
- ACCESS_CONTROL_FILE：可选，覆盖默认的 app/access_control.yaml 路径。
- DIFY_API_BASE、DIFY_API_KEY、DIFY_SQL_OUTPUT_KEY：Dify 工作流配置。
- LOG_LEVEL、LOG_DIR：日志配置。

可用下面的命令生成随机签名密钥：

    python -c "import secrets; print(secrets.token_urlsafe(48))"

账号密码使用 Argon2 哈希，不能存储明文。app.services.auth_service.hash_password 可用于账号创建流程。当前没有账号注册、密码重置或退出登录接口。

修改访问策略文件后重启服务，使缓存的配置重新加载。

## 数据库

先配置 MySQL 并创建数据库表。app/models/user_account.py 只映射已有 user_account 表，不负责建表或迁移。运行 scripts/sql/all.sql 前请检查其中的 DROP TABLE 语句并备份数据，因为它会删除后重建清单中的表。

## 安装与运行

在项目根目录执行：

    conda env create -f environment.yml
    conda activate SST

配置好 .env 后启动：

    uvicorn app.main:app --reload

服务运行后可通过 /docs 查看 FastAPI 接口文档。
