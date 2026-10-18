"""客服测试只使用 SQLite 内存库及明确虚构的数据。"""
from datetime import datetime, timedelta

from sqlalchemy import ForeignKeyConstraint, Integer, MetaData, create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.agent import ChatMessage, ChatSession, CourseProject, EventSignup, Faq, LectureEvent

MODELS = (CourseProject, LectureEvent, EventSignup, Faq, ChatSession, ChatMessage)


def make_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    # SQLite 自增仅支持 INTEGER PRIMARY KEY；只调整测试 DDL 副本。
    metadata = MetaData()
    for model in MODELS:
        table = model.__table__.to_metadata(metadata)
        table.c.id.type = Integer()
    # 匹配现有 scripts/sql/all.sql 的两个外键，不能只测试没有关联约束的表。
    metadata.tables["chat_message"].append_constraint(ForeignKeyConstraint(["session_id"], ["chat_session.session_id"]))
    metadata.tables["event_signup"].append_constraint(ForeignKeyConstraint(["event_id"], ["lecture_event.id"]))
    metadata.create_all(engine)
    return engine


def seed_catalog(db: Session):
    db.add_all([
        CourseProject(id=1, course_name="虚构语言培训课程", category="语言培训", target_audience="虚构测试学员", description="仅用于接口测试", status="上架"),
        CourseProject(id=2, course_name="虚构下架课程", category="语言培训", target_audience="虚构测试学员", description="仅用于接口测试", status="下架"),
        LectureEvent(id=1, event_name="虚构留学讲座", event_type="线上", start_time=datetime.now()+timedelta(days=1), quota=2, signed_count=0, status="报名中"),
        LectureEvent(id=2, event_name="虚构已结束讲座", event_type="线上", start_time=datetime.now()-timedelta(days=1), quota=2, signed_count=0, status="已结束"),
        LectureEvent(id=3, event_name="虚构满额讲座", event_type="线上", start_time=datetime.now()+timedelta(days=1), quota=1, signed_count=1, status="报名中"),
        Faq(id=1, question="虚构报名流程是什么？", answer="这是虚构流程答复，仅供测试。", category="测试"),
    ])
    db.commit()
