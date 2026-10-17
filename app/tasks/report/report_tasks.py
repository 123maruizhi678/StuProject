"""智能报告后台任务：定时调度、持久任务/租约/恢复。

契约来源（操作文档 0127/0230/041）：
    - 定时生成复用授权生成链路（report_service.run_generation），不是另一个
      对外公开模型入口；daily_report 每天 17:00，其余四类每周五 17:00，
      时区 Asia/Shanghai；17:00 只是触发时刻，不改变统计窗（038）。
    - cron 沿用含秒六字段逻辑方言；适配器显式转换目标库字段数及 weekday
      编码，不能直接把 SQL 中的 5 交给不同周编号库。
    - 调度以 report_code + 可信 scope + 完整窗口 + 版本 + generation_revision
      形成同一稳定业务键；通过唯一任务与租约防多进程重复；attempt 不参与键。
    - 心跳仅扫描应触发且缺失的窗口；failed/unknown 不能因补偿扫描被当作
      “缺失”重发模型。
    - 外部结果不明不盲重发：请求已发出但结果不明置 failed 并标
      MODEL_OUTCOME_UNKNOWN，停止自动重发，按可信 workflow_run_id 核对。
    - 041 拟新增 report_task 持久任务表尚未部署：部署前执行所有权回退为
      report_record 行版本栅栏（进程内租约），跨进程卡死的 running 记录
      不自动重发；部署后由任务表租约与检查点恢复（见 models/report/report.py）。

范围说明（006 未部署）：本期请求与调度 Schema 均无部门选择字段，调度只
生成公司范围报告；任何声明为部门的任务若解析不到合法部门均返回依赖未就绪，
不能降级公司范围。
"""
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.report import ReportRecord, utcnow
from app.repositories.report import report_repository as repo

# 业务时区与调度时刻（用户确认 Asia/Shanghai）。
BUSINESS_TZ = timezone(timedelta(hours=8))
DAILY_TRIGGER = time(17, 0, 0)
WEEKLY_TRIGGER_WEEKDAY = 4  # cron dow：周五（周日=0）

# 执行租约与尝试上限（041 设计默认值，须配置化，不作为运行性能承诺）。
DEFAULT_LEASE_SECONDS = 300
MAX_ATTEMPTS = 3

# 受控调度服务标识（真实自动任务 service_code，不伪造员工）。
SCHEDULER_SERVICE_CODE = "report_scheduler"

# 结果不明标记：调度补偿扫描不得重发（041）。
MODEL_OUTCOME_UNKNOWN = "MODEL_OUTCOME_UNKNOWN"

# 每类周期的补偿回看窗口（按周期个数）。
_LOOKBACK_PERIODS = {"day": 7, "week": 6, "month": 3}


# ---------------------------------------------------------------------------
# cron 适配器（含秒六字段方言）
# ---------------------------------------------------------------------------


def _expand_field(field: str, lo: int, hi: int) -> set[int]:
    """展开单个 cron 字段：*、*/n、a、a-b、a-b/n、逗号列表。"""
    values: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if not part:
            raise ValueError("cron 字段存在空片段")
        step = 1
        if "/" in part:
            part, _, step_text = part.partition("/")
            if not step_text.isdigit() or int(step_text) < 1:
                raise ValueError(f"非法的步长：{part}/{step_text}")
            step = int(step_text)
        if part == "*":
            start, end = lo, hi
        elif "-" in part:
            start_text, _, end_text = part.partition("-")
            if not (start_text.isdigit() and end_text.isdigit()):
                raise ValueError(f"非法的范围：{part}")
            start, end = int(start_text), int(end_text)
        elif part.isdigit():
            start = end = int(part)
        else:
            raise ValueError(f"非法的取值：{part}")
        if start < lo or end > hi or start > end:
            raise ValueError(f"取值越界：{part}")
        values.update(range(start, end + 1, step))
    return values


def parse_cron(expr: str) -> dict:
    """解析含秒六字段 cron：秒 分 时 日 月 周。

    要求时/分/秒为单值（本期调度只触发一次时刻）；日/周均为受限时按
    Vixie 语义“二者任一命中即触发”。
    """
    fields = str(expr).split()
    if len(fields) != 6:
        raise ValueError("cron_expr 须为含秒的六字段（秒 分 时 日 月 周）")
    second_s, minute_s, hour_s, dom_s, month_s, dow_s = fields

    seconds = _expand_field(second_s, 0, 59)
    minutes = _expand_field(minute_s, 0, 59)
    hours = _expand_field(hour_s, 0, 23)
    months = _expand_field(month_s, 1, 12)
    dom = _expand_field(dom_s, 1, 31)
    # cron 周日=0（且 7=周日）；规范为集合时把 7 归一为 0。
    dow = {0 if value == 7 else value for value in _expand_field(dow_s, 0, 7)}

    if len(seconds) != 1 or len(minutes) != 1 or len(hours) != 1:
        raise ValueError("秒/分/时字段须为单值（本期调度每天只触发一个时刻）")

    return {
        "second": next(iter(seconds)),
        "minute": next(iter(minutes)),
        "hour": next(iter(hours)),
        "dom": dom,
        "month": months,
        "dow": dow,
        "dom_restricted": dom_s != "*",
        "dow_restricted": dow_s != "*",
    }


