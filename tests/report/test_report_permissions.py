"""报告授权回归：人群、动作与数据范围（正反分支）；无真实外部调用。

覆盖（操作文档第二章「智能报告授权方案」/第一章五接口表）：
    - 平台管理员：生成/配置/读取全部可达，全公司范围；
    - 部门主管（有效员工且 role_codes 含 manager）：仅 report.read，
      仅本人有效主部门范围（部门范围列 006 未部署前看不到任何部门报告，
      也不能读取全公司报告）；
    - 普通员工、客户、学生与匿名访客一律 403；
    - 403/404 不泄露跨部门对象是否存在；
    - 非法枚举、未知查询参数、非法路径 ID 走统一信封 400。
"""
import json
import re
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import sqlite as sqlite_dialect
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateTable

from app.core.auth import get_current_account
from app.core.report import ReportAccess, ReportScope, resolve_report_access
from app.database import get_db
from app.main import app
from app.models.report import REPORT_TABLES, ReportConfig, ReportRecord
from app.schemas.report import GenerateReportRequest
from app.services.report import report_service as service_module

BUSINESS_TZ = timezone(timedelta(hours=8))


def create_report_tables(engine):
    """按 SQLite 方言编译报告三表 DDL，并做两处兼容改写：
    - 剥离 MySQL 专有的时间戳服务器默认值（created_at/updated_at 由 ORM 默认值供给）；
    - SQLite 仅 INTEGER PRIMARY KEY 自增，BIGINT 主键改写为 INTEGER 主键。
    """
    with engine.begin() as conn:
        for table in REPORT_TABLES:
            ddl = str(CreateTable(table).compile(dialect=sqlite_dialect.dialect()))
            ddl = re.sub(
                r"DEFAULT CURRENT_TIMESTAMP\(3\)( ON UPDATE CURRENT_TIMESTAMP\(3\))?",
                "",
                ddl,
            )
            pk = re.search(r"PRIMARY KEY \((\w+)\)", ddl)
            if pk:
                column = pk.group(1)
                ddl = re.sub(
                    rf"^\t{column} BIGINT NOT NULL,[ \t]*$",
                    f"\t{column} INTEGER PRIMARY KEY,",
                    ddl,
                    flags=re.M,
                )
                ddl = re.sub(rf"\n\tPRIMARY KEY \({column}\),", "", ddl)
            conn.exec_driver_sql(ddl)


