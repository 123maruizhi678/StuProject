"""校验真实适配器的 HTTP 契约和失败行为，不访问网络。"""
import json
import unittest
from unittest.mock import patch

import httpx
from pydantic import SecretStr

from app.config import settings
from app.core.common.dify import DifyHttpClient
from app.services.dify_client import AgentDifyError, MockDifyClient, RealDifyClient, get_dify_client


def succeeded(intent="chat", reply="虚构回复", **extra):
    return {"data": {"status": "succeeded", "outputs": {"intent": intent, "reply": reply, **extra}}}


class DifyClientTests(unittest.TestCase):
    def setUp(self):
        self.key = patch.object(settings, "DIFY_AGENT_API_KEY", SecretStr("fake-agent-key-for-tests"))
        self.key.start()
        self.addCleanup(self.key.stop)

    def client(self, handler):
        return RealDifyClient(DifyHttpClient("http://dify.test/v1", transport=httpx.MockTransport(handler)))

    def test_request_contract_and_controlled_course_action(self):
        requests = []

        def handle(request):
            requests.append(request)
            self.assertEqual(str(request.url), "http://dify.test/v1/workflows/run")
            self.assertEqual(request.headers["Authorization"], "Bearer fake-agent-key-for-tests")
            self.assertEqual(json.loads(request.content), {"inputs": {"query": "虚构课程咨询"}, "response_mode": "blocking", "user": "visitor-fake-session"})
            return httpx.Response(200, json=succeeded("course_recommend", "虚构课程答复", action={"type": "arbitrary-model-action"}))

        result = self.client(handle).chat("fake-session", "虚构课程咨询")
        self.assertEqual(result.intent, "course_recommend")
        self.assertEqual(result.action, {"type": "show_courses", "payload": {}})
        self.assertEqual(len(requests), 1)

    def test_event_action_and_other_intents(self):
        for intent in ("event_query", "company_info", "business_query", "policy_query", "faq", "chat"):
            with self.subTest(intent=intent):
                result = self.client(lambda _: httpx.Response(200, json=succeeded(intent))).chat("fake-session", "虚构咨询")
                expected = {"type": "show_events", "payload": {}} if intent == "event_query" else None
                self.assertEqual(result.action, expected)

    def test_reasoning_removed_before_reply_is_returned(self):
        result = self.client(lambda _: httpx.Response(200, json=succeeded("chat", "<think>虚构思考\n内容</think>\n对外答复"))).chat("fake", "虚构咨询")
        self.assertEqual(result.reply, "对外答复")

    def test_invalid_outputs_rejected(self):
        responses = [
            {}, {"data": None}, {"data": {"status": "failed", "error": "fake-upstream-private-detail"}},
            {"data": {"status": "succeeded", "outputs": None}},
            succeeded(intent=1), succeeded(intent="unknown-action"), succeeded(reply=None),
            succeeded(reply=" "), succeeded(reply="<think>only reasoning</think>"),
            succeeded(reply="<think>unfinished reasoning"),
        ]
        for payload in responses:
            with self.subTest(payload_type=type(payload).__name__):
                with self.assertRaises(AgentDifyError) as caught:
                    self.client(lambda _: httpx.Response(200, json=payload)).chat("fake", "虚构咨询")
                self.assertEqual(caught.exception.code, 502)
                self.assertNotIn("fake-upstream-private-detail", str(caught.exception))

    def test_non_object_or_non_json_results_rejected(self):
        for response in (httpx.Response(200, json=[]), httpx.Response(200, text="<html>invalid</html>")):
            with self.assertRaises(AgentDifyError) as caught:
                self.client(lambda _: response).chat("fake", "虚构咨询")
            self.assertEqual(caught.exception.code, 502)

    def test_http_failures_do_not_leak_details_or_retry(self):
        for status in (401, 403, 429, 500):
            calls = []

            def handle(request):
                calls.append(request)
                return httpx.Response(status, json={"message": "fake-agent-key-for-tests"})

            with self.subTest(status=status), self.assertRaises(AgentDifyError) as caught:
                self.client(handle).chat("fake", "虚构咨询")
            self.assertEqual(caught.exception.code, 503)
            self.assertNotIn("fake-agent-key-for-tests", str(caught.exception))
            self.assertEqual(len(calls), 1)

    def test_network_failures_do_not_retry(self):
        for error_type in (httpx.ConnectError, httpx.ReadTimeout):
            calls = []

            def handle(request):
                calls.append(request)
                raise error_type("fake-agent-key-for-tests", request=request)

            with self.assertRaises(AgentDifyError) as caught:
                self.client(handle).chat("fake", "虚构咨询")
            self.assertEqual(caught.exception.code, 503)
            self.assertEqual(len(calls), 1)
            self.assertNotIn("fake-agent-key-for-tests", str(caught.exception))

    def test_missing_key_fails_before_request(self):
        with patch.object(settings, "DIFY_AGENT_API_KEY", SecretStr("")):
            with self.assertRaises(AgentDifyError):
                self.client(lambda _: self.fail("缺少Key不得发出请求")).chat("fake", "虚构咨询")

    def test_factory_requires_explicit_mock_selection(self):
        with patch.object(settings, "DIFY_CLIENT", "real"):
            self.assertIsInstance(get_dify_client(), RealDifyClient)
        with patch.object(settings, "DIFY_CLIENT", "mock"):
            self.assertIsInstance(get_dify_client(), MockDifyClient)
        self.assertNotIn("fake-agent-key-for-tests", repr(settings))
