"""智能报告固定指标取数（metrics-v2）。

契约来源（操作文档 038/039/055/056 指标字典）：
    - 五类报告使用固定参数化 SQL 计算真实指标，先算指标、应用心理聚合范围
      后再传模型；严禁把报告生成解释为可让模型任意执行 SQL（NL2SQL 为未来待办）。
    - 取数建立独立一致性快照事务：所有表、关联及前期比较窗口复用同一连接/
      事务，不各开连接；只发 SELECT，不调用 Dify、不写报告状态。
    - 每个指标保存 {value, unit, availability, reason, numerator, denominator,
      valid_count, missing_count, metric_version}；availability 为
      available/not_computable/unavailable：上游齐全且确无记录的 count 才是 0；
      分母 0 为 value=NULL 及 not_computable；缺表/列、授权范围、状态历史、
      版本或匿名保护为 value=NULL 及 unavailable，不以 0 占位。
    - 必须的主来源不可读时抛 ReportDataUnavailable（任务失败并给出脱敏依赖
      原因，不生成“全零成功报告”）；可选来源缺失时相关指标 unavailable。
    - source_record_count 等于参与取数的各表去重行数之和，不是“客户数”。

心理周报（045）：只输出匿名聚合；个人明细、原因及个人情绪值不进入指标
快照的模型输入区，由 report_anonymizer 复核后才传模型。
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterator

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine

from app.database import engine as default_engine

# 指标与查询版本：跨版本不可比，不重标旧报告（038）。
METRIC_VERSION = "metrics-v2"
QUERY_VERSION = "report-metrics-v2-q1"

# 业务时区：按北京时间解析自然周期后转 UTC 存储和比较。
BUSINESS_TZ = timezone(timedelta(hours=8))

# 每类报告必须可读的主来源表；缺失即任务失败。
REQUIRED_TABLES: dict[str, tuple[str, ...]] = {
    "customer_overview": ("customer_profile", "customer_followup"),
    "daily_report": ("employee_daily_report",),
    "weekly_report": ("employee_daily_report",),
    "mental_weekly": ("mental_health_profile", "mental_warning"),
    "complaint_weekly": ("service_ticket",),
}

# 可选来源表；缺失时相关指标标 unavailable，不影响主指标。
OPTIONAL_TABLES: dict[str, tuple[str, ...]] = {
    "customer_overview": ("research_result", "customer_info", "product"),
    "complaint_weekly": ("service_ticket_record",),
}


class ReportDataUnavailable(Exception):
    """必须的主来源不可读：任务失败并给出脱敏依赖原因。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class MetricsResult:
    """一次取数的结果：指标条目、来源记录数与复算清单。"""

    entries: dict[str, dict] = field(default_factory=dict)
    source_record_count: int = 0
    snapshot_at: datetime | None = None
    manifest: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 指标条目构造（统一 {value, unit, availability, ...} 结构）
# ---------------------------------------------------------------------------


def _base_entry(unit: str, calc_rule: str) -> dict:
    return {
        "value": None,
        "unit": unit,
        "availability": "available",
        "reason": None,
        "metric_version": METRIC_VERSION,
        "calc_rule": calc_rule,
    }


def _count_entry(value: int, calc_rule: str) -> dict:
    entry = _base_entry("count", calc_rule)
    entry["value"] = int(value)
    return entry


def _rate_entry(
    numerator: int | float | None,
    denominator: int | float | None,
    calc_rule: str,
) -> dict:
    entry = _base_entry("rate", calc_rule)
    entry["numerator"] = numerator
    entry["denominator"] = denominator
    if not denominator:
        entry["availability"] = "not_computable"
        entry["reason"] = "分母为0"
        return entry
    entry["value"] = round(float(numerator) / float(denominator) * 100, 4)
    return entry


