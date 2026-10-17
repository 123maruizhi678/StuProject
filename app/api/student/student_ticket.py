"""学生投诉与建议的提交、查询、回复、确认和评价接口。"""
from fastapi import APIRouter, Depends, Query
from app.core.student.student_route import StudentRoute
from app.core.student.student_auth import get_principal, request_key
from app.core.common.response import success
from app.clients.student.student_clients import get_query_client
from app.api.student.student_dependencies import get_service, read_scene


from app.schemas.student.student_ticket import TicketInput, TicketReply, TicketConfirm, RatingInput

router = APIRouter(route_class=StudentRoute)

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
