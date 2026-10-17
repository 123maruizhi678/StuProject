"""FastAPI 应用入口：初始化、中间件、路由注册、全局异常处理。"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.config import BASE_DIR
from app.api.common.auth import router as auth_router
from app.core.common.authorization import load_access_control, require_permission
from app.core.common.logger import get_logger, init_logger
from app.core.common.response import register_exception_handlers, success
from app.database import dispose_db, get_db

init_logger()
logger = get_logger(__name__)

# 仍停留在历史扁平布局、尚未迁入按业务模块分包结构的模块（目录架构归位中）。
# 智能报告已迁入 app/api/report 包，不在此列。
# 此集合只跟踪目录迁移；客服路由已挂载，不代表其中模块均未启用。
MIGRATION_PENDING_MODULES = {
    "agent",
    "customer",
    "enterprise",
    "enterprise_student",
    "student",
    "student_leave",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期回调：启动时校验访问策略，关闭时释放数据库连接池。"""
    logger.info("数据库初始化中...")
    load_access_control()
    yield
    logger.info("释放数据库连接池...")
    dispose_db()


logger.info("StuProject 启动中...")
app = FastAPI(title="StuProject", version="1.0.0", lifespan=lifespan)
# CORS 当前为开发配置，生产环境应按实际前端域名收紧来源、方法和请求头。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)
app.include_router(auth_router, prefix="/api/v1")

# 客服六接口允许匿名访问；业务数据读写由客服服务负责。
from app.api.agent import router as agent_router

app.include_router(agent_router, prefix="/api/v1")

# enterprise_student 仍为历史扁平模块且尚未就绪：缺失时不阻塞应用装配，
# 迁移归位后随 MIGRATION_PENDING_MODULES 收敛移除本兼容分支。
try:
    from app.api.enterprise_student import router as enterprise_student_router
except ModuleNotFoundError:
    enterprise_student_router = None
if enterprise_student_router is not None:
    app.include_router(enterprise_student_router, prefix="/api/v1")

# S01仅接入学生请假；登录和权限判断复用组长公共依赖。
# student_leave 仍在目录迁移中（扁平文件与其客户端未齐）：缺失时不阻塞装配，
# 迁移归位（app/clients/student 等就绪）后随 MIGRATION_PENDING_MODULES 收敛。
try:
    from app.api.student_leave import create_router as create_student_leave_router

    app.include_router(
        create_student_leave_router(
            require_permission("student.admin_service.create"), get_db
        ),
        prefix="/api/v1",
    )
except ModuleNotFoundError as exc:
    logger.warning("student_leave 路由暂未挂载（迁移中）：%s", exc.name)

# 路由注册（各业务模块就绪后在此 include，挂载到 /api/v1）
# from app.api import customer, enterprise, student
# app.include_router(customer.router, prefix="/api/v1")
# app.include_router(enterprise.router, prefix="/api/v1")
# app.include_router(student.router, prefix="/api/v1")

# 智能报告：已按业务模块分包迁入 app/api/report，五接口挂载到 /api/v1/report。
from app.api.report import router as report_router

app.include_router(report_router, prefix="/api/v1")

FRONTEND_DIR = BASE_DIR / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/health")
def root():
    """提供公开的根路径服务状态响应。"""
    return success({"service": "StuProject"})


@app.get("/", include_in_schema=False)
@app.get("/account", include_in_schema=False)
def workspace_page():
    """统一主入口；页面可见性不替代各业务接口的认证与权限校验。"""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(FRONTEND_DIR / "common" / "login.html")


# 学生路由沿用小组HTTP 200 + code信封；仅修正这些路由的OpenAPI描述。
from fastapi.openapi.utils import get_openapi


def student_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    for path, operations in schema.get("paths", {}).items():
        if not path.startswith((
            "/api/v1/student",
            "/api/v1/internal/student",
            "/api/v1/enterprise",
            "/api/v1/report",
        )):
            continue
        for operation in operations.values():
            if not isinstance(operation, dict) or "responses" not in operation:
                continue
            if operation.get("x-response-convention") == "http-status":
                continue
            operation["responses"].pop("422", None)
            operation["responses"]["200"] = {
                "description": "统一信封：code=0成功；400参数、401身份、403权限、404不存在、409冲突、503依赖不可用。HTTP状态沿用小组现有200约定。",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["code", "message", "data"],
                            "properties": {
                                "code": {"type": "integer"},
                                "message": {"type": "string"},
                                "data": {},
                            },
                        }
                    }
                },
            }
    app.openapi_schema = schema
    return schema


app.openapi = student_openapi