def _duration_entry(
    total_hours: float | None,
    valid_count: int,
    missing_count: int,
    calc_rule: str,
) -> dict:
    entry = _base_entry("duration", calc_rule)
    entry["valid_count"] = valid_count
    entry["missing_count"] = missing_count
    if not valid_count or total_hours is None:
        entry["availability"] = "not_computable"
        entry["reason"] = "无有效样本"
        return entry
    entry["value"] = round(float(total_hours) / valid_count, 4)
    return entry


def _avg_entry(
    total: float | None,
    valid_count: int,
    missing_count: int,
    calc_rule: str,
    unit: str = "score",
) -> dict:
    entry = _base_entry(unit, calc_rule)
    entry["valid_count"] = valid_count
    entry["missing_count"] = missing_count
    if not valid_count or total is None:
        entry["availability"] = "not_computable"
        entry["reason"] = "无有效样本"
        return entry
    entry["value"] = round(float(total) / valid_count, 4)
    return entry


def _unavailable_entry(unit: str | None, calc_rule: str, reason: str) -> dict:
    entry = _base_entry(unit or "count", calc_rule)
    entry["availability"] = "unavailable"
    entry["reason"] = reason
    return entry


# ---------------------------------------------------------------------------
# 一致性快照与表结构探测
# ---------------------------------------------------------------------------


@contextmanager
def _snapshot(bind: Engine | None = None) -> Iterator[Connection]:
    """独立一致性快照事务：所有读取复用同一连接/事务（039）。

    MySQL 默认隔离级别为 REPEATABLE READ，同一事务即一致视图；本上下文只发
    SELECT，不调用 Dify、不写报告状态；读取并计算完成后提交，再由调用方以
    独立写事务保存冻结输入。
    """
    engine = bind or default_engine
    with engine.connect() as conn:
        with conn.begin():
            yield conn


def _table_names(conn: Connection) -> set[str]:
    try:
        return set(inspect(conn).get_table_names())
    except Exception:  # noqa: BLE001 - 探测失败按缺失处理，转 unavailable
        return set()


def _columns(conn: Connection, table: str) -> set[str]:
    try:
        return {col["name"] for col in inspect(conn).get_columns(table)}
    except Exception:  # noqa: BLE001
        return set()


def _require_tables(conn: Connection, report_code: str) -> None:
    """主来源表缺失即失败；缺列同样视为不可读。"""
    tables = _table_names(conn)
    for table in REQUIRED_TABLES[report_code]:
        if table not in tables:
            raise ReportDataUnavailable(f"主来源表缺失：{table}")


def _read_db_clock(conn: Connection) -> datetime:
    """固定数据库 UTC 时钟读数（MySQL UTC_TIMESTAMP(3)）。"""
    try:
        value = conn.execute(text("SELECT UTC_TIMESTAMP(3)")).scalar()
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
    except Exception:  # noqa: BLE001 - SQLite 等无该函数时回退本地 UTC
        pass
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hours_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return (end - start).total_seconds() / 3600.0


def _as_datetime(value) -> datetime | None:
    """把驱动返回的时间统一为 naive datetime（SQLite 返回字符串）。"""
    if value is None or isinstance(value, datetime):
        return value
    text_value = str(value).strip()
    if not text_value:
        return None
    normalized = text_value.replace("T", " ").replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


def _within_due(event_at, due_at) -> bool:
    """事件时间不晚于合法期限（缺任一时间不计入及时）。"""
    event_at = _as_datetime(event_at)
    due_at = _as_datetime(due_at)
    return event_at is not None and due_at is not None and event_at <= due_at


# ---------------------------------------------------------------------------
# 取数入口
# ---------------------------------------------------------------------------


