"""客服 Agent 路由。

对齐《接口设计文档》第三章（修改后）：
    POST /agent/chat            客服对话（含会话/消息落库）
    GET  /agent/events          活动列表
    GET  /agent/events/{id}     活动详情
    POST /agent/events/signup   活动报名（校验 + 防重 + 事务）
    GET  /agent/courses         课程列表
    GET  /agent/faq             FAQ 兜底查询
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.common.response import BusinessException, ResponseModel, ResultCode, success
from app.database import get_db
from app.schemas.agent import (
    ChatData,
    ChatRequest,
    CourseItem,
    EventItem,
    FaqData,
    SignupData,
    SignupRequest,
)
from app.services.agent import agent_service

router = APIRouter(prefix="/agent", tags=["客服Agent"])


@router.post("/chat", response_model=ResponseModel[ChatData], summary="客服对话")
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    data = agent_service.run_chat(db, req.session_id, req.user_id, req.message)
    return success(data=data)


@router.get("/events", response_model=ResponseModel[list[EventItem]], summary="活动列表")
def list_events(
    status: str | None = Query(None, description="活动状态筛选，如：报名中"),
    db: Session = Depends(get_db),
):
    return success(data=agent_service.list_events(db, status))


@router.get("/events/{event_id}", response_model=ResponseModel[EventItem], summary="活动详情")
def get_event(event_id: int, db: Session = Depends(get_db)):
    data = agent_service.get_event(db, event_id)
    if data is None:
        raise BusinessException("活动不存在", code=ResultCode.PARAM_ERROR)
    return success(data=data)


@router.post("/events/signup", response_model=ResponseModel[SignupData], summary="活动报名")
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    data = agent_service.signup(
        db, req.event_id, req.customer_name, req.customer_phone, req.customer_info
    )
    return success(data=data)


@router.get("/courses", response_model=ResponseModel[list[CourseItem]], summary="课程列表")
def list_courses(
    category: str | None = Query(None, description="课程类别筛选，如：语言培训"),
    db: Session = Depends(get_db),
):
    return success(data=agent_service.list_courses(db, category))


@router.get("/faq", response_model=ResponseModel[FaqData], summary="FAQ 兜底查询")
def faq(
    question: str | None = Query(None, description="问题关键词"),
    db: Session = Depends(get_db),
):
    data = agent_service.search_faq(db, question)
    if data is None:
        raise BusinessException("未找到相关问答", code=ResultCode.PARAM_ERROR)
    return success(data=data)
