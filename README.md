# StuProject

StuProject 是基于 Python 3.11、FastAPI、SQLAlchemy 和 MySQL 的后端项目。代码包含认证与访问清单接口、学生助手业务路由、业务服务、同步逻辑和后台通知任务。Dify 可辅助自然语言交互；数据库写操作由后端固定业务逻辑执行。

## 项目结构

- `app/main.py`：创建 FastAPI 应用、初始化日志和访问策略、挂载认证路由、注册异常处理、定义状态接口及学生 OpenAPI 文档格式。
- `app/config.py`：定义 `.env` 配置及默认值，覆盖日志、MySQL 和 Dify 设置。
- `app/database.py`：构造同步 MySQL 引擎/会话工厂，提供请求级会话和连接池释放。
- `app/access_control.yaml`：角色权限、页面和模块访问元数据，详见下文配置说明。
- `app/api/`：HTTP 路由层。`auth.py` 提供登录和访问清单；`student.py` 提供学生自助与员工协作接口。
- `app/core/`：认证、授权、统一响应与异常、日志、Dify 客户端等基础组件。
- `app/models/`：SQLAlchemy 数据表映射，包括统一账号、学生模块表和企业共享表映射。
- `app/schemas/`：认证、学生请求及外部服务响应的数据校验模型。
- `app/services/`：认证、学生业务规则、固定查询、聊天动作确认、外部服务适配和数据同步。
- `app/tasks/student_tasks.py`：生成提醒并派发通知的独立后台任务。
- `app/logs/`：默认日志目录，可由 `LOG_DIR` 改写。
- `scripts/`、`tests/`、`dify/`、`业务文档/`：脚本、测试、工作流定义和项目文档。

## 安装与启动

```powershell
conda env create -f environment.yml
conda activate SST
uvicorn app.main:app --reload
```

启动后可在 `/docs` 查看已注册接口。当前 `app/main.py` 挂载认证路由；学生路由在 `app/api/student.py` 定义，需在应用入口注册后才会对外提供。后台任务由独立调度进程调用，启动 Web 服务不会自动周期运行任务。

## 环境配置

在项目根目录创建 `.env`。环境变量可覆盖 `app/config.py` 中的默认值；未声明的字段会被忽略。不要把真实数据库密码或 API Key 提交到版本库。

| 配置项 | 默认值 | 用途 |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | 日志等级，例如 `DEBUG`、`INFO`、`WARNING`、`ERROR`。 |
| `LOG_DIR` | 空 | 日志文件目录；留空时使用 `app/logs`。 |
| `DB_HOST` | `localhost` | MySQL 主机或地址。 |
| `DB_PORT` | `3306` | MySQL 端口。 |
| `DB_USER` | `root` | MySQL 用户名。 |
| `DB_PASSWORD` | `12345` | MySQL 密码；部署前请设置为安全的专用凭据。 |
| `DB_NAME` | `education_agent` | 数据库名称。 |
| `DB_ECHO` | `false` | 是否输出 SQLAlchemy SQL 调试日志。 |
| `DIFY_API_BASE` | `http://127.0.0.1/v1` | Dify API 基础地址。 |
| `DIFY_API_KEY` | 空 | Dify 应用密钥；调用工作流时配置。 |
| `DIFY_SQL_OUTPUT_KEY` | `sql` | NL2SQL 工作流中保存 SQL 的输出变量名。 |

`app/config.py` 当前仅声明上表字段；其他 `.env` 项会被忽略。请在启用认证令牌所需配置前核对认证服务与设置类中的字段定义。

## 认证接口

- `GET /api/v1/auth/public-access`：公开页面清单，无需登录。
- `POST /api/v1/auth/login`：以用户名和密码登录，返回 Bearer 访问令牌。
- `GET /api/v1/auth/me/access`：需要令牌，返回身份、权限以及可访问页面/模块。

受保护请求使用 `Authorization: Bearer <access_token>`。账号须预先存在于 `user_account` 表，密码应保存为 Argon2 哈希。当前没有注册、密码重置或登出接口。

## 学生助手

`app/api/student.py` 定义请假、服务工单、心理状态监测、提醒、通知、聊天动作确认、学业/进展查询，以及内部员工处理和数据同步路由。路由使用 `{code, message, data}` 响应信封；实际接口以挂载后的 `/docs` 为准。身份从令牌中解析，写操作交给固定业务服务处理，不将模型生成内容直接作为数据库写入语句执行。

## 访问策略配置

`app/access_control.yaml` 使用 YAML 定义：

- `version`：策略文件格式版本。
- `roles`：身份类型到权限标识集合的映射；`permissions` 列出该角色持有的权限。
- `pages`：页面 ID 到页面元数据的映射。`title` 是显示名称，`route` 是建议路由；`public: true` 表示公开页面，`requires_auth: true` 要求登录；`permission` 要求单项权限，`permission_any` 要求至少一项权限。
- `modules`：客户端功能模块元数据。`required_any` 要求列表中至少一项权限，`required_all` 要求全部权限；`pages` 列出模块关联页面 ID。

页面与模块设置用于生成访问清单，不会创建前端页面，也不能替代每个后端 API 的权限和数据归属校验。修改策略后重启服务以刷新进程缓存。

## 数据库与任务

`app/database.py` 使用同步 PyMySQL 驱动，不自动建表。按数据库初始化脚本和迁移说明准备数据库；执行含 `DROP TABLE` 的脚本前先审查影响并备份。学生共享表映射不应用于重建企业模块拥有的表。

`app/tasks/student_tasks.py` 使用数据库租约准备提醒、发送通知并处理失败重试，适合由单独调度进程周期调用。当前 FastAPI 启动流程不会自动调度它，通知发送还需要配置相应外部服务。