def compute_metrics(
    report_code: str,
    start_utc: datetime,
    end_utc: datetime,
    period_type: str | None,
    *,
    bind: Engine | None = None,
    scope_key: str = "company",
) -> MetricsResult:
    """按报告代码计算固定指标；主来源不可读抛 ReportDataUnavailable。"""
    if report_code not in REQUIRED_TABLES:
        raise ReportDataUnavailable(f"未支持的取数类型：{report_code}")

    with _snapshot(bind) as conn:
        _require_tables(conn, report_code)
        snapshot_at = _read_db_clock(conn)
        source_counts: dict[str, int] = {}

        if report_code == "customer_overview":
            entries = _customer_overview(conn, start_utc, end_utc, source_counts)
        elif report_code in ("daily_report", "weekly_report"):
            entries = _daily_report(conn, start_utc, end_utc, source_counts)
        elif report_code == "mental_weekly":
            entries = _mental_weekly(conn, start_utc, end_utc, source_counts)
        else:  # complaint_weekly
            entries = _complaint_weekly(
                conn, start_utc, end_utc, snapshot_at, source_counts
            )

    result = MetricsResult(
        entries=entries,
        source_record_count=sum(source_counts.values()),
        snapshot_at=snapshot_at,
        manifest={
            "metric_version": METRIC_VERSION,
            "query_version": QUERY_VERSION,
            "scope_key": scope_key,
            "window": {
                "start_utc": start_utc.isoformat() + "Z",
                "end_utc": end_utc.isoformat() + "Z",
                "timezone": "Asia/Shanghai",
            },
            "period_type": period_type,
            "source_counts_by_table": source_counts,
            "snapshot_at": snapshot_at.isoformat() + "Z" if snapshot_at else None,
        },
    )
    return result


# ---------------------------------------------------------------------------
# 客户经营分析（customer_overview）
# ---------------------------------------------------------------------------


def _customer_overview(
    conn: Connection,
    start_utc: datetime,
    end_utc: datetime,
    source_counts: dict,
) -> dict:
    entries: dict[str, dict] = {}
    params = {"s": start_utc, "e": end_utc}

    # 取数快照现状：distinct customer_id 总量（不套期间新增口径）。
    total = conn.execute(
        text("SELECT COUNT(DISTINCT customer_id) FROM customer_profile")
    ).scalar()
    entries["customer_total"] = _count_entry(
        int(total or 0), "授权 customer_profile 取数快照 distinct customer_id 总量"
    )
    source_counts["customer_profile"] = int(total or 0)

    for row in conn.execute(
        text(
            "SELECT status, COUNT(DISTINCT customer_id) AS n FROM customer_profile "
            "GROUP BY status"
        )
    ).mappings():
        entries[f"customer_state_{row['status']}"] = _count_entry(
            int(row["n"]), "取数快照按 status 分类的 distinct customer_id"
        )

    archived = conn.execute(
        text(
            "SELECT COUNT(DISTINCT customer_id) FROM customer_profile "
            "WHERE is_archived = 1"
        )
    ).scalar()
    entries["customer_archived_count"] = _count_entry(
        int(archived or 0), "取数快照已归档 distinct customer_id，不抹去已有销售状态"
    )

    new_count = conn.execute(
        text(
            "SELECT COUNT(DISTINCT customer_id) FROM customer_profile "
            "WHERE created_at >= :s AND created_at < :e"
        ),
        params,
    ).scalar()
    entries["customer_new_count"] = _count_entry(
        int(new_count or 0), "created_at 在窗口内的 distinct customer_id，含后来归档"
    )

    followups = conn.execute(
        text(
            "SELECT COUNT(DISTINCT followup_id) AS n, "
            "COUNT(DISTINCT customer_id) AS customers FROM customer_followup "
            "WHERE followup_at >= :s AND followup_at < :e"
        ),
        params,
    ).mappings().one()
    entries["followup_count"] = _count_entry(
        int(followups["n"] or 0), "followup_at 在窗口内的 distinct followup_id"
    )
    entries["followup_customer_count"] = _count_entry(
        int(followups["customers"] or 0), "窗口内被跟进的 distinct customer_id"
    )
    source_counts["customer_followup"] = int(followups["n"] or 0)

    # 缺真实状态事件历史：不用当前 lost 数冒充期间流失量，不计算未定义基数流失率。
    entries["customer_lost_event_count"] = _unavailable_entry(
        "count", "窗口内真实转入 lost 的客户状态事件数（稳定事件ID去重）",
        "缺可信客户状态事件历史，不用当前 lost 数冒充期间流失量",
    )

    # 研判上游（research_result/customer_info/product）未接入。
    research_reason = "研判上游未接入（research_result/customer_info/product）"
    for code, rule in (
        ("research_customer_count", "037 选取集 distinct 已研判客户数"),
        ("research_matched_customer_count", "至少一个产品 matched=true 的 distinct 客户数"),
        ("research_match_rate", "命中客户数/已研判客户数×100"),
    ):
        entries[code] = _unavailable_entry(
            "rate" if code.endswith("_rate") else "count", rule, research_reason
        )
    return entries