def validate_cron_expr(expr: str | None) -> None:
    """调度适配器语法校验；非法抛 ValueError（由服务层转 400）。"""
    if expr is None:
        return
    parse_cron(expr)


def _cron_matches_date(spec: dict, day: date) -> bool:
    """按 Vixie 语义判断日期是否命中（日月均受限时任一命中）。"""
    if day.month not in spec["month"]:
        return False
    cron_dow = (day.weekday() + 1) % 7  # Python 周一=0 → cron 周日=0
    dom_hit = day.day in spec["dom"]
    dow_hit = cron_dow in spec["dow"]
    if spec["dom_restricted"] and spec["dow_restricted"]:
        return dom_hit or dow_hit
    if spec["dom_restricted"]:
        return dom_hit
    if spec["dow_restricted"]:
        return dow_hit
    return True


# ---------------------------------------------------------------------------
# 统计窗口（038：按北京时间自然周期解析后转 UTC）
# ---------------------------------------------------------------------------


def default_window(report_period: str, now_utc: datetime) -> tuple[datetime, datetime]:
    """上一完整自然日/自然周窗口（北京时间边界，转 naive UTC）。

    day=昨天 00:00 ~ 今天 00:00；week=上周一 00:00 ~ 本周一 00:00；
    不采用最近 24 小时/7 天滚动窗口。
    """
    now_bj = now_utc.replace(tzinfo=timezone.utc).astimezone(BUSINESS_TZ)
    today_bj = datetime(now_bj.year, now_bj.month, now_bj.day, tzinfo=BUSINESS_TZ)
    if report_period == "day":
        start_bj, end_bj = today_bj - timedelta(days=1), today_bj
    elif report_period == "month":
        first_this_month = today_bj.replace(day=1)
        first_last_month = (first_this_month - timedelta(days=1)).replace(day=1)
        start_bj, end_bj = first_last_month, first_this_month
    else:  # week
        this_monday = today_bj - timedelta(days=today_bj.weekday())
        start_bj, end_bj = this_monday - timedelta(days=7), this_monday
    return (
        start_bj.astimezone(timezone.utc).replace(tzinfo=None),
        end_bj.astimezone(timezone.utc).replace(tzinfo=None),
    )


def window_for_trigger(report_period: str, trigger_date: date) -> tuple[datetime, datetime]:
    """触发日期对应的统计窗口（触发时刻不改变统计窗）。

    day：触发日 T 统计 [T-1, T)；week：触发日 T（周五）统计上一完整周
    [周一(T)-7, 周一(T))；month：触发日 T 统计上一个自然月。
    """
    if report_period == "day":
        start_bj = datetime(trigger_date.year, trigger_date.month, trigger_date.day, tzinfo=BUSINESS_TZ) - timedelta(days=1)
        end_bj = datetime(trigger_date.year, trigger_date.month, trigger_date.day, tzinfo=BUSINESS_TZ)
    elif report_period == "month":
        end_bj = datetime(trigger_date.year, trigger_date.month, 1, tzinfo=BUSINESS_TZ)
        start_bj = (end_bj - timedelta(days=1)).replace(day=1)
    else:  # week
        monday = datetime(trigger_date.year, trigger_date.month, trigger_date.day, tzinfo=BUSINESS_TZ) - timedelta(days=trigger_date.weekday())
        start_bj = monday - timedelta(days=7)
        end_bj = monday
    return (
        start_bj.astimezone(timezone.utc).replace(tzinfo=None),
        end_bj.astimezone(timezone.utc).replace(tzinfo=None),
    )


