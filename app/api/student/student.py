"""学生助手 HTTP 路由：提供学生自助业务，以及教师/员工侧请假、通知、预警和同步协作接口。"""

from typing import Literal
from fastapi import APIRouter, Depends, Query
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from app.repositories.student.student_schema import StudentSchemaError
from pydantic import ValidationError
from app.database import get_db
from app.core.common.response import success, BusinessException
from app.core.student.student_auth import get_principal, get_sync_principal, request_key
from app.schemas.student.student import (
    LeaveInput,
    LeaveDecision,
    TicketInput,
    TicketReply,
    TicketConfirm,
    RatingInput,
    ReminderInput,
    ReminderCancel,
    MentalInput,
    VersionInput,
    WarningInput,
    ChatInput,
    ConfirmInput,
    AcademicBatch,
    ProgressBatch,
    SyncRequest,
)
from app.services.student.student_service import StudentService, warnings, public_row, leave_public
from app.clients.student.student_clients import get_dify, get_query_client, get_source_client
from app.services.student.student_chat import StudentChatService
from app.services.student.student_sync import StudentSyncService


class StudentRoute(APIRoute):
    """仅学生路由适配统一错误信封，不修改其他组员的异常处理行为。"""

    def get_route_handler(self):
        original = super().get_route_handler()

        async def handle(request):
            try:
                return await original(request)
            except RequestValidationError as exc:
                details = [
                    {"loc": list(e["loc"]), "type": e["type"]} for e in exc.errors()
                ]
                return JSONResponse(status_code=200, content=
                    {"code": 400, "message": "请求参数不符合要求", "data": details}
                )
            except BusinessException as exc:
                return JSONResponse(status_code=200,content={'code':exc.code,'message':exc.message,'data':None})
            except HTTPException as exc:
                return JSONResponse(status_code=200, content={"code":exc.status_code,"message":"身份或权限不可用","data":None})
            except StudentSchemaError as exc:
                return JSONResponse(status_code=200,content={"code":503,"message":exc.message,"data":None})
            except SQLAlchemyError:
                # 不记录SQL参数和连接异常原文，防止心理原文、密码进入日志。
                return JSONResponse(status_code=200, content=
                    {"code": 503, "message": "学生数据服务暂不可用", "data": None}
                )

            except Exception:
                return JSONResponse(status_code=200, content={"code":500,"message":"学生服务内部错误","data":None})

        return handle


router = APIRouter(
    route_class=StudentRoute, prefix="/api/v1/student", tags=["学生助手"]
)
internal_router = APIRouter(
    route_class=StudentRoute,
    prefix="/api/v1/internal/student",
    tags=["学生助手内部协作"],
)


def get_service(db=Depends(get_db)):
    return StudentService(db)



@router.delete("/leave/{apply_id}")
def withdraw_leave(
    apply_id: int,
    body: VersionInput,
    actor=Depends(get_principal),
    key=Depends(request_key),
    service=Depends(get_service),
):
    return success(service.withdraw_leave(actor, key, apply_id, body.expected_version))



@router.post("/tickets/{ticket_id}/reply")
def reply_ticket(
    ticket_id: int,
    body: TicketReply,
    actor=Depends(get_principal),
    key=Depends(request_key),
    service=Depends(get_service),
):
    return success(service.ticket_reply(actor, key, ticket_id, body))


@router.post("/tickets/{ticket_id}/confirm")
def confirm_ticket(
    ticket_id: int,
    body: TicketConfirm,
    actor=Depends(get_principal),
    key=Depends(request_key),
    service=Depends(get_service),
):
    return success(service.confirm_ticket(actor, key, ticket_id, body))


@router.post("/tickets/{ticket_id}/rating")
def rate_ticket(
    ticket_id: int,
    body: RatingInput,
    actor=Depends(get_principal),
    key=Depends(request_key),
    service=Depends(get_service),
):
    return success(service.rate_ticket(actor, key, ticket_id, body))


@router.post("/mental/monitor")
def mental_monitor(
    body: MentalInput,
    actor=Depends(get_principal),
    key=Depends(request_key),
    service=Depends(get_service),
    dify=Depends(get_dify),
):
    return success(StudentChatService(service,dify,None).monitor(actor,key,body))


@router.post("/reminders")
def set_reminder(
    body: ReminderInput,
    actor=Depends(get_principal),
    key=Depends(request_key),
    service=Depends(get_service),
):
    return success(service.set_reminder(actor, key, body))


@router.delete("/reminders/{reminder_id}")
def cancel_reminder(
    reminder_id: int,
    body: ReminderCancel,
    actor=Depends(get_principal),
    key=Depends(request_key),
    service=Depends(get_service),
):
    return success(service.cancel_reminder(actor, key, reminder_id, body))


@router.post("/notifications/{notification_id}/read")
def read_notification(
    notification_id: int,
    actor=Depends(get_principal),
    key=Depends(request_key),
    service=Depends(get_service),
):
    return success(service.read_notification(actor, key, notification_id))


