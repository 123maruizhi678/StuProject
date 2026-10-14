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
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.logger import get_logger

logger = get_logger("exception")

# 1. 状态码（对齐接口文档 1.4）
class ResultCode:
    SUCCESS = 0
    PARAM_ERROR = 400
    UNAUTHORIZED = 401
    SERVER_ERROR = 500


# 2. 统一返回模型
T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    code: int = ResultCode.SUCCESS
    message: str = "success"
    data: Optional[T] = None


# 3. 便捷函数：业务层 / 路由层直接调用
def success(data: Any = None, message: str = "success") -> dict:
    return {"code": ResultCode.SUCCESS, "message": message, "data": data}


def fail(
    code: int = ResultCode.SERVER_ERROR,
    message: str = "error",
    data: Any = None,
) -> dict:
    return {"code": code, "message": message, "data": data}


# 4. 业务异常：service 层 raise，统一被 handler 捕获
class BusinessException(Exception):
    def __init__(
        self,
        message: str = "业务异常",
        code: int = ResultCode.SERVER_ERROR,
        data: Any = None,
    ) -> None:
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


# 5. 全局异常处理器（在 main.py 中注册）
def register_exception_handlers(app) -> None:
    @app.exception_handler(BusinessException)
    async def _biz_handler(_: Request, exc: BusinessException):
        return JSONResponse(
            status_code=200, content=fail(exc.code, exc.message, exc.data)
        )

    @app.exception_handler(Exception)
    async def _all_handler(_: Request, exc: Exception):
        logger.exception("未捕获异常", exc_info=exc)
        return JSONResponse(
            status_code=200, content=fail(ResultCode.SERVER_ERROR, "服务器内部错误")
        )
