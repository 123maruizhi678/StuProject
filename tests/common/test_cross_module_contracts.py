"""请假、通知、审计共享模型和仓储的事务联合回归。"""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from app.models import common as t
from app.repositories.common.notification_repository import NotificationRepository
from app.repositories.common.operation_log_repository import OperationLogRepository
from app.schemas.student_leave import LeaveAnalysis, LeaveInput
from app.services.student_leave_service import LeaveError, StudentLeaveService
from tests.common.support import make_engine, seed_people


class Workflow:
    def __init__(self):
        self.calls = 0

    def analyze_leave(self, student_id, payload):
        self.calls += 1
        return LeaveAnalysis(summary="虚构请假摘要", review_points=["核验时间"], workflow_run_id="fake-test-run", analysis_version="test-v1")


class CommonTransactionTests(unittest.TestCase):
    def setUp(self):
        self.engine = make_engine()
        self.addCleanup(self.engine.dispose)
        self.db = Session(self.engine)
        self.addCleanup(self.db.close)
        seed_people(self.db)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.execute(insert(t.student_staff_binding).values(binding_id=1, student_id=1, employee_id=10,
                        relation_type="class_teacher", is_primary=True, valid_from=now-timedelta(days=1)))
        self.db.commit()
        self.workflow = Workflow()
        self.service = StudentLeaveService(self.db, self.workflow)
        self.account = SimpleNamespace(user_id=103, identity_type="student", student_id=1)
        start = datetime.now(timezone.utc) + timedelta(days=1)
        self.payload = LeaveInput(leave_content="虚构联动测试", leave_type="personal", leave_start_at=start, leave_end_at=start+timedelta(hours=1))

    def count(self, table):
        return self.db.scalar(select(func.count()).select_from(table))

    def test_atomic_submission_idempotency_and_conflict(self):
        receipt = self.service.submit(self.account, "fake-request-1", self.payload)
        self.assertEqual(receipt["reviewer_id"], 10)
        self.assertTrue(receipt["notification_queued"])
        replay = self.service.submit(self.account, "fake-request-1", self.payload)
        self.assertEqual(receipt, replay)
        self.assertEqual(self.workflow.calls, 1)
        for table in (t.student_admin_service, t.operation_log, t.business_notification):
            self.assertEqual(self.count(table), 1)
        audit = self.db.execute(select(t.operation_log)).mappings().one()
        self.assertEqual(audit["operation_status"], "succeeded")
        self.assertEqual(audit["student_id"], 1)
        self.assertEqual(audit["row_version"], 2)
        with self.assertRaises(LeaveError) as error:
            self.service.submit(self.account, "fake-request-1", self.payload.model_copy(update={"leave_content": "变更内容"}))
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.workflow.calls, 1)

    def test_notification_failure_rolls_back_application_and_audit(self):
        with patch.object(self.service.repository.notifications, "enqueue", side_effect=RuntimeError("fake-queue-failure")):
            with self.assertRaises(RuntimeError):
                self.service.submit(self.account, "fake-rollback", self.payload)
        for table in (t.student_admin_service, t.operation_log, t.business_notification):
            self.assertEqual(self.count(table), 0)

    def test_notification_reads_are_scoped_and_read_is_idempotent(self):
        self.service.submit(self.account, "fake-read-scope", self.payload)
        repository = NotificationRepository(self.db)
        self.assertEqual(repository.list_for_recipient(employee_id=10), [])
        # 模拟既有投递方完成站内发布；本仓储不自行启动通知任务。
        self.db.execute(update(t.business_notification).values(delivery_status="sent"))
        self.db.commit()
        records = repository.list_for_recipient(employee_id=10)
        self.assertEqual(len(records), 1)
        self.assertEqual(repository.list_for_recipient(student_id=1), [])
        identifier = records[0]["notification_id"]
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        self.assertFalse(repository.mark_read(identifier, now, student_id=1))
        self.assertTrue(repository.mark_read(identifier, now, employee_id=10))
        self.assertFalse(repository.mark_read(identifier, now, employee_id=10))
        self.db.rollback()
        self.assertIsNone(repository.list_for_recipient(employee_id=10)[0]["read_at"])

    def test_invalid_recipient_and_actor_are_rejected(self):
        notifications = NotificationRepository(self.db)
        with self.assertRaises(ValueError):
            notifications.enqueue({"employee_id": 10, "student_id": 1})
        with self.assertRaises(ValueError):
            notifications.list_for_recipient()
        with self.assertRaises(ValueError):
            OperationLogRepository(self.db).create({"employee_id": 10, "student_id": 1})

    def test_repository_writes_do_not_commit_business_transaction(self):
        repository = OperationLogRepository(self.db)
        key = "e" * 64
        repository.create(dict(operation_key=key, student_id=1, action_code="test.rollback", entity_type="test", request_key="fake-request", parameters_hash="f" * 64))
        self.assertIsNotNone(repository.find_by_key(key))
        self.db.rollback()
        self.assertIsNone(repository.find_by_key(key))