def due_windows(config, now_utc: datetime | None = None) -> list[tuple[datetime, datetime]]:
    """补偿回看内应触发且触发时刻已过的窗口（按时间正序）。"""
    now = now_utc or utcnow()
    spec = parse_cron(config.cron_expr)
    lookback = _LOOKBACK_PERIODS.get(config.report_period, 7)
    span_days = {"day": lookback + 1, "week": lookback * 7 + 1, "month": lookback * 31 + 1}[
        config.report_period
    ]
    now_bj = now.replace(tzinfo=timezone.utc).astimezone(BUSINESS_TZ)
    trigger_time = time(spec["hour"], spec["minute"], spec["second"])

    windows: list[tuple[datetime, datetime]] = []
    for offset in range(span_days, -1, -1):
        day = (now_bj - timedelta(days=offset)).date()
        if not _cron_matches_date(spec, day):
            continue
        trigger_at = datetime(
            day.year, day.month, day.day,
            trigger_time.hour, trigger_time.minute, trigger_time.second,
            tzinfo=BUSINESS_TZ,
        )
        if trigger_at.astimezone(timezone.utc).replace(tzinfo=None) > now:
            continue  # 触发时刻未到
        windows.append(window_for_trigger(config.report_period, day))
    return windows


# ---------------------------------------------------------------------------
# 调度扫描（只补缺失窗口；failed/unknown 不当缺失重发）
# ---------------------------------------------------------------------------


def _scheduled_business_key(report_code: str, config, start_utc: datetime, end_utc: datetime) -> str:
    """调度侧稳定业务键（公司范围；与人工受理同一派生口径）。"""
    from app.services.report.report_service import _business_key

    return _business_key(
        report_code=report_code,
        scope_key="company",
        start_utc=start_utc,
        end_utc=end_utc,
        config=config,
    )


def scheduler_scan(
    db: Session,
    *,
    now_utc: datetime | None = None,
    service_code: str = SCHEDULER_SERVICE_CODE,
) -> dict:
    """扫描启用中的配置，补齐应触发且缺失的窗口（只建单，不执行）。

    已存在任何状态记录（含 failed/unknown）的窗口跳过：补偿扫描不把
    failed/unknown 当缺失重发模型；pending/running 不重复派发。
    """
    now = now_utc or utcnow()
    summary = {"scanned": 0, "created": [], "skipped": []}
    for config in repo.list_configs(db):
        if not config.enabled or not config.cron_expr:
            continue
        summary["scanned"] += 1
        try:
            windows = due_windows(config, now)
        except ValueError as exc:
            summary["skipped"].append(
                {"report_code": config.report_code, "reason": f"cron 非法：{exc}"}
            )
            continue
        for start_utc, end_utc in windows:
            key = _scheduled_business_key(config.report_code, config, start_utc, end_utc)
            if repo.find_record_by_key(db, key) is not None:
                summary["skipped"].append(
                    {
                        "report_code": config.report_code,
                        "start_time": start_utc.isoformat() + "Z",
                        "reason": "窗口已有记录",
                    }
                )
                continue
            record = ReportRecord(
                report_config_id=config.report_config_id,
                report_code=config.report_code,
                idempotency_key=key,
                start_time=start_utc,
                end_time=end_utc,
                timezone="Asia/Shanghai",
                report_version="v1",
                source_record_count=0,
                status="pending",
            )
            try:
                record = repo.insert_record(db, record)
            except Exception:  # noqa: BLE001 - 唯一键竞争：其他进程已建，跳过
                db.rollback()
                summary["skipped"].append(
                    {
                        "report_code": config.report_code,
                        "start_time": start_utc.isoformat() + "Z",
                        "reason": "并发已创建",
                    }
                )
                continue
            summary["created"].append(
                {
                    "report_code": config.report_code,
                    "report_record_id": record.report_record_id,
                    "service_code": service_code,
                    "start_time": start_utc.isoformat() + "Z",
                    "end_time": end_utc.isoformat() + "Z",
                }
            )
    return summary


# ---------------------------------------------------------------------------
# 执行队列（041：持久任务/租约/恢复；表未部署时回退记录行版本栅栏）
# ---------------------------------------------------------------------------


@dataclass
class TaskLease:
    """一次执行租约。"""

    record_id: int
    backend: str
    owner: str
    task_id: int | None = None
    row_version: int | None = None


