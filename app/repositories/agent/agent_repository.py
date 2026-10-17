"""客服 Agent 六表数据访问。

对应《开发文档/操作文档.md》第一章：会话 / 消息、活动、报名、课程、FAQ
均以数据库事实为准；Dify 只生成话术与动作，不直接写业务库。

所有函数只做读写，不 commit；事务边界由 `app.services.agent.agent_service`
显式控制（对齐操作文档“客服消息持久化与模型调用的事务顺序”）。
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent.agent import (
    ChatMessage,
    ChatSession,
    CourseProject,
    EventSignup,
    Faq,
    LectureEvent,
)

# ---------- 会话 / 消息 ----------


def ensure_session(db: Session, session_id: str | None, user_id: str | None) -> str:
    """按 session_id 复用会话；不存在（或未传）则创建并 flush。

    新建会话后立即 flush：chat_message.session_id 有指向 chat_session 的外键，
    必须保证父行先于子行插入，否则同事务内 INSERT 顺序不定会触发外键违例。
    """
    sid = session_id or uuid.uuid4().hex
    existing = db.scalar(select(ChatSession).where(ChatSession.session_id == sid))
    if existing:
        return existing.session_id
    db.add(ChatSession(session_id=sid, user_id=user_id or "", channel="web"))
    db.flush()
    return sid


def add_message(db: Session, session_id: str, role: str, content: str, intent: str = "") -> ChatMessage:
    """写入一条会话消息（调用方负责 commit）。"""
    msg = ChatMessage(session_id=session_id, role=role, content=content, intent=intent)
    db.add(msg)
    return msg


# ---------- 活动 ----------


def list_events(db: Session, status: str | None = None) -> list[LectureEvent]:
    """活动列表；支持按状态筛选（如“报名中”）。"""
    stmt = select(LectureEvent).order_by(LectureEvent.start_time.asc())
    if status:
        stmt = stmt.where(LectureEvent.status == status)
    return list(db.scalars(stmt).all())


def get_event(db: Session, event_id: int) -> LectureEvent | None:
    """按 ID 取活动；不存在返回 None。"""
    return db.get(LectureEvent, event_id)


def lock_event(db: Session, event_id: int) -> LectureEvent | None:
    """行锁取活动（SELECT ... FOR UPDATE）。

    并发报名在同一活动行上串行化，防止名额超卖与计数丢失；
    锁顺序固定为活动父行，避免与其他写入口死锁。
    """
    return db.execute(
        select(LectureEvent).where(LectureEvent.id == event_id).with_for_update()
    ).scalar_one_or_none()


# ---------- 报名 ----------


def find_active_signup(db: Session, event_id: int, customer_phone: str) -> EventSignup | None:
    """状态式防重：仅“有效”报名记录视为重复；已取消记录不阻挡重新报名。"""
    return db.scalar(
        select(EventSignup).where(
            EventSignup.event_id == event_id,
            EventSignup.customer_phone == customer_phone,
            EventSignup.status == "有效",
        )
    )


def add_signup(
    db: Session,
    event: LectureEvent,
    customer_name: str,
    customer_phone: str,
    customer_info: dict | None = None,
) -> EventSignup:
    """写入报名并递增活动已报名人数（调用方在同一事务内 commit）。

    必须在已持锁的 event 行上调用，保证名额校验与人数更新同事务原子完成。
    """
    signup = EventSignup(
        event_id=event.id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_info=customer_info,
        source="客服对话",
        status="有效",
    )
    db.add(signup)
    event.signed_count += 1
    return signup


# ---------- 课程 ----------


def list_courses(db: Session, category: str | None = None) -> list[CourseProject]:
    """仅返回上架课程；支持类别筛选，为 show_courses 动作提供真实数据。"""
    stmt = (
        select(CourseProject)
        .where(CourseProject.status == "上架")
        .order_by(CourseProject.id.asc())
    )
    if category:
        stmt = stmt.where(CourseProject.category == category)
    return list(db.scalars(stmt).all())


# ---------- FAQ ----------


def search_faq(db: Session, keyword: str | None = None) -> Faq | None:
    """FAQ 兜底：按问题关键词模糊匹配，无命中返回第一条。"""
    kw = (keyword or "").strip()
    if kw:
        row = db.scalar(
            select(Faq).where(Faq.question.like(f"%{kw}%")).order_by(Faq.id.asc()).limit(1)
        )
    else:
        row = None
    if row is None:
        row = db.scalar(select(Faq).order_by(Faq.id.asc()).limit(1))
    return row
