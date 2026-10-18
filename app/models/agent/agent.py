"""客服 Agent 模块 ORM 模型。

表（对应《客服Agent实现方案》第四章 / scripts/sql/all.sql）：
    - CourseProject  课程项目
    - LectureEvent   讲座活动
    - EventSignup    活动报名
    - Faq            FAQ 问答对
    - ChatSession    客服会话
    - ChatMessage    客服消息

复用公共 Base；导入模型不会自动建表。
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CourseProject(Base):
    """课程项目表。"""

    __tablename__ = "course_project"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键，自增")
    course_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="课程名称")
    category: Mapped[str] = mapped_column(String(32), nullable=False, comment="类别：留学申请/背景提升/语言培训")
    target_audience: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="适用人群")
    description: Mapped[str] = mapped_column(Text, nullable=False, comment="课程简介")
    location: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="上课地点")
    signup_method: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="报名方式")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="上架", comment="状态：上架/下架")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )


class LectureEvent(Base):
    """讲座活动表。"""

    __tablename__ = "lecture_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键，自增")
    event_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="活动名称")
    event_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="线上/线下")
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="开始时间")
    location: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="地点")
    signup_method: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="报名方式")
    quota: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="名额（0 表示不限）")
    signed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="已报名人数")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="报名中", comment="状态：报名中/已满/已结束")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )


class EventSignup(Base):
    """活动报名表。"""

    __tablename__ = "event_signup"
    __table_args__ = (UniqueConstraint("event_id", "customer_phone", name="uk_event_phone"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键，自增")
    event_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="活动ID")
    customer_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="客户姓名")
    customer_phone: Mapped[str] = mapped_column(String(32), nullable=False, comment="客户手机号")
    customer_info: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="客户扩展信息")
    signup_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="报名时间")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="客服对话", comment="来源渠道")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="有效", comment="状态：有效/取消")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")


class Faq(Base):
    """FAQ 问答对表（兜底查询）。"""

    __tablename__ = "faq"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键，自增")
    question: Mapped[str] = mapped_column(Text, nullable=False, comment="问题")
    answer: Mapped[str] = mapped_column(Text, nullable=False, comment="答案")
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="", comment="分类")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")


class ChatSession(Base):
    """客服会话表。"""

    __tablename__ = "chat_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键，自增")
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="会话唯一标识（UUID）")
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="访客标识")
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="web", comment="渠道")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )


class ChatMessage(Base):
    """客服消息表。"""

    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键，自增")
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="关联会话")
    role: Mapped[str] = mapped_column(String(16), nullable=False, comment="user / assistant")
    intent: Mapped[str] = mapped_column(String(32), nullable=False, default="", comment="意图标签")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息内容")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
