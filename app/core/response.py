"""统一返回值格式工具。

对齐接口文档 1.3（响应格式）与 1.4（状态码）：
    {
        "code": 0,
        "message": "success",
        "data": {}
    }

对外暴露：
    - ResultCode        状态码常量
    - ResponseModel     统一返回模型（泛型，可用于 response_model 标注）
    - success / fail    便捷构造函数在业务/路由层调用
    - BusinessException 业务异常，由全局 handler 统一收敛为同一信封
    - register_exception_handlers  在 main.py 中调用，注册全局异常处理器
"""
from typing import Any, Generic, Optional, TypeVar

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.logger import get_logger

logger = get_logger("exception")

# 1. 状态码（对齐接口文档 1.4）
class ResultCode:
    """统一 API 响应信封使用的业务状态码常量。"""
    SUCCESS = 0
    PARAM_ERROR = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    SERVER_ERROR = 500


# 2. 统一返回模型
T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    """统一 API 响应模型，包含业务码、消息和泛型数据。"""
    code: int = ResultCode.SUCCESS
    message: str = "success"
    data: Optional[T] = None


# 3. 便捷函数：业务层 / 路由层直接调用
def success(data: Any = None, message: str = "success") -> dict:
    """构造统一格式的成功响应数据。"""
    return {"code": ResultCode.SUCCESS, "message": message, "data": data}


def fail(
    code: int = ResultCode.SERVER_ERROR,
    message: str = "error",
    data: Any = None,
) -> dict:
    """构造统一格式的失败响应数据。"""
    return {"code": code, "message": message, "data": data}


# 4. 业务异常：service 层 raise，统一被 handler 捕获
class BusinessException(Exception):
    """可由业务层抛出并交给统一异常处理器处理的异常。"""
    def __init__(
        self,
        message: str = "业务异常",
        code: int = ResultCode.SERVER_ERROR,
        data: Any = None,
    ) -> None:
        """初始化异常对象并保存业务码、消息和附加数据。"""
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


# 5. 全局异常处理器（在 main.py 中注册）
# 采用 HTTP 200 + {code,message,data} 应用信封的业务路径前缀（035 报告契约
# 与企业/学生一致）：400 参数、401 身份、403 权限、404 对象、409 冲突、
# 500 内部错误统一收敛为信封；网络、代理等非应用异常仍可能是非 200。
_ENVELOPE_PATH_PREFIXES = ("/api/v1/enterprise", "/api/v1/report")


def register_exception_handlers(app) -> None:
    """向 FastAPI 注册业务异常和未处理异常处理器。"""
    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        if request.url.path.startswith(_ENVELOPE_PATH_PREFIXES):
            # 不回显输入正文（可能包含敏感字段）。
            return JSONResponse(status_code=200, content=fail(400, "请求参数不符合接口约定", [
                {"loc": list(e["loc"]), "message": e["msg"]} for e in exc.errors()]))
        from fastapi.exception_handlers import request_validation_exception_handler
        return await request_validation_exception_handler(request, exc)

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request: Request, exc: StarletteHTTPException):
        if request.url.path.startswith(_ENVELOPE_PATH_PREFIXES):
            return JSONResponse(status_code=200, content=fail(exc.status_code, str(exc.detail)), headers=exc.headers)
        from fastapi.exception_handlers import http_exception_handler
        return await http_exception_handler(request, exc)

    @app.exception_handler(BusinessException)
    async def _biz_handler(_: Request, exc: BusinessException):
        """将业务异常转换为统一响应信封。"""
        return JSONResponse(
            status_code=200, content=fail(exc.code, exc.message, exc.data)
        )

    @app.exception_handler(Exception)
    async def _all_handler(_: Request, exc: Exception):
        """记录未处理异常并返回不泄露内部详情的通用错误。"""
        logger.exception("未捕获异常", exc_info=exc)
        return JSONResponse(
            status_code=200, content=fail(ResultCode.SERVER_ERROR, "服务器内部错误")
        )