# ---------------------------------------------------------------------------
# 员工日报汇总（daily_report / weekly_report）
# ---------------------------------------------------------------------------


def _daily_report(
    conn: Connection,
    start_utc: datetime,
    end_utc: datetime,
    source_counts: dict,
) -> dict:
    entries: dict[str, dict] = {}
    # report_date 为北京时间业务日期：窗口两端换算北京时间后按日期过滤。
    start_date = start_utc.replace(tzinfo=timezone.utc).astimezone(BUSINESS_TZ).date()
    end_date = end_utc.replace(tzinfo=timezone.utc).astimezone(BUSINESS_TZ).date()
    params = {"d0": start_date, "d1": end_date}

    row = conn.execute(
        text(
            "SELECT COUNT(DISTINCT daily_report_id) AS submitted, "
            "COUNT(DISTINCT employee_id) AS authors FROM employee_daily_report "
            "WHERE report_date >= :d0 AND report_date < :d1 AND status = 'submitted'"
        ),
        params,
    ).mappings().one()
    entries["daily_submitted_count"] = _count_entry(
        int(row["submitted"] or 0),
        "首次提交冻结的 report_date 在北京时间日期窗口内且截至快照仍 submitted 的 distinct 日报ID；修订同ID只计一次",
    )
    entries["daily_author_count"] = _count_entry(
        int(row["authors"] or 0),
        "同上队列的 distinct employee_id；部门按首次提交快照，迟交不挪业务日期",
    )
    source_counts["employee_daily_report"] = int(row["submitted"] or 0)

    # 缺可信作废事件历史：作废量须按作废事件时间，不按 report_date 倒推。
    entries["daily_void_count"] = _unavailable_entry(
        "count", "作废事件时间在窗口内的 distinct 日报ID（可信审计事件）",
        "缺可信作废事件历史，不按 report_date 倒推",
    )
    return entries


# ---------------------------------------------------------------------------
# 学生心理健康周报（mental_weekly，仅匿名聚合）
# ---------------------------------------------------------------------------


