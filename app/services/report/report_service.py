"""智能报告业务逻辑层：配置管理 + 报告生成链路（收单→取数→AI→发布）。

生成链路（0127/040/041）：
    收单（校验、算窗、幂等、建 pending）→ 后台执行：
    领取执行权（pending→running 行版本栅栏）→ 固定取数算指标
    （report_metrics，一致性快照）→ 保存冻结输入 → 心理匿名聚合后传模型
    （report_anonymizer + clients/report_dify）→ 剥离推理内容 → 正文对账 →
    同一事务原子发布（正文 + metric_json + report_metric + success）。

关键语义：
    - 同请求键同参数回放原记录（即使已跨日/配置后来更新）；同键不同参数 409；
      业务键相同复用同一记录，不偷偷重新调用模型（040）。
    - 已冻结输入后重试只复用该输入，不悄悄重新取数混入新数据（2310）。
    - 模型结果不明（请求已发出）标记 MODEL_OUTCOME_UNKNOWN 并停止自动重发；
      调度补偿扫描不把 failed/unknown 当缺失窗口重发（041）。
    - 报告“已受理”不表示已生成成功；查询接口按保存状态返回。
"""
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.clients.report import ReportDifyClient, ReportDifyError, ReportModelOutcomeUnknown
from app.core.response import BusinessException, ResultCode
from app.database import SessionLocal
from app.models.report import ReportConfig, ReportRecord, utcnow
from app.repositories.report import report_repository as repo
from app.schemas.report import (
    BUSINESS_TIMEZONE,
    REPORT_CODES,
    GenerateReportRequest,
    UpdateReportConfigRequest,
)
from app.services.report.report_anonymizer import (
    AnonymizationError,
    ContentReconciliationError,
    anonymize_for_model,
    public_metric_json,
    reconcile_content,
    sanitize_fail_reason,
    strip_reasoning,
)
from app.services.report.report_metrics import (
    METRIC_VERSION,
    QUERY_VERSION,
    MetricsResult,
    ReportDataUnavailable,
    compute_metrics,
)
from app.tasks.report.report_tasks import default_window, validate_cron_expr

# 报告生成版本与业务键版本（参与幂等键；升级生成逻辑时递增）。
REPORT_VERSION = "v1"
BUSINESS_KEY_VERSION = "report-key-v1"
TEMPLATE_VERSION = "report-template-v1"

# 业务时区：按北京时间解析自然周期后转 UTC 存储（038）。
BUSINESS_TZ = timezone(timedelta(hours=8))

# 显式窗口跨度上限（北京时间自然日）。
MAX_WINDOW_DAYS = 366

# 需要日报日期指标的报告：显式窗口两端须为北京时间 00:00（038）。
DATE_METRIC_CODES = ("daily_report", "weekly_report")

# 请求回执注册表（进程内）。
# 041 拟新增持久回执（report_task/回执表）尚未部署：部署前同进程内重试可
# 正确回放/冲突，跨进程重启后回退为业务键匹配（同参数仍得同一记录）。
_REQUEST_RECEIPTS: dict[tuple[int, str, str], dict] = {}

# 幂等请求头：8—128 位可见 ASCII，无首尾空白，重试复用（035）。
_HEADER_PATTERN = re.compile(r"^[\x21-\x7e]{8,128}$")


def validate_idempotency_key(header_key: str | None) -> str:
    """校验 Idempotency-Key 请求头；非法返回 400。"""
    if header_key is None or not _HEADER_PATTERN.match(header_key):
        raise BusinessException(
            "Idempotency-Key 请求头必传，且须为 8—128 位可见 ASCII（无首尾空白）",
            code=ResultCode.PARAM_ERROR,
        )
    return header_key


# ---------------------------------------------------------------------------
# 配置管理（仅平台管理员；其他四接口不调 AI）
# ---------------------------------------------------------------------------


def list_configs(db: Session) -> list[ReportConfig]:
    """返回全部报告配置，按 report_code 排序。"""
    return repo.list_configs(db)


