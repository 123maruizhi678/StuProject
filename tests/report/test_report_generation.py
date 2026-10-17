"""报告生成链路回归：受理幂等、后台执行、原子发布、失败与对账、调度扫描。

无真实外部调用：Dify 客户端以桩替换；取数使用 SQLite 内存库（bind 注入）。
覆盖（操作文档 035/040/041/0127）：
    - 同请求键同参数回放原记录；同键不同参数 409；业务键相同复用不重调模型；
    - pending→running→success/failed 状态机与脱敏 fail_reason；
    - 结果不明（MODEL_OUTCOME_UNKNOWN）不自动重发语义；
    - 正文数字必须映射受控指标，否则失败不发布；
    - pending/running 不发布半成品；success 才返回正文与白名单指标；
    - 定时扫描只补缺失窗口，failed/unknown 不当缺失重发。
"""
import re
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import BackgroundTasks
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import sqlite as sqlite_dialect
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from app.clients.report import ReportDifyError, ReportModelOutcomeUnknown
from app.core.common.response import BusinessException
from app.core.report import ReportAccess, ReportScope
from app.models.report import REPORT_TABLES, ReportConfig, ReportRecord
from app.schemas.report import GenerateReportRequest
from app.services.report import report_service
from app.services.report import report_service as service_module
from app.tasks.report.report_tasks import (
    default_window,
    drain,
    scheduler_scan,
    validate_cron_expr,
)

BUSINESS_TZ = timezone(timedelta(hours=8))
MODEL_OUTCOME_UNKNOWN = "MODEL_OUTCOME_UNKNOWN"


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


def bj_aware(year, month, day, hour=0, minute=0):
    """带时区偏移的显式窗口时间（038：显式 start_time/end_time 必须带偏移）。"""
    return datetime(year, month, day, hour, minute, tzinfo=BUSINESS_TZ)


class FakeDifyClient:
    """桩：按指标构造正文，或按配置抛出失败。"""

    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error
        self.calls = []

    def generate_report(self, report_code, metrics, user="report-service"):
        self.calls.append((report_code, metrics, user))
        if self.error is not None:
            raise self.error
        if self.content is not None:
            return self.content
        submitted = metrics.get("daily_submitted_count", {}).get("value", 0)
        return (
            "## 摘要\n"
            f"本周提交日报 {submitted} 条，整体按时完成。\n"
            "## 建议\n"
            "保持当前节奏，关注未提交员工。"
        )


def admin_access():
    account = SimpleNamespace(user_id=1, identity_type="admin", employee_id=None)
    return ReportAccess(
        account=account,
        actions=frozenset(
            {
                "report.generate",
                "report.read",
                "report.config.read",
                "report.config.write",
            }
        ),
        scope=ReportScope.all_company(),
    )


