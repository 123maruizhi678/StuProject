"""公共登录与权限入口的唯一应用装配。"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.api.common.auth import router as auth_router
from app.config import BASE_DIR, settings
from app.core.common.authorization import load_access_control
from app.core.common.logger import get_logger
from app.core.common.response import register_exception_handlers, success
from app.database import dispose_db

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_access_control()
    logger.info("公共登录与权限入口已启动")
    try:
        yield
    finally:
        dispose_db()


app = FastAPI(title="StuProject 公共登录与权限入口", version="1.0.0", lifespan=lifespan)
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=False,
        allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"],
    )
register_exception_handlers(app)
app.include_router(auth_router, prefix="/api/v1")
app.mount("/static", StaticFiles(directory=BASE_DIR / "frontend"), name="static")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE_DIR / "frontend" / "index.html")


@app.get("/login", include_in_schema=False)
@app.get("/account", include_in_schema=False)
def login_page():
    return FileResponse(BASE_DIR / "frontend" / "common" / "login.html")


@app.get("/health", tags=["公共服务"])
def health():
    return success({"service": "StuProject", "module": "common"})


# 学生模块共用公共认证、异常信封与唯一应用入口。
from app.api.student.student import router as student_router, internal_router
app.include_router(student_router)
app.include_router(internal_router)


@app.get("/student-assistant", include_in_schema=False)
def student_page():
    return FileResponse(BASE_DIR / "frontend" / "student" / "student-assistant.html")