def update_config(
    db: Session, report_code: str, payload: UpdateReportConfigRequest
) -> ReportConfig:
    """按代码更新配置；cron 非法 400，配置不存在 404，row_version 不匹配 409。"""
    if payload.cron_expr is not None:
        try:
            validate_cron_expr(payload.cron_expr)
        except ValueError as exc:
            raise BusinessException(
                f"cron_expr 不符合调度适配器语法：{exc}", code=ResultCode.PARAM_ERROR
            ) from exc

    config, error = repo.update_config(
        db,
        report_code,
        report_name=payload.report_name,
        cron_expr=payload.cron_expr,
        enabled=payload.enabled,
        expected_row_version=payload.row_version,
    )
    if error == "not_found":
        raise BusinessException(
            f"报告配置不存在：{report_code}", code=ResultCode.NOT_FOUND
        )
    if error == "conflict":
        raise BusinessException(
            "配置已被其他人修改，请重新查询后再试", code=ResultCode.CONFLICT
        )
    assert config is not None
    return config


# ---------------------------------------------------------------------------
# 时间窗解析（038）
# ---------------------------------------------------------------------------


def _to_naive_utc(dt: datetime) -> datetime:
    """把可能带时区的时间统一为「naive UTC」，与库里 DATETIME(3) 存储口径一致。"""
    if dt.tzinfo is None:
        raise BusinessException(
            "显式 start_time/end_time 必须带时区偏移", code=ResultCode.PARAM_ERROR
        )
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _is_day_aligned(dt_utc: datetime) -> bool:
    """是否恰好为北京时间 00:00（日报日期指标要求两端对齐）。"""
    bj = dt_utc.replace(tzinfo=timezone.utc).astimezone(BUSINESS_TZ)
    return (bj.hour, bj.minute, bj.second, bj.microsecond) == (0, 0, 0, 0)


def _resolve_window(
    report_code: str,
    report_period: str,
    payload: GenerateReportRequest,
    now_utc: datetime,
) -> tuple[datetime, datetime]:
    """解析并校验统计时间窗（038 口径）。"""
    if payload.timezone != BUSINESS_TIMEZONE:
        raise BusinessException(
            "本期 timezone 仅接受 Asia/Shanghai", code=ResultCode.PARAM_ERROR
        )

    if (payload.start_time is None) != (payload.end_time is None):
        raise BusinessException(
            "start_time 与 end_time 必须同时提供或同时省略",
            code=ResultCode.PARAM_ERROR,
        )

    if payload.start_time is not None and payload.end_time is not None:
        for dt in (payload.start_time, payload.end_time):
            if dt.microsecond % 1000 != 0:
                raise BusinessException(
                    "时间精度超过毫秒且多余位不全为 0，拒绝悄悄截断",
                    code=ResultCode.PARAM_ERROR,
                )
        start_utc = _to_naive_utc(payload.start_time)
        end_utc = _to_naive_utc(payload.end_time)
        if end_utc <= start_utc:
            raise BusinessException("结束时间必须晚于开始时间", code=ResultCode.PARAM_ERROR)
        if end_utc > now_utc:
            raise BusinessException("结束时间不能晚于受理时刻", code=ResultCode.PARAM_ERROR)
        start_date = start_utc.replace(tzinfo=timezone.utc).astimezone(BUSINESS_TZ).date()
        end_date = end_utc.replace(tzinfo=timezone.utc).astimezone(BUSINESS_TZ).date()
        if (end_date - start_date).days > MAX_WINDOW_DAYS:
            raise BusinessException(
                f"窗口跨度不能超过 {MAX_WINDOW_DAYS} 个北京时间自然日",
                code=ResultCode.PARAM_ERROR,
            )
        if report_code in DATE_METRIC_CODES and not (
            _is_day_aligned(start_utc) and _is_day_aligned(end_utc)
        ):
            raise BusinessException(
                "日报类报告的显式窗口两端须为北京时间 00:00（含时分秒的窗口不被允许）",
                code=ResultCode.PARAM_ERROR,
            )
        return start_utc, end_utc

    return default_window(report_period, now_utc)


# ---------------------------------------------------------------------------
# 业务键与请求回执（040）
# ---------------------------------------------------------------------------


