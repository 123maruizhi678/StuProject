"""客服 Agent 请求 / 响应契约。

对齐《开发文档/操作文档.md》第一章：对话返回 intent / reply / action；
列表与详情字段以数据库事实为准，模型只生成话术和动作。
"""
from app.schemas.agent.agent import (
    ChatAction,
    ChatData,
    ChatRequest,
    CourseItem,
    EventItem,
    FaqData,
    SignupData,
    SignupRequest,
)

__all__ = [
    "ChatAction",
    "ChatData",
    "ChatRequest",
    "CourseItem",
    "EventItem",
    "FaqData",
    "SignupData",
    "SignupRequest",
]
