"""客服对话（run_chat）单元测试。

不依赖数据库：以 mock 替换 repository 与 Dify 客户端，覆盖
    1. 空消息拒绝；
    2. 正常路径：user 消息先行提交 → 调 Dify → assistant 消息落库；
    3. Dify 异常：兜底话术 + 用户消息不丢；
    4. 会话复用：传入 session_id 时复用，不重复建会话。

运行：python -m unittest tests.agent.test_agent_chat -v
"""
import unittest
from unittest.mock import MagicMock, patch

from app.core.response import BusinessException
from app.services.agent import agent_service
from app.clients.agent.dify_client import ChatResult


class TestRunChat(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()

    @patch("app.services.agent.agent_service.repo")
    @patch("app.services.agent.agent_service.get_dify_client")
    def test_chat_success(self, mock_get_client, mock_repo):
        mock_repo.ensure_session.return_value = "sid-1"
        mock_get_client.return_value.chat.return_value = ChatResult(
            intent="event_query",
            reply="近期有以下讲座",
            action={"type": "show_events", "payload": {}},
        )

        data = agent_service.run_chat(self.db, None, "u1", "  最近有什么讲座  ")

        self.assertEqual(data["session_id"], "sid-1")
        self.assertEqual(data["intent"], "event_query")
        self.assertTrue(data["need_action"])
        self.assertEqual(data["action"]["type"], "show_events")

        # 消息边界：user 先行提交，assistant 随后；共两次 commit
        roles = [c.args[2] for c in mock_repo.add_message.call_args_list]
        self.assertEqual(roles, ["user", "assistant"])
        self.assertEqual(self.db.commit.call_count, 2)

        # 消息内容 strip 后落库
        user_call = mock_repo.add_message.call_args_list[0]
        self.assertEqual(user_call.args[3], "最近有什么讲座")

    @patch("app.services.agent.agent_service.repo")
    @patch("app.services.agent.agent_service.get_dify_client")
    def test_chat_dify_failure_uses_fallback(self, mock_get_client, mock_repo):
        mock_repo.ensure_session.return_value = "sid-2"
        mock_get_client.return_value.chat.side_effect = RuntimeError("dify down")

        data = agent_service.run_chat(self.db, None, None, "你好")

        self.assertEqual(data["reply"], agent_service.FALLBACK_REPLY)
        self.assertFalse(data["need_action"])
        self.assertIsNone(data["action"])
        # 用户消息已提交，不因模型失败丢失
        self.assertEqual(self.db.commit.call_count, 2)
        roles = [c.args[2] for c in mock_repo.add_message.call_args_list]
        self.assertEqual(roles, ["user", "assistant"])

    @patch("app.services.agent.agent_service.repo")
    def test_chat_empty_message_rejected(self, mock_repo):
        with self.assertRaises(BusinessException):
            agent_service.run_chat(self.db, None, None, "   ")
        mock_repo.ensure_session.assert_not_called()
        mock_repo.add_message.assert_not_called()

    @patch("app.services.agent.agent_service.repo")
    @patch("app.services.agent.agent_service.get_dify_client")
    def test_chat_reuses_session(self, mock_get_client, mock_repo):
        """传入已有 session_id 时透传复用，不新建会话。"""
        mock_repo.ensure_session.return_value = "existing-sid"
        mock_get_client.return_value.chat.return_value = ChatResult("chat", "hi", None)

        data = agent_service.run_chat(self.db, "existing-sid", None, "hello")

        mock_repo.ensure_session.assert_called_once_with(self.db, "existing-sid", None)
        self.assertEqual(data["session_id"], "existing-sid")


if __name__ == "__main__":
    unittest.main()