@router.post("/chat")
def student_chat(
    body: ChatInput,
    actor=Depends(get_principal),
    key=Depends(request_key),
    service=Depends(get_service),
    dify=Depends(get_dify),
    query=Depends(get_query_client),
):
    return success(StudentChatService(service, dify, query).chat(actor, key, body))


@router.post("/actions/confirm")
def confirm_action(
    body: ConfirmInput,
    key=Depends(request_key),
    actor=Depends(get_principal),
    service=Depends(get_service),
    dify=Depends(get_dify),
    query=Depends(get_query_client),
):
    return success(
        StudentChatService(service, dify, query).confirm(actor, body.action_token, key)
    )


# 查询入口统一走组长的受控查询契约，不在学生模块生成或执行AI SQL。
def read_scene(scene, actor, service, query, entity_id=None, limit=20, offset=0, approval_status=None):
    service.student(actor)
    result=query.query(actor,scene,entity_id=entity_id,limit=limit,offset=offset,approval_status=approval_status)
    return success(result['items'][0] if entity_id is not None and scene in ('leave','tickets') else result)


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





@router.get("/academic")
def get_academic(
    actor=Depends(get_principal),
    service=Depends(get_service),
    query=Depends(get_query_client),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return read_scene("academic", actor, service, query, limit=limit, offset=offset)


@router.get("/progress")
def get_progress(
    actor=Depends(get_principal),
    service=Depends(get_service),
    query=Depends(get_query_client),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return read_scene("progress", actor, service, query, limit=limit, offset=offset)


@router.get("/reminders")
def get_reminders(
    actor=Depends(get_principal),
    service=Depends(get_service),
    query=Depends(get_query_client),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return read_scene("reminders", actor, service, query, limit=limit, offset=offset)


@router.get("/notifications")
def get_notifications(
    actor=Depends(get_principal),
    service=Depends(get_service),
    query=Depends(get_query_client),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread: bool | None = None,
):
    from app.services.student.student_notifications import list_own
    service.student(actor)
    return success(list_own(service.db,actor,limit,offset,unread))


# 企业侧只调用学生业务协作接口；企业页面及其他模块由对应负责人实现。
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


@internal_router.get("/notifications")
def teacher_notifications(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor=Depends(get_principal),
    service=Depends(get_service),
    unread: bool | None = None,
):
    from app.services.student.student_notifications import list_own
    service.employee(actor)
    return success(list_own(service.db,actor,limit,offset,unread))


@internal_router.post("/notifications/{notification_id}/read")
def teacher_read_notification(
    notification_id: int,
    actor=Depends(get_principal),
    key=Depends(request_key),
    service=Depends(get_service),
):
    return success(service.read_teacher_notification(actor, key, notification_id))


@internal_router.get("/warnings")
def teacher_warning_list(
    status: Literal["pending", "processing", "closed"] | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor=Depends(get_principal),
    service=Depends(get_service),
):
    return success(service.teacher_warnings(actor, status, limit, offset))


@internal_router.get("/warnings/{warning_id}")
def warning_detail(
    warning_id: int,
    actor=Depends(get_principal),
    service=Depends(get_service),
    query=Depends(get_query_client),
):
    service.employee(actor)
    row = service._load(warnings, warning_id, lock=False)
    if (
        not service.bound(actor.actor_id, row["student_id"])
    ) or row["follower_id"] != actor.actor_id:
        raise BusinessException("记录不存在", 404)
    result=query.warning(actor,warning_id,row["student_id"])
    result["history"]=service.warning_history(actor,warning_id)
    return success(result)


@internal_router.post("/warnings/{warning_id}/ack")
def ack_warning(
    warning_id: int,
    body: WarningInput,
    actor=Depends(get_principal),
    key=Depends(request_key),
    service=Depends(get_service),
):
    return success(service.handle_warning(actor, key, warning_id, "ack", body))


@internal_router.post("/warnings/{warning_id}/follow")
def follow_warning(
    warning_id: int,
    body: WarningInput,
    actor=Depends(get_principal),
    key=Depends(request_key),
    service=Depends(get_service),
):
    return success(service.handle_warning(actor, key, warning_id, "follow", body))


@internal_router.post("/warnings/{warning_id}/close")
def close_warning(
    warning_id: int,
    body: WarningInput,
    actor=Depends(get_principal),
    key=Depends(request_key),
    service=Depends(get_service),
):
    return success(service.handle_warning(actor, key, warning_id, "close", body))


@internal_router.post("/sync/academic")
def sync_academic(
    body: AcademicBatch,
    actor=Depends(get_sync_principal),
    key=Depends(request_key),
    db=Depends(get_db),
):
    return success(StudentSyncService(db).academic(actor, key, body))


@internal_router.post("/sync/progress")
def sync_progress(
    body: ProgressBatch,
    actor=Depends(get_sync_principal),
    key=Depends(request_key),
    db=Depends(get_db),
):
    return success(StudentSyncService(db).application(actor, key, body))


@internal_router.post("/sync/{kind}/pull")
def pull_source(
    kind: str,
    body: SyncRequest,
    actor=Depends(get_sync_principal),
    key=Depends(request_key),
    db=Depends(get_db),
    source=Depends(get_source_client),
):
    actor.require_scope("student:sync")
    service = StudentSyncService(db)
    if kind not in ("academic", "progress"):
        raise BusinessException("不支持的同步类型", 400)
    student = service.student_record(body.student_id)
    student = dict(student)
    db.rollback()
    payload = source.fetch(kind, student)
    try:
        batch = (AcademicBatch if kind == "academic" else ProgressBatch).model_validate(
            {
                "student_id": body.student_id,
                "source_system": payload["source_system"],
                "records": payload["records"],
            }
        )
    except (ValidationError, KeyError):
        raise BusinessException("外部数据不符合学生同步契约", 503) from None
    return success(
        service.academic(actor, key, batch)
        if kind == "academic"
        else service.application(actor, key, batch)
    )

for route in [*router.routes,*internal_router.routes]:
    route.openapi_extra = {'x-response-convention':'business-envelope'}


@router.post('/leave')
def submit_leave(body: LeaveInput, actor=Depends(get_principal), key=Depends(request_key), service=Depends(get_service)):
    return success(service.submit_leave(actor,key,body))

@router.post('/complaint')
def submit_complaint(body: TicketInput, actor=Depends(get_principal), key=Depends(request_key), service=Depends(get_service)):
    return success(service.submit_ticket(actor,key,body))

@router.get('/tickets')
def tickets(actor=Depends(get_principal), service=Depends(get_service), query=Depends(get_query_client), limit: int=Query(20,ge=1,le=100), offset: int=Query(0,ge=0)):
    return read_scene('tickets',actor,service,query,limit=limit,offset=offset)

@router.get('/tickets/{ticket_id}')
def ticket_detail(ticket_id: int, actor=Depends(get_principal), service=Depends(get_service), query=Depends(get_query_client)):
    return read_scene('tickets',actor,service,query,ticket_id)

@router.get('/tickets/{ticket_id}/records')
def ticket_records(ticket_id: int, actor=Depends(get_principal), service=Depends(get_service), query=Depends(get_query_client), limit: int=Query(20,ge=1,le=100), offset: int=Query(0,ge=0)):
    service._load(__import__('app.models.common',fromlist=['service_ticket']).service_ticket,ticket_id,actor,lock=False)
    return read_scene('ticket_records',actor,service,query,ticket_id,limit,offset)

@router.get('/courses')
def get_courses(actor=Depends(get_principal), service=Depends(get_service), query=Depends(get_query_client), limit: int=Query(20,ge=1,le=100), offset: int=Query(0,ge=0)):
    return read_scene('courses',actor,service,query,limit=limit,offset=offset)

@router.get('/scores')
def get_scores(actor=Depends(get_principal), service=Depends(get_service), query=Depends(get_query_client), limit: int=Query(20,ge=1,le=100), offset: int=Query(0,ge=0)):
    return read_scene('scores',actor,service,query,limit=limit,offset=offset)

@router.get('/notifications/{notification_id}')
def notification_detail(notification_id: int, actor=Depends(get_principal), service=Depends(get_service), query=Depends(get_query_client)):
    from app.services.student.student_notifications import detail
    service.student(actor)
    return success(detail(service.db,actor,notification_id))


from app.schemas.student.student import AssignmentInput
from app.services.student.student_assignments import StudentAssignments

@internal_router.get('/leave/assignments')
def leave_assignments(actor=Depends(get_principal),db=Depends(get_db),limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0)):
    return success(StudentAssignments(db).list_assignments(actor,'leave',limit,offset))

@internal_router.post('/leave/{apply_id}/assign')
def assign_leave(apply_id:int,body:AssignmentInput,actor=Depends(get_principal),key=Depends(request_key),db=Depends(get_db)):
    return success(StudentAssignments(db).assign(actor,key,'leave',apply_id,body))

@internal_router.get('/warnings/assignments')
def warning_assignments(actor=Depends(get_principal),db=Depends(get_db),limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0)):
    return success(StudentAssignments(db).list_assignments(actor,'warning',limit,offset))

@internal_router.post('/warnings/{warning_id}/assign')
def assign_warning(warning_id:int,body:AssignmentInput,actor=Depends(get_principal),key=Depends(request_key),db=Depends(get_db)):
    return success(StudentAssignments(db).assign(actor,key,'warning',warning_id,body))

# 静态接管列表先匹配，避免被整数详情路由吞掉。
internal_router.routes.sort(key=lambda route: 0 if route.path.endswith('/assignments') else 1)


from app.services.student.student_local_source import LocalStudentSource, LocalAcademic, LocalProgress
@internal_router.put('/academic/{student_id}')
def maintain_academic(student_id:int,body:LocalAcademic,actor=Depends(get_principal),key=Depends(request_key),db=Depends(get_db)):
    return success(LocalStudentSource(db).maintain(actor,key,student_id,'academic',body))

@internal_router.put('/progress/{student_id}')
def maintain_progress(student_id:int,body:LocalProgress,actor=Depends(get_principal),key=Depends(request_key),db=Depends(get_db)):
    return success(LocalStudentSource(db).maintain(actor,key,student_id,'progress',body))
