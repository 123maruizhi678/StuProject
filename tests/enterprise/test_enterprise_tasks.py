"""企业后台任务的安排代次、领取租约、重试及业务隔离回归。"""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import func, insert, select, update

from app.models import common as t
from app.services.enterprise.enterprise_customer import CustomerService
from app.services.enterprise.enterprise_notification import enqueue
from app.tasks.enterprise import enterprise_tasks as tasks
from tests.enterprise import test_enterprise as fixtures


class EnterpriseTaskTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.EnterpriseTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)
        self.db = self.fixture.db
        self.now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
        self.clock = patch.object(tasks, '_utcnow', return_value=self.now)
        self.clock_mock = self.clock.start()
        self.addCleanup(self.clock.stop)

    def followup(self, key='task-followup-test', **kwargs):
        customer = self.fixture.customer()
        params = {'content': '合成跟进', 'channel': 'phone',
                  'followup_at': (self.now - timedelta(hours=3)).replace(tzinfo=timezone.utc),
                  'next_followup_at': (self.now - timedelta(hours=2)).replace(tzinfo=timezone.utc), **kwargs}
        row = CustomerService(self.fixture.repo).followup(customer['customer_id'], key, params)
        return customer, row

    def notifications(self):
        return self.db.execute(select(t.business_notification).order_by(
            t.business_notification.c.notification_id)).mappings().all()

    def queue(self, event='enterprise.customer.test'):
        customer = self.fixture.customer()
        enqueue(self.db, event=event, entity_type='customer_profile', entity_id=customer['customer_id'],
                employee_id=1, version=1, title='合成通知')
        self.db.commit()

    def test_due_round_is_deduplicated_and_old_round_expires(self):
        self.followup()
        self.assertEqual(tasks.scan(self.db), 1)
        self.assertEqual(tasks.scan(self.db), 0)
        self.clock_mock.return_value = self.now + timedelta(days=1)
        self.assertEqual(tasks.scan(self.db), 1)
        tasks.publish_one(self.db)
        tasks.publish_one(self.db)
        self.assertEqual([n['delivery_status'] for n in self.notifications()], ['dead_letter', 'sent'])

    def test_same_deadline_reschedule_creates_new_generation(self):
        customer, row = self.followup()
        tasks.scan(self.db)
        CustomerService(self.fixture.repo).followup(customer['customer_id'], 'task-same-date-reschedule', {
            'followup_status': 'pending', 'expected_version': 1,
            'next_followup_at': (self.now - timedelta(hours=2)).replace(tzinfo=timezone.utc)}, row['followup_id'])
        self.assertEqual(tasks.scan(self.db), 1)
        tasks.publish_one(self.db)
        tasks.publish_one(self.db)
        self.assertEqual([n['delivery_status'] for n in self.notifications()], ['dead_letter', 'sent'])

    def test_cancelled_schedule_never_publishes(self):
        customer, row = self.followup()
        tasks.scan(self.db)
        CustomerService(self.fixture.repo).followup(customer['customer_id'], 'task-cancel-schedule', {
            'followup_status': 'cancelled', 'expected_version': 1}, row['followup_id'])
        tasks.publish_one(self.db)
        self.assertEqual(self.notifications()[0]['delivery_status'], 'dead_letter')

    def test_reassignment_invalidates_old_manager_recipient(self):
        customer, _ = self.followup()
        tasks.scan(self.db)
        self.db.execute(update(t.customer_profile).where(t.customer_profile.c.customer_id == customer['customer_id'])
                        .values(employee_id=2))
        self.db.commit()
        self.assertEqual(tasks.scan(self.db), 1)
        tasks.publish_one(self.db)
        tasks.publish_one(self.db)
        self.assertEqual([(n['employee_id'], n['delivery_status']) for n in self.notifications()],
                         [(1, 'dead_letter'), (2, 'sent')])

    def test_scan_skips_future_archived_and_inactive_recipients(self):
        customer, _ = self.followup(next_followup_at=(self.now + timedelta(days=1)).replace(tzinfo=timezone.utc))
        self.assertEqual(tasks.scan(self.db), 0)
        self.followup('task-due-second-followup')
        self.db.execute(update(t.customer_profile).where(t.customer_profile.c.customer_id == customer['customer_id'])
                        .values(is_archived=True))
        self.db.commit()
        self.assertEqual(tasks.scan(self.db), 0)
        self.db.execute(update(t.customer_profile).values(is_archived=False))
        self.db.execute(update(t.employee).where(t.employee.c.employee_id == 1).values(status='disabled'))
        self.db.commit()
        self.assertEqual(tasks.scan(self.db), 0)
        self.assertEqual(self.notifications(), [])

    def test_revoked_role_invalidates_already_queued_notice(self):
        self.followup()
        tasks.scan(self.db)
        self.db.execute(update(t.employee).where(t.employee.c.employee_id == 1).values(role_codes=['employee']))
        self.db.commit()
        tasks.publish_one(self.db)
        self.assertEqual(self.notifications()[0]['delivery_status'], 'dead_letter')

    def test_scan_batch_does_not_starve_later_due_records(self):
        self.followup('task-batch-first-followup')
        self.followup('task-batch-second-followup')
        self.assertEqual(tasks.scan(self.db, limit=1), 2)
        self.assertEqual(tasks.scan(self.db, limit=1), 0)

    def test_live_lease_is_untouched_and_expired_lease_is_recovered(self):
        self.queue()
        self.db.execute(update(t.business_notification).values(
            delivery_status='sending', lease_until=self.now + timedelta(seconds=60), attempt_count=1))
        self.db.commit()
        self.assertFalse(tasks.publish_one(self.db))
        self.clock_mock.return_value = self.now + timedelta(seconds=61)
        self.assertTrue(tasks.publish_one(self.db))
        row = self.notifications()[0]
        self.assertEqual(row['delivery_status'], 'sent')
        self.assertEqual(row['attempt_count'], 2)
        self.assertIsNone(row['lease_until'])

    def test_retry_backoff_and_terminal_failure(self):
        self.queue()
        now = self.now
        delays = tasks.policy()['retry_minutes']
        with patch.object(tasks, '_send', side_effect=OSError('合成传输故障')) as send:
            for attempt in range(1, len(delays) + 2):
                self.clock_mock.return_value = now
                self.assertTrue(tasks.publish_one(self.db))
                row = self.notifications()[0]
                self.assertEqual(row['attempt_count'], attempt)
                if attempt <= len(delays):
                    self.assertEqual(row['delivery_status'], 'failed')
                    self.assertEqual(row['next_retry_at'], now + timedelta(minutes=delays[attempt - 1]))
                    self.assertFalse(tasks.publish_one(self.db))
                    now = row['next_retry_at']
                else:
                    self.assertEqual(row['delivery_status'], 'dead_letter')
                    self.assertIsNone(row['next_retry_at'])
                    self.assertFalse(tasks.publish_one(self.db))
            self.assertEqual(send.call_count, len(delays) + 1)

    def test_worker_cannot_complete_after_lease_expires(self):
        self.queue()
        def expire_lease(_):
            self.clock_mock.return_value = self.now + timedelta(seconds=61)
        with patch.object(tasks, '_send', side_effect=expire_lease):
            self.assertTrue(tasks.publish_one(self.db))
        row = self.notifications()[0]
        self.assertEqual(row['delivery_status'], 'sending')
        self.assertIsNone(row['sent_at'])
        self.assertTrue(tasks.publish_one(self.db))
        self.assertEqual(self.notifications()[0]['delivery_status'], 'sent')

    def test_expired_last_attempt_is_not_sent_again(self):
        self.queue()
        attempts = len(tasks.policy()['retry_minutes']) + 1
        self.db.execute(update(t.business_notification).values(delivery_status='sending',
            lease_until=self.now - timedelta(seconds=1), attempt_count=attempts))
        self.db.commit()
        with patch.object(tasks, '_send') as send:
            self.assertTrue(tasks.publish_one(self.db))
            send.assert_not_called()
        row = self.notifications()[0]
        self.assertEqual((row['delivery_status'], row['attempt_count']), ('dead_letter', attempts))

    def test_enterprise_worker_leaves_student_queue_unchanged(self):
        self.queue('student.customer.test')
        before = dict(self.notifications()[0])
        self.assertFalse(tasks.publish_one(self.db))
        self.assertEqual(dict(self.notifications()[0]), before)

    def test_ticket_deadlines_use_existing_facts_and_do_not_close_ticket(self):
        ticket = dict(ticket_no='TASK-T1', student_id=1, ticket_type='complaint', category_code='teaching',
            content='合成工单', priority='normal', employee_id=1, handling_department_id=1, status='assigned',
            response_due_at=self.now - timedelta(hours=2), resolution_due_at=self.now - timedelta(hours=1),
            reopen_count=0, row_version=1)
        ticket_id = self.db.execute(insert(t.service_ticket).values(**ticket)).inserted_primary_key[0]
        self.db.commit()
        self.assertEqual(tasks.scan(self.db), 2)
        self.assertEqual(tasks.scan(self.db), 0)
        # 人工已回应之后，旧首次回应提醒失效，处理到期提醒仍有效。
        self.db.execute(update(t.service_ticket).where(t.service_ticket.c.ticket_id == ticket_id)
                        .values(first_response_at=self.now))
        self.db.commit()
        tasks.publish_one(self.db)
        tasks.publish_one(self.db)
        self.assertEqual([n['delivery_status'] for n in self.notifications()], ['dead_letter', 'sent'])
        row = self.db.execute(select(t.service_ticket).where(t.service_ticket.c.ticket_id == ticket_id)).mappings().one()
        self.assertEqual(row['status'], 'assigned')
        self.assertIsNone(row['closed_at'])
        self.assertEqual(self.db.scalar(select(func.count()).select_from(t.service_ticket_record)), 0)


if __name__ == '__main__':
    unittest.main()
