"""研判业务异常，复用公共业务信封。"""
from app.core.common.response import BusinessException


class BadRequestError(BusinessException):
    def __init__(self, message):
        super().__init__(message, code=400)


class ForbiddenError(BusinessException):
    def __init__(self, message):
        super().__init__(message, code=403)


class NotFoundError(BusinessException):
    def __init__(self, message):
        super().__init__(message, code=404)


class ConflictError(BusinessException):
    def __init__(self, message):
        super().__init__(message, code=409)
