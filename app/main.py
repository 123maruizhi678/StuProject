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

# 路由注册（各业务模块就绪后在此 include，挂载到 /api/v1）
# from app.api import customer, agent, enterprise, student, report
# app.include_router(customer.router, prefix="/api/v1")
# app.include_router(agent.router, prefix="/api/v1")
# app.include_router(enterprise.router, prefix="/api/v1")
# app.include_router(student.router, prefix="/api/v1")
# app.include_router(report.router, prefix="/api/v1")


@app.get("/")
def root():
    return {"code": 0, "message": "success", "data": {"service": "StuProject"}}