class ReportGenerationTest(unittest.TestCase):
    def setUp(self):
        service_module._REQUEST_RECEIPTS.clear()
        self.engine = create_engine("sqlite://")
        create_report_tables(self.engine)
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE employee_daily_report ("
                    "daily_report_id INTEGER PRIMARY KEY, employee_id INTEGER, "
                    "report_date DATE, department_id_at_submit INTEGER, "
                    "submitted_content TEXT, status TEXT, submitted_at DATETIME)"
                )
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
            db.add(
                ReportConfig(
                    report_code="weekly_report",
                    report_name="员工日报汇总报告（周）",
                    report_period="week",
                    cron_expr=None,
                    enabled=True,
                    row_version=1,
                )
            )
            db.commit()
        self.addCleanup(self.engine.dispose)
        self.access = admin_access()

    # -- 工具 ---------------------------------------------------------------

    def _seed_daily_rows(self, start_utc):
        start_date = (
            start_utc.replace(tzinfo=timezone.utc).astimezone(BUSINESS_TZ).date()
        )
        with Session(self.engine) as db:
            db.execute(
                text(
                    "INSERT INTO employee_daily_report "
                    "(daily_report_id, employee_id, report_date, status, submitted_at) "
                    "VALUES (1, 10, :d, 'submitted', :s), (2, 11, :d, 'submitted', :s)"
                ),
                {"d": str(start_date), "s": bj(2026, 1, 1, 9)},
            )
            db.commit()

    def _generate(self, *, key="idem-key-0001", payload=None, tasks=None):
        payload = payload or GenerateReportRequest(report_code="daily_report")
        tasks = tasks or BackgroundTasks()
        data = report_service.generate_report(
            Session(self.engine), payload, key, self.access, tasks
        )
        return data, tasks

    # -- 成功链路 -----------------------------------------------------------

    def test_generate_pending_then_publish_success(self):
        window = default_window("day", datetime.utcnow().replace(tzinfo=None))
        self._seed_daily_rows(window[0])
        fake = FakeDifyClient()

        data, tasks = self._generate()
        self.assertEqual(data["status"], "pending")
        self.assertFalse(data["reused"])
        self.assertEqual(len(tasks.tasks), 1)
        record_id = data["report_record_id"]

        with patch.object(service_module, "ReportDifyClient", lambda: fake):
            report_service.run_generation(record_id, bind=self.engine)

        self.assertEqual(len(fake.calls), 1)
        with Session(self.engine) as db:
            record = db.get(ReportRecord, record_id)
            self.assertEqual(record.status, "success")
            self.assertIn("本周提交日报 2 条", record.report_content)
            self.assertIsNotNone(record.generated_at)
            self.assertIsNotNone(record.data_snapshot_at)
            self.assertEqual(record.source_record_count, 2)
            # metric_json 含保留区；对外投影不含。
            self.assertIn("_manifest", record.metric_json)
            rows = db.execute(
                text("SELECT COUNT(*) FROM report_metric WHERE report_record_id = :id"),
                {"id": record_id},
            ).scalar()
            self.assertEqual(rows, len(record.metric_json) - 2)  # 减去两个保留区键

        detail = report_service.get_report(
            Session(self.engine), record_id, self.access
        )
        self.assertEqual(detail["status"], "success")
        self.assertIn("本周提交日报 2 条", detail["report_content"])
        self.assertNotIn("_manifest", detail["metric_json"])
        self.assertEqual(
            detail["metric_json"]["daily_submitted_count"]["value"], 2
        )

    def test_pending_projection_hides_content_and_metrics(self):
        data, _ = self._generate()
        detail = report_service.get_report(
            Session(self.engine), data["report_record_id"], self.access
        )
        self.assertEqual(detail["status"], "pending")
        self.assertIsNone(detail["report_content"])
        self.assertIsNone(detail["metric_json"])
        self.assertIsNone(detail["fail_reason"])

    # -- 幂等 ---------------------------------------------------------------

    def test_same_key_same_params_replays_record(self):
        window = default_window("day", datetime.utcnow().replace(tzinfo=None))
        self._seed_daily_rows(window[0])
        fake = FakeDifyClient()
        first, tasks = self._generate(key="idem-key-replay")
        with patch.object(service_module, "ReportDifyClient", lambda: fake):
            report_service.run_generation(first["report_record_id"], bind=self.engine)

        second, tasks2 = self._generate(key="idem-key-replay", tasks=BackgroundTasks())
        self.assertTrue(second["reused"])
        self.assertEqual(second["report_record_id"], first["report_record_id"])
        # 复用已有记录：不再派发后台任务，不再次调用模型。
        self.assertEqual(len(tasks2.tasks), 0)
        self.assertEqual(second["status"], "success")
        self.assertEqual(len(fake.calls), 1)

    def test_same_key_different_params_conflict(self):
        self._generate(key="idem-key-conflict")
        with self.assertRaises(BusinessException) as caught:
            self._generate(
                key="idem-key-conflict",
                payload=GenerateReportRequest(report_code="weekly_report"),
            )
        self.assertEqual(caught.exception.code, 409)

    def test_different_key_same_business_key_reuses(self):
        window = default_window("day", datetime.utcnow().replace(tzinfo=None))
        self._seed_daily_rows(window[0])
        first, _ = self._generate(key="idem-key-a")
        second, tasks = self._generate(key="idem-key-b", tasks=BackgroundTasks())
        self.assertTrue(second["reused"])
        self.assertEqual(second["report_record_id"], first["report_record_id"])
        self.assertEqual(len(tasks.tasks), 0)

    def test_invalid_idempotency_key_rejected(self):
        with self.assertRaises(BusinessException) as caught:
            report_service.validate_idempotency_key("short")
        self.assertEqual(caught.exception.code, 400)
        with self.assertRaises(BusinessException):
            report_service.validate_idempotency_key(None)
        with self.assertRaises(BusinessException):
            report_service.validate_idempotency_key(" pad-key-0001 ")
        report_service.validate_idempotency_key("valid-key-0001")

    # -- 失败与对账 ----------------------------------------------------------

    def test_model_failure_marks_failed_with_sanitized_reason(self):
        fake = FakeDifyClient(
            error=ReportDifyError("报告生成 Dify 工作流未成功完成")
        )
        data, _ = self._generate()
        with patch.object(service_module, "ReportDifyClient", lambda: fake):
            report_service.run_generation(data["report_record_id"], bind=self.engine)

        detail = report_service.get_report(
            Session(self.engine), data["report_record_id"], self.access
        )
        self.assertEqual(detail["status"], "failed")
        self.assertIsNone(detail["report_content"])
        self.assertIsNone(detail["metric_json"])
        self.assertIn("未成功完成", detail["fail_reason"])

    def test_model_outcome_unknown_not_auto_resent(self):
        fake = FakeDifyClient(error=ReportModelOutcomeUnknown("请求结果不明"))
        data, tasks = self._generate(key="idem-key-unknown")
        with patch.object(service_module, "ReportDifyClient", lambda: fake):
            report_service.run_generation(data["report_record_id"], bind=self.engine)

        with Session(self.engine) as db:
            record = db.get(ReportRecord, data["report_record_id"])
            self.assertEqual(record.status, "failed")
            self.assertTrue(record.fail_reason.startswith(MODEL_OUTCOME_UNKNOWN))

        # 同业务键不同请求键：只回放该失败，不偷偷重新调用模型。
        replay, tasks2 = self._generate(
            key="idem-key-unknown-2", tasks=BackgroundTasks()
        )
        self.assertTrue(replay["reused"])
        self.assertEqual(replay["status"], "failed")
        self.assertEqual(len(tasks2.tasks), 0)
        self.assertEqual(len(fake.calls), 1)

    def test_fabricated_number_fails_reconciliation(self):
        window = default_window("day", datetime.utcnow().replace(tzinfo=None))
        self._seed_daily_rows(window[0])
        fake = FakeDifyClient(content="## 摘要\n本周提交日报 9999 条。")
        data, _ = self._generate()
        with patch.object(service_module, "ReportDifyClient", lambda: fake):
            report_service.run_generation(data["report_record_id"], bind=self.engine)

        with Session(self.engine) as db:
            record = db.get(ReportRecord, data["report_record_id"])
            self.assertEqual(record.status, "failed")
            self.assertIn("无法映射到受控指标", record.fail_reason)
            self.assertIsNone(record.report_content)

    def test_frozen_input_reused_after_failure(self):
        window = default_window("day", datetime.utcnow().replace(tzinfo=None))
        self._seed_daily_rows(window[0])
        failing = FakeDifyClient(error=ReportDifyError("工作流未成功完成"))
        data, _ = self._generate()
        with patch.object(service_module, "ReportDifyClient", lambda: failing):
            report_service.run_generation(data["report_record_id"], bind=self.engine)

        # 冻结输入已保存（取数完成先冻结，再调模型）。
        with Session(self.engine) as db:
            record = db.get(ReportRecord, data["report_record_id"])
            frozen_json = dict(record.metric_json)
            self.assertIn("_manifest", frozen_json)
            # 模拟受控恢复：确定未成功发布前把执行权交还 pending。
            record.status = "pending"
            db.commit()

        # 恢复执行复用冻结输入：传给模型的指标与首次一致，不重新取数。
        ok = FakeDifyClient()
        with patch.object(service_module, "ReportDifyClient", lambda: ok):
            report_service.run_generation(data["report_record_id"], bind=self.engine)
        self.assertEqual(len(ok.calls), 1)
        self.assertEqual(ok.calls[0][1], failing.calls[0][1])
        with Session(self.engine) as db:
            record = db.get(ReportRecord, data["report_record_id"])
            self.assertEqual(record.status, "success")
            self.assertIn("本周提交日报 2 条", record.report_content)

    # -- 参数校验 ------------------------------------------------------------

    def test_window_validation(self):
        cases = [
            GenerateReportRequest(report_code="daily_report", timezone="UTC"),
            GenerateReportRequest(
                report_code="daily_report",
                start_time=bj(2026, 10, 12),
                end_time=None,
            ),
            # 显式时间必须带时区偏移（naive 拒绝）。
            GenerateReportRequest(
                report_code="daily_report",
                start_time=datetime(2026, 10, 12, 0, 0),
                end_time=datetime(2026, 10, 13, 0, 0),
            ),
            # 日报类显式窗口两端须为北京时间 00:00。
            GenerateReportRequest(
                report_code="daily_report",
                start_time=bj_aware(2026, 10, 12, 9),
                end_time=bj_aware(2026, 10, 13, 9),
            ),
            # 结束时间不能晚于受理时刻。
            GenerateReportRequest(
                report_code="daily_report",
                start_time=bj_aware(2027, 1, 1),
                end_time=bj_aware(2027, 1, 2),
            ),
            # 跨度不超过 366 个北京时间自然日。
            GenerateReportRequest(
                report_code="daily_report",
                start_time=bj_aware(2025, 1, 1),
                end_time=bj_aware(2026, 10, 13),
            ),
            # 毫秒以下精度非全零：拒绝悄悄截断。
            GenerateReportRequest(
                report_code="daily_report",
                start_time=bj_aware(2026, 10, 12).replace(microsecond=1500),
                end_time=bj_aware(2026, 10, 13),
            ),
            GenerateReportRequest(report_code="not_a_report"),
        ]
        for payload in cases:
            with self.assertRaises(BusinessException) as caught:
                self._generate(payload=payload)
            self.assertEqual(caught.exception.code, 400, payload.model_dump())

    def test_valid_explicit_window_accepted(self):
        payload = GenerateReportRequest(
            report_code="daily_report",
            start_time=bj_aware(2026, 10, 12),
            end_time=bj_aware(2026, 10, 13),
        )
        data, _ = self._generate(payload=payload)
        self.assertEqual(data["start_time"], bj(2026, 10, 12))
        self.assertEqual(data["end_time"], bj(2026, 10, 13))
        self.assertEqual(data["timezone"], "Asia/Shanghai")

    # -- 列表 ----------------------------------------------------------------

    def test_list_filters_and_projection(self):
        window = default_window("day", datetime.utcnow().replace(tzinfo=None))
        self._seed_daily_rows(window[0])
        fake = FakeDifyClient()
        first, _ = self._generate(key="idem-list-1")
        with patch.object(service_module, "ReportDifyClient", lambda: fake):
            report_service.run_generation(first["report_record_id"], bind=self.engine)
        second, _ = self._generate(
            key="idem-list-2",
            payload=GenerateReportRequest(
                report_code="daily_report",
                start_time=bj_aware(2026, 10, 5),
                end_time=bj_aware(2026, 10, 6),
            ),
        )

        listing = report_service.list_reports(
            Session(self.engine),
            self.access,
            report_code="daily_report",
            status=None,
            page=1,
            page_size=20,
        )
        self.assertEqual(listing["total"], 2)
        # 稳定排序：created_at DESC, report_record_id DESC。
        ids = [item["report_record_id"] for item in listing["items"]]
        self.assertEqual(ids, sorted(ids, reverse=True))
        for item in listing["items"]:
            self.assertNotIn("report_content", item)
            self.assertNotIn("idempotency_key", item)

        failed_only = report_service.list_reports(
            Session(self.engine),
            self.access,
            report_code="daily_report",
            status="failed",
            page=1,
            page_size=20,
        )
        self.assertEqual(failed_only["total"], 0)

        with self.assertRaises(BusinessException) as caught:
            report_service.list_reports(
                Session(self.engine),
                self.access,
                report_code="bad_code",
                status=None,
                page=1,
                page_size=20,
            )
        self.assertEqual(caught.exception.code, 400)

    # -- 对账书写形式 ---------------------------------------------------------

    def test_reconciliation_accepts_float_writing_of_integer_metric(self):
        """整数值指标的浮点书写（75.0）是 JSON 原样引用，不算新增数字。"""
        from app.services.report.report_anonymizer import (
            ContentReconciliationError,
            reconcile_content,
        )

        entries = {
            "complaint_first_response_timely_rate": {
                "value": 75.0,
                "unit": "%",
                "availability": "available",
            },
            "complaint_new_count": {
                "value": 24,
                "unit": "件",
                "availability": "available",
            },
        }
        # 75.0 与 75.00 均应放行；24 放行。
        reconcile_content(
            "complaint_weekly",
            "及时率为 75.0%，另有 75.00% 的余量说明；新建投诉 24 件。",
            entries,
        )
        # 真正的派生数字（差值/比率）仍然必须失败。
        with self.assertRaises(ContentReconciliationError):
            reconcile_content(
                "complaint_weekly",
                "及时率为 75.0%，未回应 3 件占比 12.5%。",
                entries,
            )

    # -- 调度 ----------------------------------------------------------------

    def test_scheduler_scan_creates_missing_windows_once(self):
        with Session(self.engine) as db:
            config = db.get(ReportConfig, 1)
            config.cron_expr = "0 0 17 * * *"
            db.commit()

        now = bj(2026, 10, 16, 18)  # 周五 18:00（北京时间）
        scan = scheduler_scan(Session(self.engine), now_utc=now)
        self.assertGreaterEqual(len(scan["created"]), 1)
        latest = max(scan["created"], key=lambda item: item["start_time"])
        self.assertEqual(latest["start_time"], bj(2026, 10, 15).isoformat() + "Z")
        self.assertEqual(latest["end_time"], bj(2026, 10, 16).isoformat() + "Z")

        # 二次扫描：窗口已有记录，跳过；failed 也不当缺失重发。
        with Session(self.engine) as db:
            for record in db.query(ReportRecord).all():
                record.status = "failed"
            db.commit()
        scan2 = scheduler_scan(Session(self.engine), now_utc=now)
        self.assertEqual(scan2["created"], [])

    def test_drain_executes_pending_records(self):
        with Session(self.engine) as db:
            config = db.get(ReportConfig, 1)
            config.cron_expr = "0 0 17 * * *"
            db.commit()
        now = bj(2026, 10, 16, 18)
        scheduler_scan(Session(self.engine), now_utc=now)
        window = default_window("day", now)
        self._seed_daily_rows(window[0])

        fake = FakeDifyClient()
        with patch.object(service_module, "ReportDifyClient", lambda: fake):
            result = drain(Session(self.engine), max_tasks=10, bind=self.engine)
        self.assertEqual(result["backend"], "record")
        self.assertEqual(len(result["executed"]), len(fake.calls))
        self.assertTrue(
            all(item["status"] == "success" for item in result["executed"])
        )

    def test_cron_and_window_helpers(self):
        validate_cron_expr("0 0 17 * * *")
        validate_cron_expr("0 30 17 * * 5")
        validate_cron_expr(None)
        for bad in ("0 0 17 * *", "60 0 17 * * *", "0 0 25 * * *", "0 0 17 * * 9", "x 0 17 * * *"):
            with self.assertRaises(ValueError):
                validate_cron_expr(bad)

        start, end = default_window("day", bj(2026, 10, 16, 18))
        self.assertEqual(start, bj(2026, 10, 15))
        self.assertEqual(end, bj(2026, 10, 16))
        start, end = default_window("week", bj(2026, 10, 16, 18))
        self.assertEqual(start, bj(2026, 10, 5))
        self.assertEqual(end, bj(2026, 10, 12))


if __name__ == "__main__":
    unittest.main()
