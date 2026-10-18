"""主管研判只读与部门隔离；全部数据仅在 SQLite 内存测试库。"""
import unittest
from unittest.mock import patch
from sqlalchemy import insert, update
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.database import get_db
from app.models.common import UserAccount, employee, org_department, customer_profile
from app.models.customer import CustomerSource, CustomerInfo, ResearchResult, Product, ResearchRule
from app.services.common.auth_service import create_access_token
from tests.common.support import make_engine, seed_people, TEST_SECRET


class ManagerResearchTests(unittest.TestCase):
    def setUp(self):
        self.engine = make_engine()
        for model in (CustomerSource, CustomerInfo, Product, ResearchRule, ResearchResult):
            model.__table__.create(self.engine, checkfirst=True)
        with Session(self.engine) as db:
            seed_people(db, accounts=True)
            db.execute(update(employee).where(employee.c.employee_id == 10).values(role_codes=["manager"]))
            db.execute(insert(org_department).values(department_id=8, department_code="OTHER", department_name="其他部门"))
            db.execute(insert(customer_profile).values(customer_id=21, customer_no="OTHER", full_name="其他部门客户", department_id=8, source_channel="test"))
            db.add(Product(id=1, product_code="FAKE", product_name="虚构产品"))
            db.add(ResearchRule(id=1, product_id=1, rule_version="v1", rule_content={"conditions": []}))
            for source_id in (1, 2, 3):
                db.add(CustomerSource(id=source_id, source_type="text", created_by=101, status="parsed"))
            for info_id, source_id, customer_id in ((1, 1, 20), (2, 1, 21), (3, 2, 21), (4, 3, None)):
                db.add(CustomerInfo(id=info_id, source_id=source_id, customer_id=customer_id, full_name="客户" + str(info_id)))
                db.add(ResearchResult(id=info_id, source_id=source_id, customer_info_id=info_id, product_id=1,
                    rule_version="v1", matched=info_id == 1, input_snapshot={"full_name": "客户" + str(info_id)}))
            # 错配来源与字段不能用于绕过范围判断。
            db.add(ResearchResult(id=5, source_id=2, customer_info_id=1, product_id=1, rule_version="v1", matched=True))
            db.commit()
            self.headers = dict.fromkeys((101, 102, 103, 104))
        self.overrides = app.dependency_overrides.copy()
        def database():
            with Session(self.engine) as db:
                yield db
        app.dependency_overrides[get_db] = database
        self.secret = patch.object(settings, "AUTH_SECRET_KEY", TEST_SECRET)
        # 令牌须在同一测试签名配置下生成。
        self.secret.start()
        with Session(self.engine) as db:
            for uid in self.headers:
                token, _ = create_access_token(db.get(UserAccount, uid))
                self.headers[uid] = {"Authorization": "Bearer " + token}
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.overrides)
        self.secret.stop()
        self.engine.dispose()

    def get(self, path, uid=102):
        return self.client.get("/api/v1/customer/" + path, headers=self.headers[uid]).json()

    def test_sources_and_mixed_detail_only_return_department_customers(self):
        sources = self.get("source?limit=1&offset=0")["data"]
        self.assertEqual(sources["total"], 1)
        self.assertEqual([item["id"] for item in sources["items"]], [1])
        self.assertEqual(self.get("source?limit=1&offset=1")["data"]["items"], [])
        detail = self.get("source/1")["data"]
        self.assertEqual([item["id"] for item in detail["fields"]], [1])
        self.assertNotIn("raw_content", detail["source"])
        for object_id in (2, 3, 999):
            self.assertEqual(self.get("source/" + str(object_id))["code"], 404)
        self.assertEqual(self.get("source", 101)["data"]["total"], 3)

    def test_result_list_total_filters_and_direct_detail_share_scope(self):
        result = self.get("result")["data"]
        self.assertEqual(result["total"], 1)
        self.assertEqual([row["id"] for row in result["items"]], [1])
        self.assertEqual(self.get("result/1")["code"], 0)
        self.assertEqual(self.get("result?matched=false")["data"]["total"], 0)
        for object_id in (2, 3, 4, 5, 999):
            self.assertEqual(self.get("result/" + str(object_id))["code"], 404)
        self.assertEqual(self.get("result", 101)["data"]["total"], 5)
        self.assertEqual(self.get("rule")["code"], 0)
        self.assertEqual(self.get("product")["code"], 0)

    def test_manager_writes_and_file_access_denied_other_roles_unchanged(self):
        for method, path, body in (("post", "source", None), ("post", "source/1/parse", {}),
            ("post", "judge", {"customer_info_id": 1, "product_code": "FAKE"}),
            ("post", "judge/batch", {"customer_info_ids": [1], "product_code": "FAKE"}),
            ("put", "rule", {"product_code": "FAKE", "rule_content": {}})):
            response = getattr(self.client, method)("/api/v1/customer/" + path, headers=self.headers[102], json=body)
            self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(self.client.get("/api/v1/customer/source/1/file", headers=self.headers[102]).status_code, 403)
        for uid in (103, 104):
            self.assertEqual(self.get("result", uid)["code"], 403)
        with Session(self.engine) as db:
            db.execute(update(employee).where(employee.c.employee_id == 10).values(role_codes=["teacher"]))
            db.commit()
        self.assertEqual(self.get("result")["code"], 403)

    def test_department_change_and_archive_take_effect_without_relogin(self):
        with Session(self.engine) as db:
            db.execute(update(customer_profile).where(customer_profile.c.customer_id == 20).values(is_archived=True))
            db.commit()
        self.assertEqual(self.get("result")["data"]["total"], 0)
        self.assertEqual(self.get("source/1")["code"], 404)
        with Session(self.engine) as db:
            db.execute(update(employee).where(employee.c.employee_id == 10).values(department_id=8))
            db.commit()
        self.assertEqual(self.get("result")["data"]["total"], 2)