class ReportTaskQueue:
    """报告执行队列：task_table 后端（已部署时）与 record 后端（回退）。"""

    def __init__(self, db: Session, owner: str | None = None) -> None:
        self.db = db
        self.owner = owner or f"report-worker-{os.getpid()}"
        self.backend = (
            "task_table" if repo.report_task_table_exists(db) else "record"
        )
        self._attempts: dict[int, int] = {}

    # -- 领取 ---------------------------------------------------------------

    def claim(self) -> TaskLease | None:
        """原子领取一个待执行报告；无可用任务返回 None。"""
        if self.backend == "task_table":
            return self._claim_task_table()
        return self._claim_record()

    def _claim_record(self) -> TaskLease | None:
        pending = self.db.execute(
            text(
                "SELECT report_record_id FROM report_record WHERE status = 'pending' "
                "ORDER BY created_at, report_record_id LIMIT 1"
            )
        ).scalars().all()
        for record_id in pending:
            record = repo.claim_record(self.db, record_id)
            if record is None:
                continue  # 竞争失败，尝试下一个
            attempts = self._attempts.get(record_id, 0) + 1
            self._attempts[record_id] = attempts
            if attempts > MAX_ATTEMPTS:
                # 超过安全重试上限：不自动重发，留待受控恢复。
                repo.mark_failed(
                    self.db,
                    record,
                    expected_row_version=record.row_version,
                    fail_reason=f"超过安全重试上限（{MAX_ATTEMPTS}），停止自动重发",
                )
                continue
            return TaskLease(
                record_id=record_id,
                backend="record",
                owner=self.owner,
                row_version=record.row_version,
            )
        return None

    def _claim_task_table(self) -> TaskLease | None:
        now = utcnow()
        rows = self.db.execute(
            text(
                "SELECT report_task_id, report_record_id, row_version FROM report_task "
                "WHERE status = 'pending' AND attempt_count < :max_attempts "
                "AND (lease_expires_at IS NULL OR lease_expires_at < :now) "
                "ORDER BY report_task_id LIMIT 5"
            ),
            {"max_attempts": MAX_ATTEMPTS, "now": now},
        ).mappings().all()
        for row in rows:
            claimed = self.db.execute(
                text(
                    "UPDATE report_task SET status = 'running', lease_owner = :owner, "
                    "lease_expires_at = :lease_until, attempt_count = attempt_count + 1, "
                    "row_version = row_version + 1, updated_at = :now "
                    "WHERE report_task_id = :task_id AND status = 'pending' "
                    "AND row_version = :row_version"
                ),
                {
                    "owner": self.owner,
                    "lease_until": now + timedelta(seconds=DEFAULT_LEASE_SECONDS),
                    "now": now,
                    "task_id": row["report_task_id"],
                    "row_version": row["row_version"],
                },
            )
            if claimed.rowcount != 1:
                continue
            record = repo.claim_record(self.db, row["report_record_id"])
            if record is None:
                # 记录已被其他执行者领取：释放任务租约回 pending。
                self.db.execute(
                    text(
                        "UPDATE report_task SET status = 'pending', lease_owner = NULL, "
                        "lease_expires_at = NULL, row_version = row_version + 1, "
                        "updated_at = :now WHERE report_task_id = :task_id"
                    ),
                    {"now": now, "task_id": row["report_task_id"]},
                )
                self.db.commit()
                continue
            return TaskLease(
                record_id=row["report_record_id"],
                backend="task_table",
                owner=self.owner,
                task_id=row["report_task_id"],
                row_version=record.row_version,
            )
        return None

    # -- 续租 / 终态 --------------------------------------------------------

    def heartbeat(self, lease: TaskLease) -> bool:
        """续租；租约丢失（被接管）返回 False，执行者应停止写回。"""
        if lease.backend != "task_table" or lease.task_id is None:
            return True  # record 后端无跨进程租约，进程内执行不续租
        now = utcnow()
        result = self.db.execute(
            text(
                "UPDATE report_task SET lease_expires_at = :lease_until, "
                "updated_at = :now WHERE report_task_id = :task_id "
                "AND lease_owner = :owner AND status = 'running'"
            ),
            {
                "lease_until": now + timedelta(seconds=DEFAULT_LEASE_SECONDS),
                "now": now,
                "task_id": lease.task_id,
                "owner": lease.owner,
            },
        )
        self.db.commit()
        return result.rowcount == 1

    def complete(self, lease: TaskLease) -> None:
        if lease.backend == "task_table" and lease.task_id is not None:
            self.db.execute(
                text(
                    "UPDATE report_task SET status = 'success', lease_owner = NULL, "
                    "lease_expires_at = NULL, last_error = NULL, "
                    "row_version = row_version + 1, updated_at = :now "
                    "WHERE report_task_id = :task_id"
                ),
                {"now": utcnow(), "task_id": lease.task_id},
            )
            self.db.commit()

    def fail(self, lease: TaskLease, reason: str, *, outcome_unknown: bool = False) -> None:
        if lease.backend == "task_table" and lease.task_id is not None:
            self.db.execute(
                text(
                    "UPDATE report_task SET status = 'failed', lease_owner = NULL, "
                    "lease_expires_at = NULL, last_error = :reason, "
                    "row_version = row_version + 1, updated_at = :now "
                    "WHERE report_task_id = :task_id"
                ),
                {
                    "reason": f"{MODEL_OUTCOME_UNKNOWN}: {reason}"
                    if outcome_unknown
                    else reason,
                    "now": utcnow(),
                    "task_id": lease.task_id,
                },
            )
            self.db.commit()

    def recover_stalled(self) -> dict:
        """恢复过期租约任务（仅 task_table 后端）。

        结果不明不盲重发：无受控结果回执可核对的一律置 failed 并标
        MODEL_OUTCOME_UNKNOWN，停止自动重发；safe 阶段（确定未发起调用）
                才可安全重排。record 后端无跨进程租约，卡死记录不自动重发。
        """
        if self.backend != "task_table":
            return {"recovered": [], "reason": "report_task 未部署，回退记录栅栏"}
        now = utcnow()
        stalled = self.db.execute(
            text(
                "SELECT report_task_id, model_checkpoint FROM report_task "
                "WHERE status = 'running' AND lease_expires_at IS NOT NULL "
                "AND lease_expires_at < :now"
            ),
            {"now": now},
        ).mappings().all()
        recovered = []
        for row in stalled:
            checkpoint = row["model_checkpoint"] or {}
            phase = checkpoint.get("phase") if isinstance(checkpoint, dict) else None
            if phase == "not_sent":
                self.db.execute(
                    text(
                        "UPDATE report_task SET status = 'pending', lease_owner = NULL, "
                        "lease_expires_at = NULL, row_version = row_version + 1, "
                        "updated_at = :now WHERE report_task_id = :task_id"
                    ),
                    {"now": now, "task_id": row["report_task_id"]},
                )
                recovered.append({"report_task_id": row["report_task_id"], "action": "reschedule"})
            else:
                # 已发出但结果不明（或无检查点）：不得自动重发。
                self.db.execute(
                    text(
                        "UPDATE report_task SET status = 'failed', lease_owner = NULL, "
                        "lease_expires_at = NULL, last_error = :reason, "
                        "row_version = row_version + 1, updated_at = :now "
                        "WHERE report_task_id = :task_id"
                    ),
                    {
                        "reason": f"{MODEL_OUTCOME_UNKNOWN}: 执行租约过期且无受控结果回执",
                        "now": now,
                        "task_id": row["report_task_id"],
                    },
                )
                recovered.append(
                    {"report_task_id": row["report_task_id"], "action": "fail_unknown"}
                )
        self.db.commit()
        return {"recovered": recovered}