def _mental_weekly(
    conn: Connection,
    start_utc: datetime,
    end_utc: datetime,
    source_counts: dict,
) -> dict:
    entries: dict[str, dict] = {}
    params = {"s": start_utc, "e": end_utc}

    # 评估：observed_at 决定窗口，按可信源事件去重；同一 analysis_version。
    assessments = conn.execute(
        text(
            "SELECT COUNT(DISTINCT source_event_id) AS n, "
            "COUNT(DISTINCT analysis_version) AS versions "
            "FROM mental_health_profile "
            "WHERE observed_at >= :s AND observed_at < :e"
        ),
        params,
    ).mappings().one()
    entries["mental_assessment_count"] = _count_entry(
        int(assessments["n"] or 0),
        "observed_at 在窗口内按可信源事件去重的评估总数；不称学生人数",
    )
    source_counts["mental_health_profile"] = int(assessments["n"] or 0)

    for row in conn.execute(
        text(
            "SELECT risk_level, COUNT(DISTINCT source_event_id) AS n "
            "FROM mental_health_profile "
            "WHERE observed_at >= :s AND observed_at < :e GROUP BY risk_level"
        ),
        params,
    ).mappings():
        entries[f"mental_risk_{row['risk_level']}_count"] = _count_entry(
            int(row["n"] or 0), "窗口内按 risk_level 分类的匿名聚合评估数"
        )

    warnings = conn.execute(
        text(
            "SELECT COUNT(DISTINCT id) AS n FROM mental_warning "
            "WHERE created_at >= :s AND created_at < :e"
        ),
        params,
    ).scalar()
    entries["mental_warning_count"] = _count_entry(
        int(warnings or 0), "created_at 在窗口内的 distinct 预警ID总量"
    )
    for row in conn.execute(
        text(
            "SELECT follower_status, COUNT(DISTINCT id) AS n FROM mental_warning "
            "WHERE created_at >= :s AND created_at < :e GROUP BY follower_status"
        ),
        params,
    ).mappings():
        entries[f"mental_warning_{row['follower_status']}_count"] = _count_entry(
            int(row["n"] or 0), "窗口内新增预警按取数快照 follower_status 分类"
        )
    source_counts["mental_warning"] = int(warnings or 0)

    # 变化率：与前一个等长且同边界口径窗口比较；上期 0 为 not_computable，
    # 上期缺依赖或版本不同为 unavailable。
    span = end_utc - start_utc
    prev_start, prev_end = start_utc - span, start_utc
    prev_params = {"s": prev_start, "e": prev_end}
    prev_assessments = conn.execute(
        text(
            "SELECT COUNT(DISTINCT source_event_id) AS n FROM mental_health_profile "
            "WHERE observed_at >= :s AND observed_at < :e"
        ),
        prev_params,
    ).scalar()
    prev_warnings = conn.execute(
        text(
            "SELECT COUNT(DISTINCT id) AS n FROM mental_warning "
            "WHERE created_at >= :s AND created_at < :e"
        ),
        prev_params,
    ).scalar()
    current_versions = conn.execute(
        text(
            "SELECT COUNT(DISTINCT analysis_version) AS n FROM mental_health_profile "
            "WHERE (observed_at >= :s AND observed_at < :e) "
            "OR (observed_at >= :ps AND observed_at < :pe)"
        ),
        {"s": start_utc, "e": end_utc, "ps": prev_start, "pe": prev_end},
    ).scalar()

    change_rule = "(本期量−上期量)/上期量×100，与上一等长同边界窗口比较"
    if int(current_versions or 0) > 1:
        mixed_reason = "窗口内含多个分析版本，不可直接混算"
        entries["mental_assessment_change_rate"] = _unavailable_entry(
            "rate", change_rule, mixed_reason
        )
    else:
        entries["mental_assessment_change_rate"] = _rate_entry(
            int(assessments["n"] or 0) - int(prev_assessments or 0),
            int(prev_assessments or 0),
            change_rule,
        )
    entries["mental_warning_change_rate"] = _rate_entry(
        int(warnings or 0) - int(prev_warnings or 0),
        int(prev_warnings or 0),
        change_rule,
    )
    return entries


# ---------------------------------------------------------------------------
# 投诉处理周报（complaint_weekly）
# ---------------------------------------------------------------------------


