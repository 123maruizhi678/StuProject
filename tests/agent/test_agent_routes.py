"""实际主入口上的客服六接口联动；数据库、咨询及报名数据均为虚构。"""
import unittest
from unittest.mock import patch

import httpx
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.common.dify import DifyHttpClient
from app.core.common.response import BusinessException
from app.database import get_db
from app.main import app
from app.models.agent import ChatMessage, ChatSession, EventSignup, LectureEvent
from app.services.agent import agent_service
from app.services.agent.dify_client import RealDifyClient
from fastapi.testclient import TestClient
from tests.agent.support import make_engine, seed_catalog


class AgentRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = make_engine()
        with Session(self.engine) as db:
            seed_catalog(db)
        self.original_overrides = app.dependency_overrides.copy()

        def database():
            with Session(self.engine) as db:
                try:
                    yield db
                except Exception:
                    db.rollback()
                    raise

        app.dependency_overrides[get_db] = database
        self.key_patch = patch.object(settings, "DIFY_AGENT_API_KEY", SecretStr("fake-agent-key-for-tests"))
        self.key_patch.start()
        self.response = {"data": {"status": "succeeded", "outputs": {"intent": "event_query", "reply": "这是虚构讲座咨询答复。"}}}
        self.calls = []

        def handle(request):
            self.calls.append(request)
            return httpx.Response(200, json=self.response)

        self.dify = RealDifyClient(DifyHttpClient("http://dify.test/v1", transport=httpx.MockTransport(handle)))
        self.factory_patch = patch.object(agent_service, "get_dify_client", return_value=self.dify)
        self.factory_patch.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.original_overrides)
        self.factory_patch.stop()
        self.key_patch.stop()
        self.engine.dispose()

    def test_all_six_routes_registered_once(self):
        paths = app.openapi()["paths"]
        for path, method in (("/chat", "post"), ("/events", "get"), ("/events/{event_id}", "get"), ("/events/signup", "post"), ("/courses", "get"), ("/faq", "get")):
            self.assertIn(method, paths["/api/v1/agent" + path])
        operations = [operation["operationId"] for path in paths.values() for operation in path.values() if isinstance(operation, dict) and "operationId" in operation]
        self.assertEqual(len(operations), len(set(operations)))

    def test_anonymous_chat_events_signup_courses_and_faq(self):
        response = self.client.post("/api/v1/agent/chat", json={"message": "虚构讲座咨询", "user_id": "fake-visitor"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["code"], 0)
        data = response.json()["data"]
        self.assertEqual(data["action"], {"type": "show_events", "payload": {}})
        self.assertTrue(data["need_action"])
        self.assertEqual(len(self.calls), 1)
        events = self.client.get("/api/v1/agent/events?status=报名中").json()["data"]
        self.assertEqual({event["event_id"] for event in events}, {1, 3})
        self.assertEqual(self.client.get("/api/v1/agent/events/1").json()["data"]["event_name"], "虚构留学讲座")
        signup = {"event_id": 1, "customer_name": "虚构测试访客", "customer_phone": "00000000000"}
        result = self.client.post("/api/v1/agent/events/signup", json=signup)
        self.assertEqual(result.json()["code"], 0)
        self.assertGreater(result.json()["data"]["signup_id"], 0)
        self.assertNotEqual(self.client.post("/api/v1/agent/events/signup", json=signup).json()["code"], 0)
        courses = self.client.get("/api/v1/agent/courses?category=语言培训").json()["data"]
        self.assertEqual([course["course_id"] for course in courses], [1])
        self.assertIn("虚构", self.client.get("/api/v1/agent/faq?question=报名").json()["data"]["answer"])
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ChatSession)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(ChatMessage)), 2)
            self.assertEqual(db.scalar(select(func.count()).select_from(EventSignup)), 1)
            self.assertEqual(db.get(LectureEvent, 1).signed_count, 1)
            messages = db.scalars(select(ChatMessage).order_by(ChatMessage.id)).all()
            self.assertEqual([message.role for message in messages], ["user", "assistant"])
            self.assertEqual(messages[1].content, data["reply"])

    def test_follow_up_reuses_session_and_saves_both_turns(self):
        first = self.client.post("/api/v1/agent/chat", json={"message": "虚构首轮咨询"}).json()["data"]
        result = self.client.post("/api/v1/agent/chat", json={"message": "虚构第二轮咨询", "session_id": first["session_id"]})
        self.assertEqual(result.json()["data"]["session_id"], first["session_id"])
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ChatSession)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(ChatMessage)), 4)

    def test_failed_workflow_rolls_back_new_conversation(self):
        self.response = {"data": {"status": "failed", "error": "fake-private-upstream-detail"}}
        result = self.client.post("/api/v1/agent/chat", json={"message": "虚构失败测试"})
        self.assertEqual(result.json()["code"], 502)
        self.assertNotIn("fake-private-upstream-detail", result.text)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ChatSession)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(ChatMessage)), 0)

    def test_failed_follow_up_preserves_existing_conversation(self):
        first = self.client.post("/api/v1/agent/chat", json={"message": "虚构成功消息"}).json()["data"]
        self.response = {"data": {"status": "failed"}}
        result = self.client.post("/api/v1/agent/chat", json={"message": "虚构失败消息", "session_id": first["session_id"]})
        self.assertEqual(result.json()["code"], 502)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ChatSession)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(ChatMessage)), 2)

    def test_missing_key_returns_dependency_error_without_model_call(self):
        with patch.object(settings, "DIFY_AGENT_API_KEY", SecretStr("")):
            result = self.client.post("/api/v1/agent/chat", json={"message": "虚构未配置测试"})
        self.assertEqual(result.json()["code"], 503)
        self.assertEqual(len(self.calls), 0)

    def test_invalid_message_and_unavailable_events_rejected(self):
        self.assertEqual(self.client.post("/api/v1/agent/chat", json={"message": ""}).status_code, 422)
        self.assertEqual(self.client.post("/api/v1/agent/chat", json={"message": "   "}).json()["code"], 400)
        self.assertEqual(len(self.calls), 0)
        self.assertNotEqual(self.client.get("/api/v1/agent/events/999").json()["code"], 0)
        for event_id in (2, 3, 999):
            result = self.client.post("/api/v1/agent/events/signup", json={"event_id": event_id, "customer_name": "虚构测试访客", "customer_phone": "00000000000"})
            self.assertNotEqual(result.json()["code"], 0)

    def test_service_failure_leaves_same_session_clean(self):
        self.response = {"data": {"status": "failed"}}
        with Session(self.engine) as db:
            with self.assertRaises(BusinessException):
                agent_service.run_chat(db, None, "fake", "虚构失败消息")
            # 直接复用业务 Session 验证已主动回滚，不依赖请求结束时清理。
            self.assertEqual(db.scalar(select(func.count()).select_from(ChatMessage)), 0)
            self.assertEqual(len(db.new), 0)

    def test_database_failure_after_model_reply_rolls_back_session_and_messages(self):
        with Session(self.engine) as db:
            with patch.object(db, "commit", side_effect=RuntimeError("fake-persistence-failure")):
                with self.assertRaises(RuntimeError):
                    agent_service.run_chat(db, None, "fake", "虚构写库失败测试")
            self.assertEqual(len(self.calls), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(ChatSession)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(ChatMessage)), 0)