def drain(
    db: Session,
    *,
    max_tasks: int = 10,
    now_utc: datetime | None = None,
    bind=None,
) -> dict:
    """执行一轮待生成报告：领取 → 生成链路 → 续租 → 终态。

    bind 仅供测试注入独立数据源；生产使用全局引擎。
    """
    from app.services.report.report_service import run_generation

    queue = ReportTaskQueue(db)
    summary = {"backend": queue.backend, "executed": [], "skipped": []}
    for _ in range(max_tasks):
        lease = queue.claim()
        if lease is None:
            break
        if not queue.heartbeat(lease):
            summary["skipped"].append(
                {"report_record_id": lease.record_id, "reason": "租约被接管"}
            )
            continue
        run_generation(lease.record_id, user=f"report-{queue.owner}", bind=bind)
        record = repo.get_record(db, lease.record_id)
        if record is None:
            summary["skipped"].append(
                {"report_record_id": lease.record_id, "reason": "记录不存在"}
            )
            continue
        if record.status == "success":
            queue.complete(lease)
            summary["executed"].append(
                {"report_record_id": lease.record_id, "status": "success"}
            )
        elif record.status == "failed":
            outcome_unknown = MODEL_OUTCOME_UNKNOWN in (record.fail_reason or "")
            queue.fail(
                lease, record.fail_reason or "生成失败", outcome_unknown=outcome_unknown
            )
            summary["executed"].append(
                {"report_record_id": lease.record_id, "status": "failed"}
            )
        else:
            queue.fail(lease, "执行未达终态")
            summary["skipped"].append(
                {"report_record_id": lease.record_id, "reason": "执行未达终态"}
            )
    return summary


def run_once(db: Session, *, now_utc: datetime | None = None) -> dict:
    """一次完整调度周期：恢复过期租约 → 扫描缺失窗口 → 执行待生成报告。"""
    queue = ReportTaskQueue(db)
    return {
        "recover": queue.recover_stalled(),
        "scan": scheduler_scan(db, now_utc=now_utc),
        "drain": drain(db, now_utc=now_utc),
    }
