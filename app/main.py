"""FastAPI 应用入口：初始化、中间件、路由注册、全局异常处理。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logger import get_logger, init_logger
from app.core.response import register_exception_handlers
from app.database import dispose_db

# 最先加载日志，保证后续所有模块输出都被捕获
init_logger()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("数据库初始化中...")
    yield
    logger.info("释放数据库连接池...")
    dispose_db()


logger.info("StuProject 启动中...")
app = FastAPI(title="StuProject", version="1.0.0", lifespan=lifespan)

# 跨域中间件（开发阶段放开，生产按需收紧）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局异常处理器：统一收敛为 {code, message, data} 信封
register_exception_handlers(app)

from app.api.student import (
    router as student_router,
    internal_router as student_internal_router,
)

app.include_router(student_router)
app.include_router(student_internal_router)

# 其他组员的路由由各自模块注册
# from app.api import customer, agent, enterprise, student, report
# app.include_router(customer.router, prefix="/api/v1")
# app.include_router(agent.router, prefix="/api/v1")
# app.include_router(enterprise.router, prefix="/api/v1")
# app.include_router(student.router, prefix="/api/v1")
# app.include_router(report.router, prefix="/api/v1")


@app.get("/")
def root():
    return {"code": 0, "message": "success", "data": {"service": "StuProject"}}


# 学生路由沿用小组HTTP 200 + code信封；仅修正这些路由的OpenAPI描述。
from fastapi.openapi.utils import get_openapi


def student_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    for path, operations in schema.get("paths", {}).items():
        if not path.startswith(("/api/v1/student", "/api/v1/internal/student")):
            continue
        for operation in operations.values():
            if not isinstance(operation, dict) or "responses" not in operation:
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
