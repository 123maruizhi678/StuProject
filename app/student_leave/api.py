"""S01路由装配；可信账号依赖和数据库依赖由小组公共入口传入。"""
from typing import Annotated, Callable

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse

from .schemas import LeaveInput, LeaveResponse
from .service import LeaveError, StudentLeaveService


def create_router(account_dependency: Callable, db_dependency: Callable) -> APIRouter:
    router = APIRouter(prefix="/student", tags=["学生助手 S01 提交请假"])

    @router.post(
        "/leave", response_model=LeaveResponse, operation_id="student_leave_submit_s01",
        summary="S01 学生提交请假",
        description="身份由组长统一入口提供；本人提交、班主任分派、幂等及通知入队。",
        responses={403: {"description": "非学生或档案不可用"},
                   409: {"description": "幂等或关联冲突"},
                   401: {"description": "组长统一入口拒绝登录身份"}},
        openapi_extra={"x-response-convention": "http-status"},
    )
    def submit_leave(
        payload: LeaveInput,
        request_key: Annotated[str, Header(
            alias="Idempotency-Key", pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
        )],
        account=Depends(account_dependency),
        db=Depends(db_dependency),
    ):
        try:
            data = StudentLeaveService(db).submit(account, request_key, payload)
            return {"code": 0, "message": "success", "data": data}
        except LeaveError as error:
            return JSONResponse(status_code=error.status, content={
                "code": error.status, "message": error.message, "data": None,
            })

    return router
