"""S01接入层；只复用组长统一身份与权限入口。"""
from typing import Annotated, Callable

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.clients.student_leave_dify import StudentLeaveDifyError, get_leave_workflow
from app.schemas.student_leave import LeaveInput, LeaveResponse
from app.services.student_leave_service import LeaveError, StudentLeaveService
from app.repositories.student_schema import StudentSchemaError


def create_router(account_dependency: Callable, db_dependency: Callable,
                  workflow_dependency: Callable = get_leave_workflow) -> APIRouter:
    router = APIRouter(prefix="/student", tags=["学生助手 S01 请假提交"])

    @router.post(
        "/leave", response_model=LeaveResponse, operation_id="student_leave_submit_s01",
        summary="S01 请假提交（可选AI摘要）",
        description="固定后端提交本人申请；默认不调用模型。可选AI失败仍保留原始申请。",
        responses={401: {"description": "公共身份入口拒绝"},
                   403: {"description": "身份、权限或学生档案不可用"},
                   409: {"description": "幂等或关联冲突"},
                   503: {"description": "共享表结构或数据库不可用"}},
        openapi_extra={"x-response-convention": "http-status"},
    )
    def submit_leave(
        payload: LeaveInput,
        request_key: Annotated[str, Header(
            alias="Idempotency-Key", pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
        )],
        account=Depends(account_dependency), db=Depends(db_dependency),
        workflow=Depends(workflow_dependency),
    ):
        try:
            data = StudentLeaveService(db, workflow).submit(account, request_key, payload)
            return {"code": 0, "message": "success", "data": data}
        except (LeaveError, StudentLeaveDifyError, StudentSchemaError) as error:
            db.rollback()
            return JSONResponse(status_code=error.status, content={
                "code": error.status, "message": error.message, "data": None,
            })
        except SQLAlchemyError:
            db.rollback()
            return JSONResponse(status_code=503, content={
                "code": 503, "message": "请假数据库暂不可用，请核验共享表结构", "data": None,
            })

    return router