def bj(year, month, day, hour=0, minute=0):
    return (
        datetime(year, month, day, hour, minute, tzinfo=BUSINESS_TZ)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


class FakeDifyClient:
    def generate_report(self, report_code, metrics, user="report-service"):
        return "## 摘要\n测试报告正文。"


def account(identity_type, user_id=1, employee_id=None):
    return SimpleNamespace(
        user_id=user_id, identity_type=identity_type, employee_id=employee_id
    )


class ReportPermissionsTest(unittest.TestCase):
    def setUp(self):
        # TestClient 在独立线程执行应用：SQLite 连接需允许跨线程且单连接共享。
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        create_report_tables(self.engine)
        with self.engine.begin() as conn:
            # 员工表最小投影：授权范围由服务端读取，不信任前端传入。
            conn.execute(
                text(
                    "CREATE TABLE employee ("
                    "employee_id INTEGER PRIMARY KEY, status TEXT, "
                    "role_codes JSON, department_id INTEGER)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO employee (employee_id, status, role_codes, department_id) VALUES "
                    "(10, 'active', :manager, 7), "
                    "(11, 'active', :teacher, 7), "
                    "(12, 'left', :manager, 7), "
                    "(13, 'active', :manager, NULL)"
                ),
                {
                    "manager": json.dumps(["manager"]),
                    "teacher": json.dumps(["teacher"]),
                },
            )
        with Session(self.engine) as db:
            db.add(
                ReportConfig(
                    report_code="daily_report",
                    report_name="员工日报汇总报告（日）",
                    report_period="day",
                    cron_expr=None,
                    enabled=True,
                    row_version=1,
                )
            )
            # 平台管理员创建的全公司范围报告。
            db.add(
                ReportRecord(
                    report_config_id=1,
                    report_code="daily_report",
                    idempotency_key="k-company-1",
                    start_time=bj(2026, 10, 15),
                    end_time=bj(2026, 10, 16),
                    timezone="Asia/Shanghai",
                    report_version="v1",
                    status="success",
                    report_content="## 摘要\n公司报告。",
                )
            )
            db.commit()
        self.addCleanup(self.engine.dispose)

        self.session = Session(self.engine)
        self.addCleanup(self.session.close)

        def override_db():
            yield self.session

        app.dependency_overrides[get_db] = override_db
        self.addCleanup(lambda: app.dependency_overrides.clear())
        self.client = TestClient(app)

    def _login_as(self, acct):
        app.dependency_overrides[get_current_account] = lambda: acct

    # -- 平台管理员 ----------------------------------------------------------

    def test_admin_full_access(self):
        self._login_as(account("admin"))
        response = self.client.get("/api/v1/report/configs")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["code"], 0)
        self.assertEqual(body["data"][0]["report_code"], "daily_report")

        listing = self.client.get("/api/v1/report/list")
        self.assertEqual(listing.json()["data"]["total"], 1)

        detail = self.client.get("/api/v1/report/1")
        self.assertEqual(detail.json()["data"]["status"], "success")
        self.assertEqual(detail.json()["data"]["report_content"], "## 摘要\n公司报告。")

        with patch.object(
            service_module, "ReportDifyClient", lambda: FakeDifyClient()
        ), patch.object(
            service_module,
            "SessionLocal",
            sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False),
        ):
            generated = self.client.post(
                "/api/v1/report/generate",
                json={"report_code": "daily_report"},
                headers={"Idempotency-Key": "admin-gen-key-1"},
            )
        self.assertEqual(generated.json()["code"], 0)
        self.assertEqual(generated.json()["data"]["status"], "pending")

    def test_admin_update_config_optimistic_lock(self):
        self._login_as(account("admin"))
        ok = self.client.put(
            "/api/v1/report/configs/daily_report",
            json={
                "row_version": 1,
                "report_name": "日报汇总（新）",
                "cron_expr": "0 0 17 * * *",
                "enabled": True,
            },
        )
        self.assertEqual(ok.json()["code"], 0)
        self.assertEqual(ok.json()["data"]["row_version"], 2)
        self.assertEqual(ok.json()["data"]["cron_expr"], "0 0 17 * * *")

        stale = self.client.put(
            "/api/v1/report/configs/daily_report",
            json={
                "row_version": 1,
                "report_name": "旧版本并发",
                "cron_expr": None,
                "enabled": True,
            },
        )
        self.assertEqual(stale.json()["code"], 409)

    def test_admin_config_rejects_bad_cron_and_unknown_fields(self):
        self._login_as(account("admin"))
        bad_cron = self.client.put(
            "/api/v1/report/configs/daily_report",
            json={
                "row_version": 2,
                "report_name": "日报汇总（新）",
                "cron_expr": "0 0 17 * *",
                "enabled": True,
            },
        )
        self.assertEqual(bad_cron.json()["code"], 400)

        unknown = self.client.put(
            "/api/v1/report/configs/daily_report",
            json={
                "row_version": 2,
                "report_name": "日报汇总（新）",
                "cron_expr": None,
                "enabled": True,
                "report_period": "week",
            },
        )
        self.assertEqual(unknown.json()["code"], 400)

        bad_code = self.client.put(
            "/api/v1/report/configs/not_a_report",
            json={
                "row_version": 2,
                "report_name": "x",
                "cron_expr": None,
                "enabled": True,
            },
        )
        self.assertEqual(bad_code.json()["code"], 400)

    # -- 部门主管 ------------------------------------------------------------

    def test_manager_read_only_own_department_scope(self):
        self._login_as(account("employee", user_id=20, employee_id=10))
        listing = self.client.get("/api/v1/report/list")
        self.assertEqual(listing.json()["code"], 0)
        # 006 范围列未部署：部门报告尚不可生成，主管看不到全公司报告。
        self.assertEqual(listing.json()["data"]["total"], 0)
        self.assertEqual(listing.json()["data"]["items"], [])

        # 直接猜 ID 读全公司报告：404，不泄露跨部门对象是否存在。
        detail = self.client.get("/api/v1/report/1")
        self.assertEqual(detail.json()["code"], 404)

        generate = self.client.post(
            "/api/v1/report/generate",
            json={"report_code": "daily_report"},
            headers={"Idempotency-Key": "manager-gen-key"},
        )
        self.assertEqual(generate.json()["code"], 403)

        configs = self.client.get("/api/v1/report/configs")
        self.assertEqual(configs.json()["code"], 403)

    def test_manager_left_or_without_department_denied(self):
        self._login_as(account("employee", user_id=21, employee_id=12))
        self.assertEqual(self.client.get("/api/v1/report/list").json()["code"], 403)
        self._login_as(account("employee", user_id=22, employee_id=13))
        self.assertEqual(self.client.get("/api/v1/report/list").json()["code"], 403)

    # -- 其余身份 ------------------------------------------------------------

    def test_other_identities_denied(self):
        for acct in (
            account("employee", user_id=30, employee_id=11),
            account("customer", user_id=31),
            account("student", user_id=32),
        ):
            self._login_as(acct)
            self.assertEqual(
                self.client.get("/api/v1/report/list").json()["code"], 403
            )
            self.assertEqual(
                self.client.get("/api/v1/report/configs").json()["code"], 403
            )
            self.assertEqual(
                self.client.get("/api/v1/report/1").json()["code"], 403
            )

    def test_anonymous_denied(self):
        app.dependency_overrides.pop(get_current_account, None)
        response = self.client.get("/api/v1/report/list")
        # 报告接口按 035 契约走 HTTP 200 应用信封：401 身份在 body.code。
        self.assertEqual(response.json()["code"], 401)

    # -- 参数校验走统一信封 ---------------------------------------------------

    def test_validation_envelope(self):
        self._login_as(account("admin"))
        missing_header = self.client.post(
            "/api/v1/report/generate", json={"report_code": "daily_report"}
        )
        self.assertEqual(missing_header.json()["code"], 400)

        bad_code = self.client.post(
            "/api/v1/report/generate",
            json={"report_code": "not_a_report"},
            headers={"Idempotency-Key": "admin-gen-key-2"},
        )
        self.assertEqual(bad_code.json()["code"], 400)

        unknown_query = self.client.get("/api/v1/report/list?limit=10")
        self.assertEqual(unknown_query.json()["code"], 400)

        bad_filter = self.client.get("/api/v1/report/list?report_code=not_a_report")
        self.assertEqual(bad_filter.json()["code"], 400)

        bad_id = self.client.get("/api/v1/report/abc")
        self.assertEqual(bad_id.json()["code"], 400)

        negative_id = self.client.get("/api/v1/report/-1")
        self.assertEqual(negative_id.json()["code"], 400)

        bad_page = self.client.get("/api/v1/report/list?page=0")
        self.assertEqual(bad_page.json()["code"], 400)

    def test_route_order_static_before_dynamic(self):
        self._login_as(account("admin"))
        # /list 不被动态详情捕获。
        listing = self.client.get("/api/v1/report/list")
        self.assertEqual(listing.json()["code"], 0)
        # /configs 不被动态详情捕获。
        configs = self.client.get("/api/v1/report/configs")
        self.assertEqual(configs.json()["code"], 0)

    # -- 授权解析单元 --------------------------------------------------------

    def test_resolve_report_access_branches(self):
        with Session(self.engine) as db:
            admin = resolve_report_access(db, account("admin"))
            self.assertEqual(admin.scope.kind, "all")
            self.assertTrue(admin.can("report.config.write"))

            manager = resolve_report_access(
                db, account("employee", employee_id=10)
            )
            self.assertEqual(manager.scope.kind, "department")
            self.assertEqual(manager.scope.department_id, 7)
            self.assertTrue(manager.can("report.read"))
            self.assertFalse(manager.can("report.generate"))

            with self.assertRaises(Exception):
                resolve_report_access(db, account("employee", employee_id=11))
            with self.assertRaises(Exception):
                resolve_report_access(db, account("customer"))
