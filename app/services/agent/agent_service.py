"""客服 Agent 业务逻辑。

职责：
    - 会话 / 消息落库（留资、审计）
    - 活动列表 / 详情查询
    - 活动报名（校验 + 防重 + 行锁事务）
    - 课程列表查询（课程推荐分支数据源）
    - FAQ 兜底查询

写库类业务规则必须在后端实现，不交给 Dify。

事务顺序（对齐《开发文档/操作文档.md》）：
    1. 短事务：确保会话 → 写 user 消息 → commit；此段失败不调用 Dify；
    2. 事务外调用 Dify，避免持锁等待外部 HTTP；失败用兜底话术，不丢留资；
    3. 新短事务：写 assistant 消息 → commit；失败不回滚已提交的用户消息。
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.response import BusinessException, ResultCode
from app.clients.agent.dify_client import get_dify_client
from app.models.agent.agent import LectureEvent
from app.repositories.agent import agent_repository as repo

logger = get_logger(__name__)

# 业务状态常量
EVENT_OPEN = "报名中"       # 活动可报名
COURSE_ON_SHELF = "上架"    # 课程上架

# Dify 调用失败时的兜底话术（用户消息已落库，不丢留资）
FALLBACK_REPLY = "抱歉，客服助手暂时繁忙，请稍后再试。如有紧急问题，可拨打热线或留下联系方式，我们会尽快联系您。"


def _fmt(dt: datetime | None) -> str:
    """datetime 统一输出为 'YYYY-MM-DD HH:MM:SS'。"""
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""


# ---------- 对话 ----------
def run_chat(db: Session, session_id: str | None, user_id: str | None, message: str) -> dict:
    """对话入口：确保会话 → 写 user 消息 → 调 Dify → 写 assistant 消息。

    Dify 调用失败不影响用户消息落库：user 消息先行提交，Dify 异常时
    记录日志并用兜底话术回复，保证对话闭环与留资不丢失。
    """
    message = (message or "").strip()
    if not message:
        raise BusinessException("消息不能为空", code=ResultCode.PARAM_ERROR)

    sid = repo.ensure_session(db, session_id, user_id)
    repo.add_message(db, sid, "user", message, "")
    db.commit()

    try:
        result = get_dify_client().chat(sid, message)
        intent, reply, action = result.intent, result.reply, result.action
    except Exception:
        logger.exception("客服 Dify 调用失败，使用兜底话术")
        intent, reply, action = "", FALLBACK_REPLY, None

    repo.add_message(db, sid, "assistant", reply, intent)
    db.commit()

    return {
        "session_id": sid,
        "intent": intent,
        "reply": reply,
        "need_action": bool(action),
        "action": action,
    }


# ---------- 活动 ----------
def list_events(db: Session, status: str | None = None) -> list[dict]:
    """活动列表；支持按状态筛选。"""
    return [_event_to_dict(e) for e in repo.list_events(db, status)]


def get_event(db: Session, event_id: int) -> dict | None:
    """活动详情；不存在返回 None（由路由层转 404 语义）。"""
    e = repo.get_event(db, event_id)
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
    """活动报名：行锁串行化 → 校验活动状态与名额 → 状态式防重 → 事务内写库。"""
    customer_name = (customer_name or "").strip()
    customer_phone = (customer_phone or "").strip()
    if not customer_name or not customer_phone:
        raise BusinessException("姓名和手机号不能为空", code=ResultCode.PARAM_ERROR)

    # FOR UPDATE 行锁：并发下串行化同一活动的报名，防止名额超卖与计数丢失
    event = repo.lock_event(db, event_id)
    if not event:
        raise BusinessException("活动不存在", code=ResultCode.PARAM_ERROR)
    if event.status != EVENT_OPEN:
        raise BusinessException("活动不在报名中，无法报名", code=ResultCode.PARAM_ERROR)
    if event.quota > 0 and event.signed_count >= event.quota:
        raise BusinessException("活动名额已满", code=ResultCode.PARAM_ERROR)

    # 状态式防重：仅当存在「有效」报名记录时拒绝；已取消的记录不阻挡重新报名
    dup = repo.find_active_signup(db, event_id, customer_phone)
    if dup:
        raise BusinessException("您已报名该活动", code=ResultCode.PARAM_ERROR)

    record = repo.add_signup(db, event, customer_name, customer_phone, customer_info)
    db.commit()
    return {"signup_id": record.id, "signup_time": _fmt(record.signup_time)}


# ---------- 课程 ----------
def list_courses(db: Session, category: str | None = None) -> list[dict]:
    """仅返回上架课程；支持类别筛选。"""
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
        for c in repo.list_courses(db, category)
    ]


# ---------- FAQ ----------
def search_faq(db: Session, question: str | None = None) -> dict | None:
    """FAQ 兜底：按问题关键词模糊匹配，无命中返回第一条。"""
    row = repo.search_faq(db, question)
    if row is None:
        return None
    return {"question": row.question, "answer": row.answer, "category": row.category}
