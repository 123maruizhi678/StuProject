"""客服 Agent 数据访问层。

约束（对齐《开发文档/操作文档.md》）：
    - 所有查询参数化，不拼接 SQL；
    - 本层不做事务提交，提交由 services 层显式控制；
    - 报名写入统一走 `lock_event` 行锁，锁顺序固定为活动父行 → 报名子行。
"""
from app.repositories.agent.agent_repository import (
    add_message,
    add_signup,
    ensure_session,
    find_active_signup,
    get_event,
    list_courses,
    list_events,
    lock_event,
    search_faq,
)

__all__ = [
    "add_message",
    "add_signup",
    "ensure_session",
    "find_active_signup",
    "get_event",
    "list_courses",
    "list_events",
    "lock_event",
    "search_faq",
]