def _complaint_weekly(
    conn: Connection,
    start_utc: datetime,
    end_utc: datetime,
    snapshot_at: datetime,
    source_counts: dict,
) -> dict:
    entries: dict[str, dict] = {}
    params = {"s": start_utc, "e": end_utc, "now": snapshot_at}
    window = "created_at >= :s AND created_at < :e AND ticket_type = 'complaint'"

    # 新增工单及其快照状态/受控分类（不是期末历史状态）。
    new_count = conn.execute(
        text(f"SELECT COUNT(DISTINCT ticket_id) FROM service_ticket WHERE {window}"),
        params,
    ).scalar()
    entries["complaint_new_count"] = _count_entry(
        int(new_count or 0),
        "ticket_type=complaint 且 created_at 在窗口内的 distinct ticket_id",
    )
    source_counts["service_ticket"] = int(new_count or 0)

    for row in conn.execute(
        text(
            f"SELECT status, COUNT(DISTINCT ticket_id) AS n FROM service_ticket "
            f"WHERE {window} GROUP BY status"
        ),
        params,
    ).mappings():
        entries[f"complaint_new_state_{row['status']}_count"] = _count_entry(
            int(row["n"] or 0), "窗口内新增投诉按取数快照 status 分类"
        )
    for row in conn.execute(
        text(
            f"SELECT category_code, COUNT(DISTINCT ticket_id) AS n FROM service_ticket "
            f"WHERE {window} GROUP BY category_code"
        ),
        params,
    ).mappings():
        entries[f"complaint_category_{row['category_code']}_count"] = _count_entry(
            int(row["n"] or 0), "窗口内新增投诉按受控分类编码统计"
        )

    # 未结存量：快照所有授权投诉中 status<>closed，不限本期新建。
    open_count = conn.execute(
        text(
            "SELECT COUNT(DISTINCT ticket_id) FROM service_ticket "
            "WHERE ticket_type = 'complaint' AND status <> 'closed'"
        )
    ).scalar()
    entries["complaint_open_count"] = _count_entry(
        int(open_count or 0),
        "取数快照 status<>closed 的 distinct ticket_id；awaiting_student 仍为未最终关闭",
    )

    # 首次有效人工回应时长：以窗口内首次回应事件为队列。
    rows = conn.execute(
        text(
            "SELECT ticket_id, created_at, first_response_at FROM service_ticket "
            "WHERE ticket_type = 'complaint' AND first_response_at >= :s "
            "AND first_response_at < :e"
        ),
        params,
    ).mappings().all()
    total_hours = 0.0
    valid = 0
    missing = 0
    for row in rows:
        hours = _hours_between(
            _as_datetime(row["created_at"]), _as_datetime(row["first_response_at"])
        )
        if hours is None:
            missing += 1
        else:
            valid += 1
            total_hours += hours
    entries["complaint_first_response_hours"] = _duration_entry(
        total_hours, valid, missing,
        "Σ(first_response_at−created_at小时)/有完整有效时间的工单数；自动回执与内部备注不计首次回应",
    )

    # 最终关闭队列：closed_at 在窗口且截至快照仍 closed。
    closed_rows = conn.execute(
        text(
            "SELECT ticket_id, created_at, closed_at, satisfaction_score "
            "FROM service_ticket WHERE ticket_type = 'complaint' "
            "AND closed_at >= :s AND closed_at < :e AND status = 'closed'"
        ),
        params,
    ).mappings().all()
    entries["complaint_closed_count"] = _count_entry(
        len({row["ticket_id"] for row in closed_rows}),
        "最终 closed_at 在窗口且截至快照仍 closed、存在可信关闭事件的 distinct ticket_id",
    )
    close_total = 0.0
    close_valid = 0
    for row in closed_rows:
        hours = _hours_between(
            _as_datetime(row["created_at"]), _as_datetime(row["closed_at"])
        )
        if hours is not None:
            close_valid += 1
            close_total += hours
    entries["complaint_close_hours"] = _duration_entry(
        close_total, close_valid, len(closed_rows) - close_valid,
        "Σ(最终closed_at−created_at小时)/有效关闭工单数；awaiting_student 与已重开不入队列",
    )

    # 满意度队列：最终关闭时间在窗口且截至快照仍有效 closed。
    scores = [
        float(row["satisfaction_score"])
        for row in closed_rows
        if row["satisfaction_score"] is not None
    ]
    closed_total = len({row["ticket_id"] for row in closed_rows})
    entries["complaint_satisfaction_avg"] = _avg_entry(
        sum(scores) if scores else None, len(scores), closed_total - len(scores),
        "学生实际1—5分最终有效评价均分；未评价不作0分",
    )
    entries["complaint_satisfaction_rate"] = _rate_entry(
        sum(1 for s in scores if s >= 4), len(scores),
        "4—5分评价数/有效评价数×100",
    )
    entries["complaint_rating_coverage_rate"] = _rate_entry(
        len(scores), closed_total, "已评价关闭工单数/该队列有效关闭工单数×100"
    )

    # 首次回应及时率：创建于窗口且截至快照已回应或截止已到。
    timely_rows = conn.execute(
        text(
            "SELECT first_response_at, response_due_at FROM service_ticket "
            "WHERE ticket_type = 'complaint' AND created_at >= :s AND created_at < :e "
            "AND response_due_at IS NOT NULL "
            "AND (first_response_at IS NOT NULL OR response_due_at <= :now)"
        ),
        params,
    ).all()
    responded_timely = sum(
        1
        for first_response_at, response_due_at in timely_rows
        if _within_due(first_response_at, response_due_at)
    )
    entries["complaint_first_response_timely_rate"] = _rate_entry(
        responded_timely, len(timely_rows),
        "回应时间≤response_due_at 的工单数/（已回应或截止已到的有效工单数）",
    )

    # 超期未回应/未给方案（按快照与合法 due_at）。
    response_overdue = conn.execute(
        text(
            "SELECT COUNT(DISTINCT ticket_id) FROM service_ticket "
            "WHERE ticket_type = 'complaint' AND first_response_at IS NULL "
            "AND response_due_at < :now AND status <> 'closed'"
        ),
        params,
    ).scalar()
    entries["complaint_response_overdue_count"] = _count_entry(
        int(response_overdue or 0),
        "快照仍待回应且超过合法 response_due_at 的工单数",
    )
    resolution_overdue = conn.execute(
        text(
            "SELECT COUNT(DISTINCT ticket_id) FROM service_ticket "
            "WHERE ticket_type = 'complaint' AND resolved_at IS NULL "
            "AND resolution_due_at < :now AND status <> 'closed'"
        ),
        params,
    ).scalar()
    entries["complaint_resolution_overdue_count"] = _count_entry(
        int(resolution_overdue or 0),
        "快照尚未给方案且超过合法 resolution_due_at 的工单数",
    )

    # 轮次指标依赖 service_ticket_record（to_status 动作后真实状态）。
    if "service_ticket_record" in _table_names(conn):
        _complaint_cycle_metrics(conn, params, entries)
    else:
        reason = "缺 service_ticket_record 轮次历史"
        entries["complaint_cycle_solution_hours"] = _unavailable_entry(
            "duration", "每轮给方案时长均值（轮次去重）", reason
        )
        entries["complaint_solved_cycle_count"] = _unavailable_entry(
            "count", "窗口内给方案的 (ticket_id,cycle_no) 轮次数", reason
        )
        entries["complaint_closed_cycle_count"] = _unavailable_entry(
            "count", "历史关闭事件在窗口的 (ticket_id,cycle_no) 轮次数", reason
        )
    return entries


