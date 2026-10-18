"""固定指标取数回归：metrics-v2 口径、可用性语义与一致性快照；无真实外部调用。

覆盖（操作文档 038/039/055/056）：
    - 日报/投诉/心理五类指标的固定口径；
    - count=0 仅在上游齐全且确无记录时出现；分母 0 为 not_computable；
      缺表/列为 unavailable，不以 0 占位；
    - 主来源表缺失抛 ReportDataUnavailable（任务失败，不生成全零成功报告）；
    - 窗口边界 [start,end)，end 事件归下一期。
"""
import re
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.dialects import sqlite as sqlite_dialect
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from app.models.report import REPORT_TABLES
from app.services.report.report_metrics import (
    ReportDataUnavailable,
    compute_metrics,
)

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
    """北京时间 → naive UTC（与库里 DATETIME 存储口径一致）。"""
    return (
        datetime(year, month, day, hour, minute, tzinfo=BUSINESS_TZ)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


class MetricsFixture:
    """SQLite 内存库 + 报告三表 + 上游最小表。"""

    def __init__(self):
        self.engine = create_engine("sqlite://")
        create_report_tables(self.engine)
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE employee_daily_report ("
                    "daily_report_id INTEGER PRIMARY KEY, employee_id INTEGER, "
                    "report_date DATE, department_id_at_submit INTEGER, "
                    "submitted_content TEXT, ai_summary TEXT, "
                    "status TEXT, submitted_at DATETIME)"
                )
            )
            conn.execute(
                text(
                    "CREATE TABLE service_ticket ("
                    "ticket_id INTEGER PRIMARY KEY, ticket_type TEXT, "
                    "category_code TEXT, status TEXT, first_response_at DATETIME, "
                    "response_due_at DATETIME, resolution_due_at DATETIME, "
                    "resolved_at DATETIME, closed_at DATETIME, "
                    "satisfaction_score INTEGER, created_at DATETIME, "
                    "handling_department_id INTEGER)"
                )
            )
            conn.execute(
                text(
                    "CREATE TABLE service_ticket_record ("
                    "ticket_record_id INTEGER PRIMARY KEY, ticket_id INTEGER, "
                    "record_type TEXT, to_status TEXT, cycle_no INTEGER, "
                    "created_at DATETIME)"
                )
            )
            conn.execute(
                text(
                    "CREATE TABLE customer_profile ("
                    "customer_id INTEGER PRIMARY KEY, status TEXT, "
                    "is_archived INTEGER, created_at DATETIME)"
                )
            )
            conn.execute(
                text(
                    "CREATE TABLE customer_followup ("
                    "followup_id INTEGER PRIMARY KEY, customer_id INTEGER, "
                    "followup_at DATETIME)"
                )
            )
            conn.execute(
                text(
                    "CREATE TABLE mental_health_profile ("
                    "id INTEGER PRIMARY KEY, student_id INTEGER, risk_level TEXT, "
                    "observed_at DATETIME, source_event_id TEXT, analysis_version TEXT)"
                )
            )
            conn.execute(
                text(
                    "CREATE TABLE mental_warning ("
                    "id INTEGER PRIMARY KEY, student_id INTEGER, profile_id INTEGER, "
                    "risk_level TEXT, follower_status TEXT, created_at DATETIME)"
                )
            )


