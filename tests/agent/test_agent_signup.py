"""活动报名（signup）单元测试。

不依赖数据库：以 mock 替换 repository，覆盖操作文档冻结的报名口径：
    1. 姓名 / 手机号非空校验；
    2. 活动不存在；
    3. 活动不在报名中；
    4. 名额已满；
    5. 状态式防重（有效报名拒绝、取消不阻挡）；
    6. 成功路径：行锁取活动 → 写报名 → 人数 +1 → 提交。

运行：python -m unittest tests.agent.test_agent_signup -v
"""
import unittest
from unittest.mock import MagicMock, patch

from app.core.response import BusinessException
from app.services.agent import agent_service


def _event(**overrides):
    event = MagicMock()
    event.id = overrides.get("id", 7)
    event.status = overrides.get("status", "报名中")
    event.quota = overrides.get("quota", 0)
    event.signed_count = overrides.get("signed_count", 0)
    return event


class TestSignup(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()

    @patch("app.services.agent.agent_service.repo")
    def test_empty_name_or_phone_rejected(self, mock_repo):
        for name, phone in (("", "138"), ("张三", ""), ("  ", "13800000000")):
            with self.assertRaises(BusinessException):
                agent_service.signup(self.db, 1, name, phone)
        mock_repo.lock_event.assert_not_called()

    @patch("app.services.agent.agent_service.repo")
    def test_event_not_found(self, mock_repo):
        mock_repo.lock_event.return_value = None
        with self.assertRaises(BusinessException) as ctx:
            agent_service.signup(self.db, 999, "张三", "13800000000")
        self.assertIn("不存在", str(ctx.exception))
        mock_repo.add_signup.assert_not_called()
        self.db.commit.assert_not_called()

    @patch("app.services.agent.agent_service.repo")
    def test_event_not_open(self, mock_repo):
        mock_repo.lock_event.return_value = _event(status="已结束")
        with self.assertRaises(BusinessException) as ctx:
            agent_service.signup(self.db, 1, "张三", "13800000000")
        self.assertIn("不在报名中", str(ctx.exception))
        mock_repo.add_signup.assert_not_called()

    @patch("app.services.agent.agent_service.repo")
    def test_quota_full(self, mock_repo):
        mock_repo.lock_event.return_value = _event(quota=2, signed_count=2)
        with self.assertRaises(BusinessException) as ctx:
            agent_service.signup(self.db, 1, "张三", "13800000000")
        self.assertIn("名额已满", str(ctx.exception))
        mock_repo.add_signup.assert_not_called()

    @patch("app.services.agent.agent_service.repo")
    def test_duplicate_active_signup_rejected(self, mock_repo):
        mock_repo.lock_event.return_value = _event()
        mock_repo.find_active_signup.return_value = MagicMock(id=99)
        with self.assertRaises(BusinessException) as ctx:
            agent_service.signup(self.db, 1, "张三", "13800000000")
        self.assertIn("已报名", str(ctx.exception))
        mock_repo.add_signup.assert_not_called()
        self.db.commit.assert_not_called()

    @patch("app.services.agent.agent_service.repo")
    def test_signup_success_increments_and_commits(self, mock_repo):
        event = _event(quota=10, signed_count=3)
        mock_repo.lock_event.return_value = event
        mock_repo.find_active_signup.return_value = None
        record = MagicMock()
        record.id = 555
        record.signup_time = None
        mock_repo.add_signup.return_value = record

        data = agent_service.signup(self.db, 7, " 张三 ", " 13800000000 ", {"note": "x"})

        self.assertEqual(data["signup_id"], 555)
        # 锁与防重使用 strip 后的手机号
        mock_repo.lock_event.assert_called_once_with(self.db, 7)
        mock_repo.find_active_signup.assert_called_once_with(self.db, 7, "13800000000")
        # add_signup 收到 strip 后的姓名与电话（签名：db, event, name, phone, info）
        args = mock_repo.add_signup.call_args.args
        self.assertEqual(args[2], "张三")
        self.assertEqual(args[3], "13800000000")
        self.db.commit.assert_called_once()

    @patch("app.services.agent.agent_service.repo")
    def test_cancelled_signup_does_not_block(self, mock_repo):
        """状态式防重：无有效报名（已取消）时允许重新报名。"""
        mock_repo.lock_event.return_value = _event()
        mock_repo.find_active_signup.return_value = None
        record = MagicMock()
        record.id = 1
        record.signup_time = None
        mock_repo.add_signup.return_value = record

        data = agent_service.signup(self.db, 7, "张三", "13800000000")
        self.assertEqual(data["signup_id"], 1)


if __name__ == "__main__":
    unittest.main()