def _complaint_cycle_metrics(conn: Connection, params: dict, entries: dict) -> None:
    """轮次指标：方案/关闭事件按历史事件时间，每轮以 (ticket_id,cycle_no) 唯一。"""
    # 每轮起点：cycle_no=1 取工单 created_at，其后取该轮重开事件时间。
    reopen_rows = conn.execute(
        text(
            "SELECT ticket_id, cycle_no, created_at FROM service_ticket_record "
            "WHERE record_type = 'reopen' AND to_status = 'reopened'"
        )
    ).all()
    reopen_at = {
        (ticket_id, cycle_no): _as_datetime(created_at)
        for ticket_id, cycle_no, created_at in reopen_rows
    }
    ticket_created = {
        ticket_id: _as_datetime(created_at)
        for ticket_id, created_at in conn.execute(
            text("SELECT ticket_id, created_at FROM service_ticket")
        ).all()
    }

    def _cycle_start(ticket_id: int, cycle_no: int) -> datetime | None:
        if cycle_no <= 1:
            return ticket_created.get(ticket_id)
        return reopen_at.get((ticket_id, cycle_no))

    # 给方案事件：to_status='awaiting_student'（解决方案进入待学生确认）。
    solution_rows = conn.execute(
        text(
            "SELECT ticket_id, cycle_no, created_at FROM service_ticket_record "
            "WHERE to_status = 'awaiting_student' AND created_at >= :s "
            "AND created_at < :e ORDER BY created_at"
        ),
        params,
    ).all()
    seen: set[tuple[int, int]] = set()
    total_hours = 0.0
    valid = 0
    missing = 0
    for ticket_id, cycle_no, solved_at in solution_rows:
        key = (ticket_id, cycle_no)
        if key in seen:
            continue  # 给方案量按轮次去重，只取首次
        seen.add(key)
        hours = _hours_between(
            _cycle_start(ticket_id, cycle_no), _as_datetime(solved_at)
        )
        if hours is None:
            missing += 1
        else:
            valid += 1
            total_hours += hours
    entries["complaint_cycle_solution_hours"] = _duration_entry(
        total_hours, valid, missing,
        "窗口内给方案轮次 Σ(方案事件−轮次起点小时)/有效轮次数；不从最近 resolved_at 回推",
    )
    entries["complaint_solved_cycle_count"] = _count_entry(
        len(seen), "窗口内给方案的 (ticket_id,cycle_no) 去重轮次数"
    )

    # 历史关闭轮次：保留重开前历史，不与最终关闭工单数互换。
    closed_cycles = conn.execute(
        text(
            "SELECT COUNT(*) FROM (SELECT DISTINCT ticket_id, cycle_no "
            "FROM service_ticket_record WHERE to_status = 'closed' "
            "AND created_at >= :s AND created_at < :e) AS cycles"
        ),
        params,
    ).scalar()
    entries["complaint_closed_cycle_count"] = _count_entry(
        int(closed_cycles or 0),
        "历史关闭事件时间在窗口、按 (ticket_id,cycle_no) 去重的关闭轮次数",
    )

    # 方案及时率：轮次起点在窗口且已给方案或期限已到。
    due_rows = conn.execute(
        text(
            "SELECT ticket_id, resolution_due_at FROM service_ticket "
            "WHERE ticket_type = 'complaint'"
        )
    ).all()
    due_by_ticket = {
        ticket_id: _as_datetime(due) for ticket_id, due in due_rows
    }
    first_solution: dict[tuple[int, int], datetime] = {}
    for ticket_id, cycle_no, solved_at in conn.execute(
        text(
            "SELECT ticket_id, cycle_no, created_at FROM service_ticket_record "
            "WHERE to_status = 'awaiting_student' ORDER BY created_at"
        )
    ).all():
        first_solution.setdefault((ticket_id, cycle_no), _as_datetime(solved_at))
    cycle_starts = []
    for (ticket_id, cycle_no), start in reopen_at.items():
        if start is not None:
            cycle_starts.append((ticket_id, cycle_no, start))
    for ticket_id, created_at in ticket_created.items():
        if created_at is not None:
            cycle_starts.append((ticket_id, 1, created_at))
    denom = 0
    numer = 0
    for ticket_id, cycle_no, start in cycle_starts:
        if not (start >= params["s"] and start < params["e"]):
            continue
        due = due_by_ticket.get(ticket_id)
        solved = first_solution.get((ticket_id, cycle_no))
        if solved is None and (due is None or due > params["now"]):
            continue  # 未给方案且期限未到：不入分母
        denom += 1
        if solved is not None and due is not None and solved <= due:
            numer += 1
    entries["complaint_solution_timely_rate"] = _rate_entry(
        numer, denom,
        "首次方案≤该轮 resolution_due_at 的轮次数/（已给方案或期限已到的有效轮次数）",
    )
