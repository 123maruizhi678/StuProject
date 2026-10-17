"""FastAPI 应用入口：初始化、中间件、路由注册、全局异常处理。

本次提交范围：仅「客服Agent」模块。
其他模块（登录鉴权 / 学生请假 S01 / 智能报告 / 企业智能助手）的导入与路由
挂载已整体注释——模块文件均未删除，需要恢复时取消对应注释即可。
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent import router as agent_router
from app.core.authorization import load_access_control
from app.core.logger import get_logger, init_logger
from app.core.response import register_exception_handlers
from app.database import dispose_db

# ===== 本次不提交的模块，导入暂注释（恢复时取消注释）=====
# from app.api.auth import router as auth_router
# from app.api.student_leave import create_router as create_student_leave_router
# from app.api import report
# from app.api.enterprise_student import router as enterprise_student_router  # 模块尚未创建
# from app.database import get_db  # 仅学生请假路由工厂需要

init_logger()
logger = get_logger(__name__)


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

# ===== 本次不提交的模块，路由挂载暂注释（恢复时取消注释）=====
# app.include_router(auth_router, prefix="/api/v1")
# app.include_router(
#     create_student_leave_router(
#         require_permission("student.admin_service.create"), get_db
#     ),
#     prefix="/api/v1",
# )
# app.include_router(report.router, prefix="/api/v1")
# app.include_router(enterprise_student_router, prefix="/api/v1")  # 模块尚未创建

# 客服 Agent：对话（后端调 Dify）/ 活动 / 报名 / 课程 / FAQ
app.include_router(agent_router, prefix="/api/v1")

# 路由注册（其他业务模块就绪后在此 include，挂载到 /api/v1）
# from app.api import customer, enterprise, student
# app.include_router(customer.router, prefix="/api/v1")
# app.include_router(enterprise.router, prefix="/api/v1")
# app.include_router(student.router, prefix="/api/v1")


@app.get("/")
def root():
    """提供公开的根路径服务状态响应。"""
    return {"code": 0, "message": "success", "data": {"service": "StuProject"}}


# 学生路由沿用小组HTTP 200 + code信封；仅修正这些路由的OpenAPI描述。
from fastapi.openapi.utils import get_openapi


def student_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    for path, operations in schema.get("paths", {}).items():
        if not path.startswith(("/api/v1/student", "/api/v1/internal/student", "/api/v1/enterprise")):
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
