"""客服 Agent ORM 模型（六表）。

表（对应《开发文档/操作文档.md》及 scripts/sql 基线）：
    - CourseProject  课程项目
    - LectureEvent   讲座活动
    - EventSignup    活动报名
    - Faq            FAQ 问答对
    - ChatSession    客服会话
    - ChatMessage    客服消息

建表由 scripts/sql 下的迁移 / 初始化脚本负责，本模块不自动建表。
"""
from app.models.agent.agent import (
    ChatMessage,
    ChatSession,
    CourseProject,
    EventSignup,
    Faq,
    LectureEvent,
)

__all__ = [
    "ChatMessage",
    "ChatSession",
    "CourseProject",
    "EventSignup",
    "Faq",
    "LectureEvent",
]
