"""客服 Agent 业务逻辑。

职责：
    - 会话 / 消息落库（留资、审计）
    - 活动列表 / 详情查询
    - 活动报名（校验 + 防重 + 事务）
    - 课程列表查询（课程推荐分支数据源）
    - FAQ 兜底查询

写库类业务规则必须在后端实现，不交给 Dify。
"""
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.common.response import BusinessException, ResultCode
from app.models.agent import (
    ChatMessage,
    ChatSession,
    CourseProject,
    EventSignup,
    Faq,
    LectureEvent,
)
from app.services.agent.dify_client import AgentDifyError, get_dify_client

# 业务状态常量
EVENT_OPEN = "报名中"       # 活动可报名
SIGNUP_ACTIVE = "有效"      # 报名记录有效
COURSE_ON_SHELF = "上架"    # 课程上架


def _fmt(dt: datetime | None) -> str:
    """datetime 统一输出为 'YYYY-MM-DD HH:MM:SS'。"""
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""


# ---------- 对话 ----------
def run_chat(db: Session, session_id: str | None, user_id: str | None, message: str) -> dict:
    """取得回复后，在同一事务内保存会话及消息对；失败时回滚。"""
    message = (message or "").strip()
    if not message:
        raise BusinessException("消息不能为空", code=ResultCode.PARAM_ERROR)

    try:
        sid = _ensure_session(db, session_id, user_id)
        result = get_dify_client().chat(sid, message)
        # 原模型未声明消息到会话的外键关系，显式保证真实库中的父行先存在。
        db.flush()
        db.add(ChatMessage(session_id=sid, role="user", content=message, intent=""))
        db.add(ChatMessage(session_id=sid, role="assistant", content=result.reply, intent=result.intent))
        db.commit()
    except AgentDifyError as error:
        db.rollback()
        raise BusinessException(str(error), code=error.code) from None
    except Exception:
        db.rollback()
        raise

    return {
        "session_id": sid,
        "intent": result.intent,
        "reply": result.reply,
        "need_action": bool(result.action),
        "action": result.action,
    }


def _ensure_session(db: Session, session_id: str | None, user_id: str | None) -> str:
    """按 session_id 复用会话；不存在（或未传）则创建。"""
    sid = session_id or uuid.uuid4().hex
    existing = db.scalar(select(ChatSession).where(ChatSession.session_id == sid))
    if existing:
        return existing.session_id
    db.add(ChatSession(session_id=sid, user_id=user_id or "", channel="web"))
    return sid


# ---------- 活动 ----------
def list_events(db: Session, status: str | None = None) -> list[dict]:
    stmt = select(LectureEvent).order_by(LectureEvent.start_time.asc())
    if status:
        stmt = stmt.where(LectureEvent.status == status)
    return [_event_to_dict(e) for e in db.scalars(stmt).all()]


def get_event(db: Session, event_id: int) -> dict | None:
    e = db.get(LectureEvent, event_id)
    return _event_to_dict(e) if e else None


def _event_to_dict(e: LectureEvent) -> dict:
    return {
        "event_id": e.id,
        "event_name": e.event_name,
        "event_type": e.event_type,
        "start_time": _fmt(e.start_time),
        "location": e.location,
        "signup_method": e.signup_method,
        "quota": e.quota,
        "signed_count": e.signed_count,
        "status": e.status,
    }


# ---------- 报名 ----------
def signup(
    db: Session,
    event_id: int,
    customer_name: str,
    customer_phone: str,
    customer_info: dict | None = None,
) -> dict:
    """活动报名：校验活动状态与名额，防重复报名，事务内写库。"""
    event = db.get(LectureEvent, event_id)
    if not event:
        raise BusinessException("活动不存在", code=ResultCode.PARAM_ERROR)
    if event.status != EVENT_OPEN:
        raise BusinessException("活动不在报名中，无法报名", code=ResultCode.PARAM_ERROR)
    if event.quota > 0 and event.signed_count >= event.quota:
        raise BusinessException("活动名额已满", code=ResultCode.PARAM_ERROR)

    dup = db.scalar(
        select(EventSignup).where(
            EventSignup.event_id == event_id,
            EventSignup.customer_phone == customer_phone,
            EventSignup.status == SIGNUP_ACTIVE,
        )
    )
    if dup:
        raise BusinessException("您已报名该活动", code=ResultCode.PARAM_ERROR)

    now = datetime.now()
    signup = EventSignup(
        event_id=event_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_info=customer_info,
        signup_time=now,
        source="客服对话",
        status=SIGNUP_ACTIVE,
    )
    db.add(signup)
    event.signed_count += 1
    db.commit()
    return {"signup_id": signup.id, "signup_time": _fmt(now)}


# ---------- 课程 ----------
def list_courses(db: Session, category: str | None = None) -> list[dict]:
    stmt = (
        select(CourseProject)
        .where(CourseProject.status == COURSE_ON_SHELF)
        .order_by(CourseProject.id.asc())
    )
    if category:
        stmt = stmt.where(CourseProject.category == category)
    return [
        {
            "course_id": c.id,
            "course_name": c.course_name,
            "category": c.category,
            "target_audience": c.target_audience,
            "description": c.description,
            "location": c.location,
            "signup_method": c.signup_method,
        }
        for c in db.scalars(stmt).all()
    ]


# ---------- FAQ ----------
def search_faq(db: Session, question: str | None = None) -> dict | None:
    """FAQ 兜底：按问题关键词模糊匹配，无命中返回第一条。"""
    kw = (question or "").strip()
    if kw:
        row = db.scalar(
            select(Faq).where(Faq.question.like(f"%{kw}%")).order_by(Faq.id.asc()).limit(1)
        )
    else:
        row = None
    if row is None:
        row = db.scalar(select(Faq).order_by(Faq.id.asc()).limit(1))
    if row is None:
        return None
    return {"question": row.question, "answer": row.answer, "category": row.category}
