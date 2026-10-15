"""S05—S08：公共鉴权依赖注入，路由只负责输入输出。"""
from typing import Annotated, Callable

from fastapi import APIRouter, Depends, Header, Path, Query
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.clients.student_ticket_dify import get_ticket_workflow
from app.repositories.student_schema import StudentSchemaError
from app.schemas.student_ticket import (ComplaintInput, TicketResponse, TicketDetailResponse,
                                        TicketListResponse, TicketRecordsResponse)
from app.services.student_leave_service import LeaveError
from app.services.student_ticket_service import StudentTicketService


def create_router(create_account_dependency: Callable, read_account_dependency: Callable,
                  db_dependency: Callable, workflow_dependency: Callable = get_ticket_workflow):
    router = APIRouter(prefix="/student", tags=["学生助手 投诉与建议"],
                       responses={403: {"description": "学生身份或权限不可用"},
                                  404: {"description": "工单不存在或无权访问"},
                                  409: {"description": "幂等冲突或部门不可用"},
                                  503: {"description": "数据库或共享表结构不可用"}})

    def run(db, action):
        try:
            return {"code": 0, "message": "success", "data": action()}
        except (LeaveError, StudentSchemaError) as error:
            db.rollback()
            return JSONResponse(status_code=error.status, content={
                "code": error.status, "message": error.message, "data": None})
        except SQLAlchemyError:
            db.rollback()
            return JSONResponse(status_code=503, content={
                "code": 503, "message": "工单数据库暂不可用，请稍后重试或核验共享表结构", "data": None})

    @router.post("/complaint", response_model=TicketResponse, summary="S05 提交投诉或建议并提炼摘要",
                 operation_id="student_ticket_submit_s05", openapi_extra={"x-response-convention": "http-status"})
    def submit_complaint(
        payload: ComplaintInput,
        request_key: Annotated[str, Header(alias="Idempotency-Key", pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")],
        account=Depends(create_account_dependency), db=Depends(db_dependency), workflow=Depends(workflow_dependency),
    ):
        return run(db, lambda: StudentTicketService(db, workflow).submit(account, request_key, payload))

    @router.get("/tickets", response_model=TicketListResponse, summary="S06 查询本人工单",
                openapi_extra={"x-response-convention": "http-status"})
    def tickets(account=Depends(read_account_dependency), db=Depends(db_dependency),
                limit: int = Query(20, ge=1, le=100), before_id: int | None = Query(None, gt=0)):
        return run(db, lambda: StudentTicketService(db).list_own(account, limit, before_id))

    @router.get("/tickets/{ticket_id}", response_model=TicketDetailResponse, summary="S07 查询本人工单详情",
                openapi_extra={"x-response-convention": "http-status"})
    def ticket_detail(ticket_id: Annotated[int, Path(gt=0)],
                      account=Depends(read_account_dependency), db=Depends(db_dependency)):
        return run(db, lambda: StudentTicketService(db).detail(account, ticket_id))

    @router.get("/tickets/{ticket_id}/records", response_model=TicketRecordsResponse, summary="S08 查询本人可见沟通记录",
                openapi_extra={"x-response-convention": "http-status"})
    def ticket_records(ticket_id: Annotated[int, Path(gt=0)], account=Depends(read_account_dependency),
                       db=Depends(db_dependency), limit: int = Query(20, ge=1, le=100),
                       after_id: int = Query(0, ge=0)):
        return run(db, lambda: StudentTicketService(db).records(account, ticket_id, limit, after_id))

    return router
