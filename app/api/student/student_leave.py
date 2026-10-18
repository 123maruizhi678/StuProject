"""学生请假及教师审批、接管接口；统一装配到学生聚合路由。"""
from typing import Literal
from fastapi import APIRouter, Depends, Header, Query
from app.core.student.student_route import StudentRoute
from app.core.student.student_auth import get_principal, request_key
from app.core.common.response import BusinessException, success
from app.database import get_db
from app.clients.student.student_clients import get_query_client
from app.api.student.student_dependencies import get_service, read_scene

from app.schemas.student.student import AssignmentInput
from app.schemas.student.student_common import VersionInput
from app.schemas.student.student_leave import LeaveInput, LeaveDecision
from app.services.student.student_leave_service import StudentLeaveService, LeaveError
from app.services.student.student_assignments import StudentAssignments
from app.services.student.student_service import leave_public
from app.clients.student.student_assistant_dify import get_leave_workflow

router = APIRouter(route_class=StudentRoute)
internal_router = APIRouter(route_class=StudentRoute)

@router.delete("/leave/{apply_id}")
def withdraw_leave(
    apply_id: int,
    body: VersionInput,
    actor=Depends(get_principal),
    key=Depends(request_key),
    service=Depends(get_service),
):
    return success(service.withdraw_leave(actor, key, apply_id, body.expected_version))


@router.get("/leave")
def list_leave(
    actor=Depends(get_principal),
    service=Depends(get_service),
    query=Depends(get_query_client),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    approval_status: Literal["pending","approved","rejected","cancelled"] | None = None,
):
    return read_scene("leave", actor, service, query, limit=limit, offset=offset,approval_status=approval_status)


@router.get("/leave/{apply_id}")
def get_leave(
    apply_id: int,
    actor=Depends(get_principal),
    service=Depends(get_service),
    query=Depends(get_query_client),
):
    return read_scene("leave", actor, service, query, apply_id)


@internal_router.get("/leave")
def teacher_leave_list(
    status: Literal["pending", "approved", "rejected", "cancelled"] | None = Query(None,alias="approval_status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor=Depends(get_principal),
    service=Depends(get_service),
):
    return success(service.teacher_leaves(actor, status, limit, offset))


@internal_router.get("/leave/{apply_id}")
def teacher_leave_detail(
    apply_id: int, actor=Depends(get_principal), service=Depends(get_service)
):
    return success(leave_public(service.leave_for_teacher(actor, apply_id)))


@internal_router.post("/leave/{apply_id}/decision")
def teacher_leave_decision(
    apply_id: int,
    body: LeaveDecision,
    actor=Depends(get_principal),
    key=Depends(request_key),
    service=Depends(get_service),
):
    return success(service.decide_leave(actor, key, apply_id, body))


@router.post('/leave')
def submit_leave(body: LeaveInput, actor=Depends(get_principal), key=Depends(request_key), service=Depends(get_service)):
    return success(service.submit_leave(actor,key,body))


@internal_router.get('/leave/assignments')
def leave_assignments(actor=Depends(get_principal),db=Depends(get_db),limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0)):
    return success(StudentAssignments(db).list_assignments(actor,'leave',limit,offset))


@internal_router.post('/leave/{apply_id}/assign')
def assign_leave(apply_id:int,body:AssignmentInput,actor=Depends(get_principal),key=Depends(request_key),db=Depends(get_db)):
    return success(StudentAssignments(db).assign(actor,key,'leave',apply_id,body))

# 静态接管清单必须先于整数详情路由匹配。
internal_router.routes.sort(key=lambda route: 0 if route.path.endswith("/assignments") else 1)

def create_router(account_dependency, db_dependency, workflow_dependency=get_leave_workflow):
    router=APIRouter(prefix='/student',route_class=StudentRoute)
    @router.post('/leave')
    def submit_leave(payload:LeaveInput,request_key:str=Header(alias='Idempotency-Key',min_length=8,max_length=128,pattern=r'^[!-~]{8,128}$'),account=Depends(account_dependency),db=Depends(db_dependency),workflow=Depends(workflow_dependency)):
        try:
            return success(StudentLeaveService(db,workflow).submit(account,request_key,payload))
        except LeaveError as exc:
            raise BusinessException(exc.message,exc.status) from None
    return router
