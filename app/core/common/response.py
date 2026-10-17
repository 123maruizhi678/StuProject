"""三字段信封；公共登录使用真实 HTTP 状态，业务协议按路径选择。"""
from typing import Any, Generic, TypeVar
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from app.core.common.logger import get_logger

logger = get_logger(__name__)
T = TypeVar("T")
_BUSINESS_PREFIXES = (
    "/api/v1/enterprise", "/api/v1/student", "/api/v1/internal/student", "/api/v1/report",
)


class ResultCode:
    SUCCESS = 0
    PARAM_ERROR = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    SERVER_ERROR = 500
    UNAVAILABLE = 503


class ResponseModel(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: T | None = None


def success(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


def fail(code: int = 500, message: str = "error", data: Any = None) -> dict:
    return {"code": code, "message": message, "data": data}


class BusinessException(Exception):
    def __init__(self, message: str = "业务异常", code: int = 500, data: Any = None):
        super().__init__(message)
        self.code, self.message, self.data = code, message, data


def _status(request: Request, code: int) -> int:
    path = request.url.path
    business_path = any(path == p or path.startswith(p + "/") for p in _BUSINESS_PREFIXES)
    route = request.scope.get("route")
    legacy_http = (getattr(route, "openapi_extra", None) or {}).get("x-response-convention") == "http-status"
    return 200 if business_path and not legacy_http else code


def register_exception_handlers(app) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, _: RequestValidationError):
        return JSONResponse(status_code=_status(request, 400), content=fail(400, "请求参数不符合接口约定"))

    @app.exception_handler(HTTPException)
    async def http_handler(request: Request, exc: HTTPException):
        message = exc.detail if isinstance(exc.detail, str) else "请求失败"
        return JSONResponse(status_code=_status(request, exc.status_code),
                            content=fail(exc.status_code, message), headers=exc.headers)

    @app.exception_handler(BusinessException)
    async def business_handler(request: Request, exc: BusinessException):
        return JSONResponse(status_code=_status(request, exc.code), content=fail(exc.code, exc.message, exc.data))

    @app.exception_handler(SQLAlchemyError)
    async def database_handler(request: Request, exc: SQLAlchemyError):
        logger.error("数据库依赖失败 method=%s error_type=%s", request.method, type(exc).__name__)
        return JSONResponse(status_code=_status(request, 503), content=fail(503, "数据库服务暂不可用"))

    @app.exception_handler(Exception)
    async def unexpected_handler(request: Request, exc: Exception):
        # 不记录可能包含密码、SQL 参数、Token 或业务原文的异常文本。
        logger.error("请求内部错误 method=%s error_type=%s", request.method, type(exc).__name__)
        return JSONResponse(status_code=_status(request, 500), content=fail(500, "服务器内部错误"))