class ReportMetricsTest(unittest.TestCase):
    def setUp(self):
        self.fixture = MetricsFixture()
        self.addCleanup(self.fixture.engine.dispose)

    def metrics(self, code, start, end, period="week"):
        return compute_metrics(
            code, start, end, period, bind=self.fixture.engine, scope_key="company"
        )

    # -- 日报 ---------------------------------------------------------------

    def test_daily_report_counts_submitted_only(self):
        with Session(self.fixture.engine) as db:
            db.execute(
                text(
                    "INSERT INTO employee_daily_report "
                    "(daily_report_id, employee_id, report_date, status, submitted_at) "
                    "VALUES (1, 10, '2026-10-12', 'submitted', :s), "
                    "(2, 10, '2026-10-13', 'submitted', :s), "
                    "(3, 11, '2026-10-13', 'submitted', :s), "
                    "(4, 12, '2026-10-14', 'void', :s)"
                ),
                {"s": bj(2026, 10, 12, 9)},
            )
            db.commit()

        result = self.metrics(
            "daily_report", bj(2026, 10, 12), bj(2026, 10, 15), "day"
        )
        entries = result.entries
        self.assertEqual(entries["daily_submitted_count"]["value"], 3)
        self.assertEqual(entries["daily_author_count"]["value"], 2)
        # 缺可信作废事件历史：unavailable，不按 report_date 倒推冒充。
        self.assertEqual(
            entries["daily_void_count"]["availability"], "unavailable"
        )
        self.assertEqual(result.source_record_count, 3)

    def test_daily_report_window_end_exclusive(self):
        with Session(self.fixture.engine) as db:
            db.execute(
                text(
                    "INSERT INTO employee_daily_report "
                    "(daily_report_id, employee_id, report_date, status, submitted_at) "
                    "VALUES (1, 10, '2026-10-14', 'submitted', :s)"
                ),
                {"s": bj(2026, 10, 14, 9)},
            )
            db.commit()

        result = self.metrics(
            "daily_report", bj(2026, 10, 12), bj(2026, 10, 14), "day"
        )
        # 10-14 的日报不属于 [10-12, 10-14) 窗口。
        self.assertEqual(result.entries["daily_submitted_count"]["value"], 0)

    def test_daily_report_empty_window_is_zero_not_unavailable(self):
        result = self.metrics(
            "daily_report", bj(2026, 10, 12), bj(2026, 10, 13), "day"
        )
        entry = result.entries["daily_submitted_count"]
        self.assertEqual(entry["value"], 0)
        self.assertEqual(entry["availability"], "available")

    def test_daily_report_summaries_reuse_ai_summary(self):
        with Session(self.fixture.engine) as db:
            db.execute(
                text(
                    "INSERT INTO employee_daily_report "
                    "(daily_report_id, employee_id, report_date, submitted_content, "
                    "ai_summary, status, submitted_at) VALUES "
                    "(1, 10, '2026-10-12', 'today', '完成客户 A 需求', 'submitted', :s), "
                    "(2, 11, '2026-10-12', 'today', '   ', 'submitted', :s), "
                    "(3, 12, '2026-10-13', 'today', NULL, 'submitted', :s)"
                ),
                {"s": bj(2026, 10, 12, 9)},
            )
            db.commit()

        result = self.metrics(
            "daily_report", bj(2026, 10, 12), bj(2026, 10, 15), "day"
        )
        # 只保留非空 ai_summary，空串/纯空白跳过；按 report_date/employee_id 稳定排序。
        self.assertEqual(result.daily_summaries, ["完成客户 A 需求"])

    # -- 投诉 ---------------------------------------------------------------

    def _seed_tickets(self):
        with Session(self.fixture.engine) as db:
            db.execute(
                text(
                    "INSERT INTO service_ticket "
                    "(ticket_id, ticket_type, category_code, status, first_response_at, "
                    "response_due_at, resolution_due_at, resolved_at, closed_at, "
                    "satisfaction_score, created_at, handling_department_id) VALUES "
                    # 窗口内新建、及时回应、最终关闭且评分 5。
                    "(1, 'complaint', 'teaching', 'closed', :r1, :due, :due, :r1, :cl, 5, :c1, 3), "
                    # 窗口内新建、超期未回应、仍未关闭。
                    "(2, 'complaint', 'visa', 'processing', NULL, :due, :due, NULL, NULL, NULL, :c1, 3), "
                    # 窗口外新建与回应/关闭：所有事件均不在窗口内。
                    "(3, 'complaint', 'teaching', 'closed', :r0, :due, :due, :r0, :c0, 3, :c0, 3), "
                    # 建议类工单不混入投诉。
                    "(4, 'suggestion', 'teaching', 'closed', :r1, :due, :due, :r1, :c1, 4, :c1, 3)"
                ),
                {
                    "c0": bj(2026, 10, 1, 10),
                    "c1": bj(2026, 10, 12, 10),
                    "cl": bj(2026, 10, 13, 9),
                    "r0": bj(2026, 10, 1, 14),
                    "r1": bj(2026, 10, 12, 14),
                    "due": bj(2026, 10, 13, 10),
                },
            )
            db.execute(
                text(
                    "INSERT INTO service_ticket_record "
                    "(ticket_record_id, ticket_id, record_type, to_status, cycle_no, created_at) VALUES "
                    "(1, 1, 'response', 'awaiting_student', 1, :r1), "
                    "(2, 1, 'close', 'closed', 1, :c1)"
                ),
                {"r1": bj(2026, 10, 12, 14), "c1": bj(2026, 10, 13, 9)},
            )
            db.commit()

    def test_complaint_new_and_state_counts(self):
        self._seed_tickets()
        result = self.metrics(
            "complaint_weekly", bj(2026, 10, 12), bj(2026, 10, 19), "week"
        )
        entries = result.entries
        self.assertEqual(entries["complaint_new_count"]["value"], 2)
        self.assertEqual(entries["complaint_new_state_closed_count"]["value"], 1)
        self.assertEqual(entries["complaint_new_state_processing_count"]["value"], 1)
        self.assertEqual(entries["complaint_category_teaching_count"]["value"], 1)
        self.assertEqual(entries["complaint_category_visa_count"]["value"], 1)
        # 快照未结存量：ticket2 未关闭（ticket4 是 suggestion 不混入）。
        self.assertEqual(entries["complaint_open_count"]["value"], 1)

    def test_complaint_duration_and_satisfaction(self):
        self._seed_tickets()
        result = self.metrics(
            "complaint_weekly", bj(2026, 10, 12), bj(2026, 10, 19), "week"
        )
        entries = result.entries
        # 首次回应：ticket1 created 10:00 → responded 14:00 = 4 小时。
        self.assertEqual(entries["complaint_first_response_hours"]["value"], 4.0)
        self.assertEqual(entries["complaint_first_response_hours"]["valid_count"], 1)
        # 最终关闭：仅 ticket1（closed_at 10-13 在窗口且仍 closed）。
        self.assertEqual(entries["complaint_closed_count"]["value"], 1)
        self.assertEqual(entries["complaint_close_hours"]["value"], 23.0)
        self.assertEqual(entries["complaint_satisfaction_avg"]["value"], 5.0)
        self.assertEqual(entries["complaint_satisfaction_rate"]["value"], 100.0)
        self.assertEqual(entries["complaint_rating_coverage_rate"]["value"], 100.0)
        # 轮次指标：来自 service_ticket_record。
        self.assertEqual(entries["complaint_solved_cycle_count"]["value"], 1)
        self.assertEqual(entries["complaint_closed_cycle_count"]["value"], 1)

    def test_complaint_timely_rate_denominator(self):
        self._seed_tickets()
        result = self.metrics(
            "complaint_weekly", bj(2026, 10, 12), bj(2026, 10, 19), "week"
        )
        entries = result.entries
        # ticket1 及时（14:00 ≤ due 10-13 10:00）；ticket2 未回应且期限已到入分母。
        rate = entries["complaint_first_response_timely_rate"]
        self.assertEqual(rate["denominator"], 2)
        self.assertEqual(rate["numerator"], 1)
        self.assertEqual(rate["value"], 50.0)
        # ticket2 超期未回应。
        self.assertEqual(entries["complaint_response_overdue_count"]["value"], 1)

    def test_complaint_without_record_table_marks_unavailable(self):
        self._seed_tickets()
        with Session(self.fixture.engine) as db:
            db.execute(text("DROP TABLE service_ticket_record"))
            db.commit()
        result = self.metrics(
            "complaint_weekly", bj(2026, 10, 12), bj(2026, 10, 19), "week"
        )
        self.assertEqual(
            result.entries["complaint_closed_cycle_count"]["availability"],
            "unavailable",
        )
        # 主指标不受可选表缺失影响。
        self.assertEqual(result.entries["complaint_new_count"]["value"], 2)

    def test_complaint_new_change_rate(self):
        self._seed_tickets()
        # 上一等长窗口 [10-05, 10-12) 补一条投诉。
        with Session(self.fixture.engine) as db:
            db.execute(
                text(
                    "INSERT INTO service_ticket "
                    "(ticket_id, ticket_type, category_code, status, created_at, "
                    "handling_department_id) VALUES (10, 'complaint', 'teaching', "
                    "'closed', :c, 3)"
                ),
                {"c": bj(2026, 10, 6, 10)},
            )
            db.commit()
        result = self.metrics(
            "complaint_weekly", bj(2026, 10, 12), bj(2026, 10, 19), "week"
        )
        rate = result.entries["complaint_new_change_rate"]
        # 本期 2，上期 1：(2 - 1) / 1 * 100 = 100.0
        self.assertEqual(rate["value"], 100.0)
        self.assertEqual(rate["availability"], "available")

    # -- 心理 ---------------------------------------------------------------

    def _seed_mental(self):
        with Session(self.fixture.engine) as db:
            db.execute(
                text(
                    "INSERT INTO mental_health_profile "
                    "(id, student_id, risk_level, observed_at, source_event_id, analysis_version) VALUES "
                    "(1, 1, 'low', :o1, 'e1', 'v1'), "
                    "(2, 2, 'high', :o1, 'e2', 'v1'), "
                    "(3, 3, 'critical', :o2, 'e3', 'v1')"
                ),
                {"o1": bj(2026, 10, 13, 9), "o2": bj(2026, 10, 12, 9)},
            )
            db.execute(
                text(
                    "INSERT INTO mental_warning "
                    "(id, student_id, profile_id, risk_level, follower_status, created_at) VALUES "
                    "(1, 2, 2, 'high', 'pending', :c), "
                    "(2, 3, 3, 'critical', 'closed', :c)"
                ),
                {"c": bj(2026, 10, 14, 9)},
            )
            db.commit()

    def test_mental_weekly_anonymous_aggregates(self):
        self._seed_mental()
        result = self.metrics(
            "mental_weekly", bj(2026, 10, 12), bj(2026, 10, 19), "week"
        )
        entries = result.entries
        self.assertEqual(entries["mental_assessment_count"]["value"], 3)
        self.assertEqual(entries["mental_risk_low_count"]["value"], 1)
        self.assertEqual(entries["mental_risk_high_count"]["value"], 1)
        self.assertEqual(entries["mental_risk_critical_count"]["value"], 1)
        self.assertEqual(entries["mental_warning_count"]["value"], 2)
        self.assertEqual(entries["mental_warning_pending_count"]["value"], 1)
        self.assertEqual(entries["mental_warning_closed_count"]["value"], 1)
        # 上一等长窗口无记录：变化率 not_computable，不用 0 冒充分母。
        self.assertEqual(
            entries["mental_assessment_change_rate"]["availability"],
            "not_computable",
        )
        self.assertIsNone(entries["mental_assessment_change_rate"]["value"])

    def test_mental_change_rate_against_previous_window(self):
        self._seed_mental()
        # 上一窗口 [10-05, 10-12) 放入 2 条评估。
        with Session(self.fixture.engine) as db:
            db.execute(
                text(
                    "INSERT INTO mental_health_profile "
                    "(id, student_id, risk_level, observed_at, source_event_id, analysis_version) VALUES "
                    "(10, 1, 'low', :o, 'p1', 'v1'), "
                    "(11, 2, 'low', :o, 'p2', 'v1')"
                ),
                {"o": bj(2026, 10, 8, 9)},
            )
            db.commit()
        result = self.metrics(
            "mental_weekly", bj(2026, 10, 12), bj(2026, 10, 19), "week"
        )
        rate = result.entries["mental_assessment_change_rate"]
        # (3 - 2) / 2 * 100 = 50
        self.assertEqual(rate["value"], 50.0)
        self.assertEqual(rate["availability"], "available")

    def test_mental_missing_source_fails_task(self):
        with Session(self.fixture.engine) as db:
            db.execute(text("DROP TABLE mental_warning"))
            db.commit()
        with self.assertRaises(ReportDataUnavailable):
            self.metrics("mental_weekly", bj(2026, 10, 12), bj(2026, 10, 19), "week")

    # -- 客户 ---------------------------------------------------------------

    def test_customer_overview_snapshot_and_window(self):
        with Session(self.fixture.engine) as db:
            db.execute(
                text(
                    "INSERT INTO customer_profile (customer_id, status, is_archived, created_at) VALUES "
                    "(1, 'signed', 0, :old), "
                    "(2, 'new', 0, :new), "
                    "(3, 'lost', 1, :old)"
                ),
                {"old": bj(2026, 9, 1, 9), "new": bj(2026, 10, 13, 9)},
            )
            db.execute(
                text(
                    "INSERT INTO customer_followup (followup_id, customer_id, followup_at) VALUES "
                    "(1, 1, :f), (2, 1, :f), (3, 2, :f)"
                ),
                {"f": bj(2026, 10, 14, 9)},
            )
            db.commit()

        result = self.metrics(
            "customer_overview", bj(2026, 10, 12), bj(2026, 10, 19), "week"
        )
        entries = result.entries
        self.assertEqual(entries["customer_total"]["value"], 3)
        self.assertEqual(entries["customer_archived_count"]["value"], 1)
        self.assertEqual(entries["customer_state_signed"]["value"], 1)
        self.assertEqual(entries["customer_new_count"]["value"], 1)
        self.assertEqual(entries["followup_count"]["value"], 3)
        self.assertEqual(entries["followup_customer_count"]["value"], 2)
        # 缺状态事件历史与研判上游：unavailable，不用当前 lost 数冒充。
        self.assertEqual(
            entries["customer_lost_event_count"]["availability"], "unavailable"
        )
        self.assertEqual(
            entries["research_match_rate"]["availability"], "unavailable"
        )

    def test_customer_new_change_rate(self):
        with Session(self.fixture.engine) as db:
            db.execute(
                text(
                    "INSERT INTO customer_profile (customer_id, status, is_archived, created_at) VALUES "
                    "(1, 'signed', 0, :prev1), "
                    "(2, 'signed', 0, :prev2), "
                    "(3, 'new', 0, :cur)"
                ),
                {
                    "prev1": bj(2026, 10, 6, 9),
                    "prev2": bj(2026, 10, 7, 9),
                    "cur": bj(2026, 10, 13, 9),
                },
            )
            db.commit()

        result = self.metrics(
            "customer_overview", bj(2026, 10, 12), bj(2026, 10, 19), "week"
        )
        rate = result.entries["customer_new_change_rate"]
        # 本期 1，上期 2：(1 - 2) / 2 * 100 = -50.0
        self.assertEqual(rate["value"], -50.0)
        self.assertEqual(rate["availability"], "available")


if __name__ == "__main__":
    unittest.main()
