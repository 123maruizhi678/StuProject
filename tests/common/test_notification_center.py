"""公共通知回归：SQLite、虚构账号，不修改业务流程和真实数据。"""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, func, update
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.main import app
from app.models import common as t
from app.services.common.auth_service import create_access_token
from tests.common.support import make_engine, seed_people, TEST_SECRET


class NotificationCenterTests(unittest.TestCase):
    def setUp(self):
        self.engine = make_engine()
        with Session(self.engine) as db:
            seed_people(db, accounts=True)
            db.execute(insert(t.student_profile).values(student_id=2, student_no="OTHER-2", full_name="其他学生", department_id=7, status="active"))
            db.commit()
        self.overrides = app.dependency_overrides.copy()
        def database():
            with Session(self.engine) as db:
                yield db
        app.dependency_overrides[get_db] = database
        self.secret = patch.object(settings, "AUTH_SECRET_KEY", TEST_SECRET)
        self.secret.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.overrides)
        self.secret.stop()
        self.engine.dispose()

    def headers(self, user=101):
        with Session(self.engine) as db:
            token, _ = create_access_token(db.get(t.UserAccount, user))
        return {"Authorization": "Bearer " + token}

    def create(self, **fields):
        data = {"title": "虚构公共通知", "content": "测试正文", "status": "published", **fields}
        result = self.client.post("/api/v1/common/announcements", json=data, headers=self.headers())
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()["data"]

    def message(self, student=1, kind="leave", number=1, **extra):
        with Session(self.engine) as db:
            result = db.execute(insert(t.business_notification).values(entity_type=kind, entity_id=77,
                event_code="student." + kind + ".updated", student_id=student, channel="in_app", title="测试消息 " + str(number),
                content="办理结果已更新", dedupe_key="fixture-" + str(student) + "-" + str(number), delivery_status="sent",
                sent_at=datetime.now(timezone.utc).replace(tzinfo=None), **extra))
            db.commit()
            return result.inserted_primary_key[0]

    def test_announcements_require_login_and_admin_can_publish(self):
        self.assertEqual(self.client.get("/api/v1/common/announcements").status_code, 401)
        for user in (102, 103, 104):
            response = self.client.post("/api/v1/common/announcements", json={"title":"伪造", "content":"内容"}, headers=self.headers(user))
            self.assertEqual(response.status_code, 403)
        self.create()
        for user in (101, 102, 103, 104):
            response = self.client.get("/api/v1/common/announcements", headers=self.headers(user))
            self.assertEqual(len(response.json()["data"]["items"]), 1)

    def test_draft_future_expired_and_withdrawn_are_not_public(self):
        instant = datetime.now(timezone.utc)
        self.create(status="draft")
        self.create(status="withdrawn")
        self.create(published_at=(instant + timedelta(days=1)).isoformat())
        self.create(published_at=(instant - timedelta(days=2)).isoformat(), expires_at=(instant - timedelta(days=1)).isoformat())
        regular = self.create(title="普通通知")
        pinned = self.create(title="置顶通知", pinned=True)
        data = self.client.get("/api/v1/common/announcements", headers=self.headers(103)).json()["data"]
        self.assertEqual([item["announcement_id"] for item in data["items"]], [pinned["announcement_id"], regular["announcement_id"]])
        managed = self.client.get("/api/v1/common/announcements/manage", headers=self.headers()).json()["data"]
        self.assertEqual(managed["total"], 6)

    def test_public_read_state_is_per_account_and_idempotent(self):
        item = self.create()
        key = "announcement:" + str(item["announcement_id"])
        path = "/api/v1/common/notifications/" + key + "/read"
        first = self.client.post(path, headers=self.headers()).json()["data"]
        second = self.client.post(path, headers=self.headers()).json()["data"]
        self.assertEqual(first, second)
        own = self.client.get("/api/v1/common/announcements", headers=self.headers()).json()["data"]
        other = self.client.get("/api/v1/common/announcements", headers=self.headers(103)).json()["data"]
        self.assertEqual(own["unread_count"], 0)
        self.assertEqual(other["unread_count"], 1)

    def test_personal_owner_filters_detail_and_business_link(self):
        own = self.message()
        self.message(student=2)
        result = self.client.get("/api/v1/common/notifications?student_id=2", headers=self.headers(103)).json()["data"]
        self.assertEqual([item["notification_id"] for item in result["items"]], [own])
        detail = self.client.get(f"/api/v1/common/notifications/business:{own}", headers=self.headers(103)).json()["data"]
        self.assertEqual(detail["related"], {"route": "/student/leave-detail.html", "selection": {"apply_id": 77}})
        for user in (101, 104):
            self.assertEqual(self.client.get(f"/api/v1/common/notifications/business:{own}", headers=self.headers(user)).status_code, 404)
            self.assertEqual(self.client.post(f"/api/v1/common/notifications/business:{own}/read", headers=self.headers(user)).status_code, 404)

    def test_personal_unread_filter_and_read_do_not_change_business_rows(self):
        own = self.message()
        self.client.post(f"/api/v1/common/notifications/business:{own}/read", headers=self.headers(103))
        result = self.client.get("/api/v1/common/notifications?unread=true", headers=self.headers(103)).json()["data"]
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["unread_count"], 0)
        with Session(self.engine) as db:
            self.assertIsNone(db.scalar(select(t.business_notification.c.read_at).where(t.business_notification.c.notification_id == own)))
            self.assertEqual(db.scalar(select(func.count()).select_from(t.platform_notification_read)), 1)

    def test_employee_messages_follow_current_customer_visibility(self):
        from app.models import enterprise
        enterprise.customer_followup.create(self.engine, checkfirst=True)
        enterprise.employee_daily_report.create(self.engine, checkfirst=True)
        with Session(self.engine) as db:
            db.execute(update(t.employee).where(t.employee.c.employee_id == 10).values(role_codes=["consultant"]))
            db.execute(update(t.customer_profile).where(t.customer_profile.c.customer_id == 20).values(employee_id=10))
            db.execute(insert(t.customer_profile).values(customer_id=21, customer_no="OTHER-C21", full_name="其他客户", source_channel="test", department_id=7))
            ids = []
            for customer_id in (20, 21):
                result = db.execute(insert(t.business_notification).values(entity_type="customer_profile", entity_id=customer_id,
                    event_code="enterprise.customer.changed", employee_id=10, channel="in_app", title="客户变更", content="状态更新",
                    dedupe_key="employee-fixture-" + str(customer_id), delivery_status="sent"))
                ids.append(result.inserted_primary_key[0])
            db.commit()
        data = self.client.get("/api/v1/common/notifications", headers=self.headers(102)).json()["data"]
        self.assertEqual([item["notification_id"] for item in data["items"]], [ids[0]])
        with Session(self.engine) as db:
            db.execute(update(t.customer_profile).where(t.customer_profile.c.customer_id == 20).values(employee_id=None))
            db.commit()
        self.assertEqual(self.client.get(f"/api/v1/common/notifications/business:{ids[0]}", headers=self.headers(102)).status_code, 404)

    def test_category_search_pagination_and_empty_recipient(self):
        for index in range(23):
            self.message(kind="ticket" if index % 2 else "leave", number=index)
        data = self.client.get("/api/v1/common/notifications?limit=20&offset=20", headers=self.headers(103)).json()["data"]
        self.assertEqual(data["total"], 23)
        self.assertEqual(len(data["items"]), 3)
        data = self.client.get("/api/v1/common/notifications?kind=reply&q=测试消息", headers=self.headers(103)).json()["data"]
        self.assertEqual(data["total"], 11)
        for user in (101, 102, 104):
            data = self.client.get("/api/v1/common/notifications", headers=self.headers(user)).json()["data"]
            self.assertEqual(data["items"], [])

    def test_edit_conflict_and_withdrawal_revoke_detail_access(self):
        item = self.create()
        body = {"title": "撤回通知", "content": "正文", "status": "withdrawn", "expected_version": item["row_version"]}
        path = "/api/v1/common/announcements/" + str(item["announcement_id"])
        self.assertEqual(self.client.patch(path, json=body, headers=self.headers()).status_code, 200)
        self.assertEqual(self.client.patch(path, json=body, headers=self.headers()).status_code, 409)
        key = "announcement:" + str(item["announcement_id"])
        self.assertEqual(self.client.get("/api/v1/common/notifications/" + key, headers=self.headers(103)).status_code, 404)

    def test_invalid_content_times_and_message_keys_are_rejected(self):
        for body in ({"title": " ", "content": "正文"}, {"title": "标题", "content": "正文", "published_at": "2026-10-18T10:00:00"},
                     {"title": "标题", "content": "正文", "published_at": "2026-10-18T10:00:00+08:00", "expires_at": "2026-10-18T09:00:00+08:00"}):
            self.assertEqual(self.client.post("/api/v1/common/announcements", json=body, headers=self.headers()).status_code, 422)
        for key in ("business:0", "unknown:1", "business:-1"):
            self.assertEqual(self.client.get("/api/v1/common/notifications/" + key, headers=self.headers(103)).status_code, 404)
