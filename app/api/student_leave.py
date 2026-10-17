"""S01接入层；只复用组长统一身份与权限入口。"""
from typing import Annotated, Callable

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse

from app.core.common.response import fail, success
from app.clients.student_leave_dify import StudentLeaveDifyError, get_leave_workflow
from app.schemas.student_leave import LeaveInput, LeaveResponse
from app.services.student_leave_service import LeaveError, StudentLeaveService


def create_router(account_dependency: Callable, db_dependency: Callable,
                  workflow_dependency: Callable = get_leave_workflow) -> APIRouter:
    router = APIRouter(prefix="/student", tags=["学生助手 S01 AI辅助请假提交"])

    @router.post(
        "/leave", response_model=LeaveResponse, operation_id="student_leave_submit_s01",
        summary="S01 AI辅助请假提交",
        description="调用Dify生成理由摘要和审批关注点，再按本人身份提交待审批申请。",
        responses={401: {"description": "公共身份入口拒绝"},
                   403: {"description": "身份、权限或学生档案不可用"},
                   409: {"description": "幂等或关联冲突"},
                   502: {"description": "工作流失败或输出不符合约定，未提交"},
                   503: {"description": "工作流未配置、超时或不可用，未提交"}},
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
            return success(data)
        except (LeaveError, StudentLeaveDifyError) as error:
            return JSONResponse(
                status_code=error.status,
                content=fail(error.status, error.message),
            )

    return router