def _business_key(
    *,
    report_code: str,
    scope_key: str,
    start_utc: datetime,
    end_utc: datetime,
    config: ReportConfig,
    generation_revision: int = 1,
) -> str:
    """稳定业务键：规范 JSON 的 SHA-256（040/2316）。

    账号纳入请求命名空间，不纳入业务键：多个管理员仅在获准相同范围时可复用
    同一业务报告。scope_key 缺失即依赖未就绪，不回退全公司。
    """
    canonical = json.dumps(
        {
            "key_version": BUSINESS_KEY_VERSION,
            "report_code": report_code,
            "scope_key": scope_key,
            "start_utc_ms": int(start_utc.replace(tzinfo=timezone.utc).timestamp() * 1000),
            "end_utc_ms": int(end_utc.replace(tzinfo=timezone.utc).timestamp() * 1000),
            "timezone": BUSINESS_TIMEZONE,
            "metric_version": METRIC_VERSION,
            "report_version": REPORT_VERSION,
            "config_id": config.report_config_id,
            "config_row_version": config.row_version,
            "template_version": TEMPLATE_VERSION,
            "privacy_policy_version": "privacy-v1",
            "generation_revision": generation_revision,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _receipt_key(user_id: int, header_key: str) -> tuple[int, str, str]:
    return (user_id, "report.generate", header_key)


# ---------------------------------------------------------------------------
# 生成受理（POST /report/generate）
# ---------------------------------------------------------------------------


def generate_report(
    db: Session,
    payload: GenerateReportRequest,
    idempotency_key: str,
    access,
    background_tasks: BackgroundTasks,
) -> dict:
    """收单：校验、算时间窗、幂等去重，新建 pending 记录并挂后台任务。

    人工生成固定为公司范围（当前请求 Schema 不新增部门选择字段）；部门报告
    由可信内部调度按第006项生成，解析不到合法部门时依赖未就绪，不降级。
    """
    if payload.report_code not in REPORT_CODES:
        raise BusinessException(
            f"非法的报告代码：{payload.report_code}", code=ResultCode.PARAM_ERROR
        )

    config = repo.get_config_by_code(db, payload.report_code)
    if config is None:
        raise BusinessException(
            f"报告配置不存在：{payload.report_code}", code=ResultCode.NOT_FOUND
        )

    now_utc = utcnow()
    start_utc, end_utc = _resolve_window(
        payload.report_code, config.report_period, payload, now_utc
    )

    scope_key = "company"
    business_key = _business_key(
        report_code=payload.report_code,
        scope_key=scope_key,
        start_utc=start_utc,
        end_utc=end_utc,
        config=config,
    )

    user_id = access.account.user_id
    receipt = _REQUEST_RECEIPTS.get(_receipt_key(user_id, idempotency_key))
    if receipt is not None:
        if receipt["business_key"] != business_key:
            raise BusinessException(
                "同一 Idempotency-Key 已用于不同参数的请求", code=ResultCode.CONFLICT
            )
        existing = repo.get_record(db, receipt["report_record_id"])
        if existing is not None:
            return _generate_out(existing, reused=True)

    existing = repo.find_record_by_key(db, business_key)
    if existing is not None:
        # 业务键相同即同口径：复用同一记录，不偷偷重新调用模型。
        _REQUEST_RECEIPTS[_receipt_key(user_id, idempotency_key)] = {
            "business_key": business_key,
            "report_record_id": existing.report_record_id,
        }
        return _generate_out(existing, reused=True)

    record = ReportRecord(
        report_config_id=config.report_config_id,
        report_code=payload.report_code,
        idempotency_key=business_key,
        start_time=start_utc,
        end_time=end_utc,
        timezone=BUSINESS_TIMEZONE,
        report_version=REPORT_VERSION,
        source_record_count=0,
        status="pending",
    )
    try:
        record = repo.insert_record(db, record)
    except Exception:
        # 唯一键竞争：回滚后按业务键复核，先获业务键者创建，其余关联已有记录。
        existing = repo.find_record_by_key(db, business_key)
        if existing is None:
            raise
        _REQUEST_RECEIPTS[_receipt_key(user_id, idempotency_key)] = {
            "business_key": business_key,
            "report_record_id": existing.report_record_id,
        }
        return _generate_out(existing, reused=True)

    _REQUEST_RECEIPTS[_receipt_key(user_id, idempotency_key)] = {
        "business_key": business_key,
        "report_record_id": record.report_record_id,
    }

    # 请求会话即将关闭，后台任务自己开新会话完成真正的生成工作。
    background_tasks.add_task(
        run_generation,
        record.report_record_id,
        user=f"report-admin:{user_id}",
    )
    return _generate_out(record, reused=False)


def _generate_out(record: ReportRecord, *, reused: bool) -> dict:
    return {
        "report_record_id": record.report_record_id,
        "idempotency_key": record.idempotency_key,
        "status": record.status,
        "reused": reused,
        "start_time": record.start_time,
        "end_time": record.end_time,
        "timezone": record.timezone,
    }


# ---------------------------------------------------------------------------
# 生成执行（后台任务与可信调度复用同一链路）
# ---------------------------------------------------------------------------


def _frozen_manifest(record: ReportRecord) -> dict | None:
    """读取已冻结输入的保留区；指标/查询版本不一致视为未冻结（跨版本不可比）。"""
    metric_json = record.metric_json
    if not isinstance(metric_json, dict):
        return None
    manifest = metric_json.get("_manifest")
    if not isinstance(manifest, dict):
        return None
    if manifest.get("metric_version") != METRIC_VERSION:
        return None
    if manifest.get("query_version") != QUERY_VERSION:
        return None
    return manifest


def _full_metric_json(metrics: MetricsResult, period_type: str | None) -> dict:
    """metric_json = 已发布指标 + 服务端保留区（_manifest/_calculation_inputs）。

    保留区仅存授权聚合基础量、配置/规则/指标版本和摘要，不存个人心理原文、
    个人ID列表、邮箱或手机号，也不把幂等请求映射放入模型输入。
    """
    calculation_inputs: dict[str, dict] = {}
    for code, entry in metrics.entries.items():
        inputs = {
            key: entry[key]
            for key in ("numerator", "denominator", "valid_count", "missing_count")
            if key in entry
        }
        if inputs:
            calculation_inputs[code] = inputs
    return {
        **metrics.entries,
        "_manifest": metrics.manifest,
        "_calculation_inputs": {
            "base_counts": calculation_inputs,
            "source_counts_by_table": metrics.manifest.get(
                "source_counts_by_table", {}
            ),
            "period_type": period_type,
        },
    }


def _metric_rows(metrics: MetricsResult, period_type: str | None) -> list[dict]:
    """指标明细行：数值存 metric_value；不可计算/不可用以 metric_text 存原因。"""
    rows: list[dict] = []
    for code, entry in metrics.entries.items():
        value = entry.get("value")
        is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
        rows.append(
            {
                "metric_code": code,
                "metric_name": code,
                "metric_value": Decimal(str(value)) if is_number else None,
                "metric_text": None if is_number else entry.get("reason"),
                "metric_unit": entry.get("unit"),
                "calc_rule": entry.get("calc_rule"),
                "period_type": period_type,
            }
        )
    return rows


def run_generation(
    report_record_id: int,
    *,
    user: str = "report-service",
    bind=None,
) -> None:
    """后台执行：领取 → 取数 → 冻结输入 → AI 写分析 → 对账 → 原子发布。

    bind 仅供测试注入独立数据源（如 SQLite）；生产使用全局引擎。
    """
    if bind is not None:
        from sqlalchemy.orm import sessionmaker

        db = sessionmaker(bind=bind, autoflush=False, expire_on_commit=False)()
    else:
        db = SessionLocal()
    try:
        record = repo.get_record(db, report_record_id)
        if record is None:
            return

        claimed = repo.claim_record(db, report_record_id)
        if claimed is None:
            # 已被其他执行者领取，或状态非 pending（含 success/failed 复用）。
            return
        record = claimed
        row_version = record.row_version

        try:
            config = repo.get_config_by_code(db, record.report_code)
            period_type = config.report_period if config is not None else None

            manifest = _frozen_manifest(record)
            if manifest is not None:
                # 已冻结：复用冻结输入，不悄悄重新取数混入新数据（2310）。
                metrics = MetricsResult(
                    entries={
                        code: entry
                        for code, entry in record.metric_json.items()
                        if not code.startswith("_")
                    },
                    source_record_count=record.source_record_count,
                    snapshot_at=record.data_snapshot_at,
                    manifest=manifest,
                )
                metric_json = record.metric_json
            else:
                metrics = compute_metrics(
                    record.report_code,
                    record.start_time,
                    record.end_time,
                    period_type,
                    bind=bind,
                )
                metric_json = _full_metric_json(metrics, period_type)
                row_version = repo.save_frozen_input(
                    db,
                    record,
                    metric_json=metric_json,
                    data_snapshot_at=metrics.snapshot_at,
                    source_record_count=metrics.source_record_count,
                )
                if row_version < 0:
                    return  # 版本栅栏不匹配：旧执行者放弃
                record.row_version = row_version

            model_input = anonymize_for_model(record.report_code, metrics.entries)
            content = strip_reasoning(
                ReportDifyClient().generate_report(
                    record.report_code, model_input, user=user
                )
            )
            reconcile_content(record.report_code, content, metrics.entries)

            published = repo.publish_record(
                db,
                record,
                expected_row_version=row_version,
                report_content=content,
                metric_json=metric_json,
                data_snapshot_at=metrics.snapshot_at,
                source_record_count=metrics.source_record_count,
                metric_entries=_metric_rows(metrics, period_type),
            )
            if not published:
                return  # 发布被新执行者或版本栅栏拒绝
        except ReportModelOutcomeUnknown as exc:
            # 请求已发出但结果不明：停止自动重发，按可信 workflow_run_id 核对。
            repo.mark_failed(
                db,
                record,
                expected_row_version=row_version,
                fail_reason=sanitize_fail_reason(str(exc)),
                model_outcome_unknown=True,
            )
        except (
            ReportDataUnavailable,
            AnonymizationError,
            ContentReconciliationError,
            ReportDifyError,
        ) as exc:
            # 主来源不可读、匿名保护未就绪、对账失败、模型明确失败等：
            # 记录 failed 与脱敏原因，不编造成功报告。
            repo.mark_failed(
                db,
                record,
                expected_row_version=row_version,
                fail_reason=sanitize_fail_reason(f"{type(exc).__name__}: {exc}"),
            )
        except Exception as exc:  # noqa: BLE001 - 后台任务兜底：失败落库供轮询
            repo.mark_failed(
                db,
                record,
                expected_row_version=row_version,
                fail_reason=sanitize_fail_reason(f"{type(exc).__name__}: {exc}"),
            )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 查询（列表 / 详情）
# ---------------------------------------------------------------------------


def get_report(db: Session, report_record_id: int, access) -> dict:
    """按主键查单份报告；不存在或超出对象范围一律 404（不泄露跨部门对象）。"""
    record = repo.get_record(db, report_record_id)
    if record is None or not repo.record_visible_in_scope(db, record, access.scope):
        raise BusinessException(
            f"报告记录不存在：{report_record_id}", code=ResultCode.NOT_FOUND
        )

    config = repo.get_config_by_code(db, record.report_code)
    report_name = config.report_name if config is not None else record.report_code

    content = record.report_content if record.status == "success" else None
    metric_json = None
    if record.status == "success" and isinstance(record.metric_json, dict):
        metric_json = public_metric_json(record.metric_json)
    fail_reason = record.fail_reason if record.status == "failed" else None

    return {
        "report_record_id": record.report_record_id,
        "report_code": record.report_code,
        "report_name": report_name,
        "idempotency_key": record.idempotency_key,
        "start_time": record.start_time,
        "end_time": record.end_time,
        "timezone": record.timezone,
        "data_snapshot_at": record.data_snapshot_at,
        "report_version": record.report_version,
        "source_record_count": record.source_record_count,
        "status": record.status,
        "report_content": content,
        "metric_json": metric_json,
        "fail_reason": fail_reason,
        "generated_at": record.generated_at,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def list_reports(
    db: Session,
    access,
    *,
    report_code: str | None,
    status: str | None,
    page: int,
    page_size: int,
) -> dict:
    """分页列出报告记录（只给授权元数据），可按类型/状态过滤。"""
    if report_code is not None and report_code not in REPORT_CODES:
        raise BusinessException(
            f"非法的报告代码：{report_code}", code=ResultCode.PARAM_ERROR
        )
    if status is not None:
        from app.schemas.report import REPORT_STATUSES

        if status not in REPORT_STATUSES:
            raise BusinessException(
                f"非法的报告状态：{status}", code=ResultCode.PARAM_ERROR
            )

    total, rows = repo.list_records(
        db,
        access.scope,
        report_code=report_code,
        status=status,
        page=page,
        page_size=page_size,
    )
    items = [
        {
            "report_record_id": record.report_record_id,
            "report_code": record.report_code,
            "report_name": report_name,
            "start_time": record.start_time,
            "end_time": record.end_time,
            "status": record.status,
            "generated_at": record.generated_at,
        }
        for record, report_name in rows
    ]
    return {"total": total, "page": page, "page_size": page_size, "items": items}
