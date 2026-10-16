"""智能报告业务逻辑层：配置读写 + 报告生成链路。

配置管理部分（list_configs / get_config / update_config）只做纯数据库读写；
报告生成部分（generate_report / run_generation / get_report / list_reports）
实现「收单 → 后台取数算指标 → AI 写分析 → 写库 → 前端轮询」的异步闭环。

取数（_fetch_metrics）直接读源表算固定指标；AI 写分析（_write_analysis）调用
Dify 报告生成工作流。两者都已替换为真实实现；心理周报等未落地数据源会在
取数时明确报错，由 run_generation 兜底把记录标记为 failed。
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import BackgroundTasks
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.clients.report_dify import ReportDifyClient
from app.core.response import BusinessException, ResultCode
from app.database import SessionLocal, engine
from app.models.report import ReportConfig, ReportMetric, ReportRecord, utcnow
from app.schemas.report import (
    REPORT_CODES,
    GenerateReportRequest,
    UpdateReportConfigRequest,
)

# 报告生成版本，参与幂等键；后续升级报告生成逻辑时递增。
REPORT_VERSION = "v1"


def list_configs(db: Session) -> list[ReportConfig]:
    """返回全部报告配置，按主键升序。"""
    return list(
        db.scalars(select(ReportConfig).order_by(ReportConfig.report_config_id))
    )


def get_config(db: Session, report_code: str) -> ReportConfig:
    """按报告代码查询配置；不存在时抛出 404 业务异常。"""
    config = db.scalar(
        select(ReportConfig).where(ReportConfig.report_code == report_code)
    )
    if config is None:
        raise BusinessException(
            f"报告配置不存在：{report_code}", code=ResultCode.NOT_FOUND
        )
    return config


def update_config(
    db: Session, report_code: str, payload: UpdateReportConfigRequest
) -> ReportConfig:
    """按代码更新配置；row_version 不一致时抛 409 乐观锁冲突。"""
    config = get_config(db, report_code)

    if config.row_version != payload.row_version:
        raise BusinessException(
            "配置已被其他人修改，请重新查询后再试", code=ResultCode.CONFLICT
        )

    config.report_name = payload.report_name
    config.cron_expr = payload.cron_expr
    config.enabled = payload.enabled
    config.row_version += 1

    db.commit()
    db.refresh(config)
    return config


def _to_naive_utc(dt: datetime) -> datetime:
    """把可能带时区的时间统一为「naive UTC」，与库里 DATETIME(3) 存储口径一致。"""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _resolve_window(
    report_period: str,
    start_time: datetime | None,
    end_time: datetime | None,
) -> tuple[datetime, datetime]:
    """解析统计时间窗。

    - 都传：直接使用（并校验 end > start）。
    - 都不传：按周期取最近完整周期 —— day=昨天、week=上周一~本周一、month=上个月。
    - 只传其一：参数错误。
    """
    if (start_time is None) != (end_time is None):
        raise BusinessException(
            "start_time 与 end_time 必须同时提供或同时省略", code=ResultCode.PARAM_ERROR
        )

    if start_time is not None and end_time is not None:
        if end_time <= start_time:
            raise BusinessException("结束时间必须晚于开始时间", code=ResultCode.PARAM_ERROR)
        return _to_naive_utc(start_time), _to_naive_utc(end_time)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today = datetime(now.year, now.month, now.day)

    if report_period == "day":
        # 昨天 00:00 ~ 今天 00:00
        return today - timedelta(days=1), today

    if report_period == "month":
        # 上个月 1 号 ~ 本月 1 号
        first_this_month = datetime(now.year, now.month, 1)
        first_last_month = (first_this_month - timedelta(days=1)).replace(day=1)
        return first_last_month, first_this_month

    # week（默认）：上周一 ~ 本周一
    this_monday = today - timedelta(days=today.weekday())
    return this_monday - timedelta(days=7), this_monday


def generate_report(
    db: Session, payload: GenerateReportRequest, background_tasks: BackgroundTasks
) -> dict:
    """收单：校验、算时间窗、幂等去重，新建 pending 记录并挂后台任务。"""
    if payload.report_code not in REPORT_CODES:
        raise BusinessException(
            f"非法的报告代码：{payload.report_code}", code=ResultCode.PARAM_ERROR
        )

    config = get_config(db, payload.report_code)
    start_time, end_time = _resolve_window(
        config.report_period, payload.start_time, payload.end_time
    )

    # 幂等键 = 报告代码 + 时间窗 + 版本（与接口方案一致）。
    idempotency_key = (
        f"{payload.report_code}:{start_time:%Y-%m-%d}/{end_time:%Y-%m-%d}:{REPORT_VERSION}"
    )

    existing = db.scalar(
        select(ReportRecord).where(ReportRecord.idempotency_key == idempotency_key)
    )
    if existing is not None:
        # 完全相同的重复请求直接返回已有记录；同键但统计口径不同则 409。
        if existing.timezone != payload.timezone:
            raise BusinessException(
                "相同时间窗已存在不同统计口径的报告，请勿重复提交",
                code=ResultCode.CONFLICT,
            )
        return {
            "report_record_id": existing.report_record_id,
            "idempotency_key": idempotency_key,
            "status": existing.status,
        }

    record = ReportRecord(
        report_config_id=config.report_config_id,
        report_code=payload.report_code,
        idempotency_key=idempotency_key,
        start_time=start_time,
        end_time=end_time,
        timezone=payload.timezone,
        report_version=REPORT_VERSION,
        source_record_count=0,
        status="pending",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # 请求会话即将关闭，后台任务自己开新会话完成真正的生成工作。
    background_tasks.add_task(run_generation, record.report_record_id)

    return {
        "report_record_id": record.report_record_id,
        "idempotency_key": idempotency_key,
        "status": "pending",
    }


def run_generation(report_record_id: int) -> None:
    """后台任务（同步）：取数 → 算指标 → AI 写分析 → 写库。"""
    db = SessionLocal()
    try:
        record = db.get(ReportRecord, report_record_id)
        if record is None:
            return

        record.status = "running"
        db.commit()

        metrics, source_count = _fetch_metrics(
            record.report_code, record.start_time, record.end_time
        )
        content = _write_analysis(record.report_code, metrics)

        config = db.get(ReportConfig, record.report_config_id)
        period_type = config.report_period if config is not None else None

        record.report_content = content
        record.metric_json = metrics
        record.source_record_count = source_count
        record.data_snapshot_at = utcnow()
        record.generated_at = utcnow()
        record.status = "success"
        record.fail_reason = None

        for key, value in metrics.items():
            is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
            db.add(
                ReportMetric(
                    report_record_id=record.report_record_id,
                    # TODO: 真实指标应有稳定英文代码；当前先用中文键占位。
                    metric_code=key,
                    metric_name=key,
                    metric_value=Decimal(str(value)) if is_number else None,
                    metric_text=None if is_number else str(value),
                    metric_unit=None,
                    calc_rule="固定聚合口径，直接查源表计算",
                    period_type=period_type,
                )
            )

        db.commit()
    except Exception as exc:  # noqa: BLE001 - 后台任务需兜底并把失败原因落库供前端轮询
        db.rollback()
        failed = db.get(ReportRecord, report_record_id)
        if failed is not None:
            failed.status = "failed"
            failed.fail_reason = str(exc)
            db.commit()
    finally:
        db.close()


def get_report(db: Session, report_record_id: int) -> dict:
    """按主键查单份报告（联表取 report_name），不存在返回 404。

    TODO: mental_weekly 对普通管理员需脱敏，只返回匿名聚合、不返回个人明细；
    桩阶段正文无个人明细，暂不处理。
    """
    row = db.execute(
        select(ReportRecord, ReportConfig.report_name)
        .join(ReportConfig, ReportConfig.report_config_id == ReportRecord.report_config_id)
        .where(ReportRecord.report_record_id == report_record_id)
    ).one_or_none()
    if row is None:
        raise BusinessException(
            f"报告记录不存在：{report_record_id}", code=ResultCode.NOT_FOUND
        )

    record, report_name = row
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
        "report_content": record.report_content,
        "metric_json": record.metric_json,
        "fail_reason": record.fail_reason,
        "generated_at": record.generated_at,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def list_reports(
    db: Session,
    report_code: str | None,
    status: str | None,
    page: int,
    page_size: int,
) -> dict:
    """分页列出报告记录（只给元数据，不含正文），可按类型/状态过滤。"""
    filters = []
    if report_code:
        filters.append(ReportRecord.report_code == report_code)
    if status:
        filters.append(ReportRecord.status == status)

    total = db.scalar(select(func.count()).select_from(ReportRecord).where(*filters)) or 0

    rows = db.execute(
        select(ReportRecord, ReportConfig.report_name)
        .join(ReportConfig, ReportConfig.report_config_id == ReportRecord.report_config_id)
        .where(*filters)
        .order_by(ReportRecord.report_record_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

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


def _fetch_metrics(
    report_code: str, start_time: datetime, end_time: datetime
) -> tuple[dict, int]:
    """真实取数：按报告类型查源表，算固定指标，返回 (指标字典, 来源记录数)。

    TODO: 组长提供「统一 NL2SQL 查询服务」后，可把这里的固定 SQL 换成 NL2SQL
    调用；当前直接读源表是为了固定指标稳定、可复现。
    """
    if report_code in ("daily_report", "weekly_report"):
        return _daily_report_metrics(start_time, end_time)
    if report_code == "complaint_weekly":
        return _complaint_metrics(start_time, end_time)
    if report_code == "customer_overview":
        return _customer_overview_metrics(start_time, end_time)
    if report_code == "mental_weekly":
        raise BusinessException(
            "心理周报源表（mental_health_profile/mental_warning）尚未接入",
            code=ResultCode.SERVER_ERROR,
        )
    raise BusinessException(f"未支持的取数类型：{report_code}", code=ResultCode.PARAM_ERROR)


def _daily_report_metrics(
    start_time: datetime, end_time: datetime
) -> tuple[dict, int]:
    """日报/周报：按 report_date 落在时间窗内聚合提交/作废/提交人数。"""
    start_date = start_time.date()
    end_date = end_time.date()
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT "
                "SUM(CASE WHEN status = 'submitted' THEN 1 ELSE 0 END) AS submitted, "
                "SUM(CASE WHEN status = 'void' THEN 1 ELSE 0 END) AS void_count, "
                "COUNT(DISTINCT CASE WHEN status = 'submitted' THEN employee_id END) "
                "  AS submitters, "
                "COUNT(*) AS total "
                "FROM employee_daily_report "
                "WHERE report_date >= :start_date AND report_date < :end_date"
            ),
            {"start_date": start_date, "end_date": end_date},
        ).mappings().one()
    metrics = {
        "提交数": int(row["submitted"] or 0),
        "作废数": int(row["void_count"] or 0),
        "提交人数": int(row["submitters"] or 0),
    }
    return metrics, int(row["total"] or 0)


def _complaint_metrics(
    start_time: datetime, end_time: datetime
) -> tuple[dict, int]:
    """投诉周报：按 created_at 窗口聚合工单总量与各状态计数。"""
    params = {"s": start_time, "e": end_time}
    with engine.connect() as conn:
        total = conn.execute(
            text(
                "SELECT COUNT(*) FROM service_ticket "
                "WHERE created_at >= :s AND created_at < :e"
            ),
            params,
        ).scalar()
        status_rows = conn.execute(
            text(
                "SELECT status, COUNT(*) AS n FROM service_ticket "
                "WHERE created_at >= :s AND created_at < :e GROUP BY status"
            ),
            params,
        ).mappings().all()
    metrics = {"投诉总量": int(total or 0)}
    for r in status_rows:
        metrics[f"状态_{r['status']}"] = int(r["n"])
    return metrics, int(total or 0)


def _customer_overview_metrics(
    start_time: datetime, end_time: datetime
) -> tuple[dict, int]:
    """客户经营分析：客户总数、各状态计数、窗口内新增与跟进数。

    注意：经营分析还依赖未落地的 customer_judgement 表（成交金额、流失原因），
    本次只做客户档案 / 跟进侧的固定指标。
    """
    params = {"s": start_time, "e": end_time}
    with engine.connect() as conn:
        total = conn.execute(
            text("SELECT COUNT(*) FROM customer_profile WHERE is_archived = 0")
        ).scalar()
        new_in_window = conn.execute(
            text(
                "SELECT COUNT(*) FROM customer_profile "
                "WHERE is_archived = 0 AND created_at >= :s AND created_at < :e"
            ),
            params,
        ).scalar()
        followups = conn.execute(
            text(
                "SELECT COUNT(*) FROM customer_followup "
                "WHERE followup_at >= :s AND followup_at < :e"
            ),
            params,
        ).scalar()
        status_rows = conn.execute(
            text(
                "SELECT status, COUNT(*) AS n FROM customer_profile "
                "WHERE is_archived = 0 GROUP BY status"
            )
        ).mappings().all()
    metrics = {
        "客户总数": int(total or 0),
        "窗口内新增客户": int(new_in_window or 0),
        "窗口内跟进数": int(followups or 0),
    }
    for r in status_rows:
        metrics[f"状态_{r['status']}"] = int(r["n"])
    return metrics, int(total or 0)


def _write_analysis(report_code: str, metrics: dict) -> str:
    """调用 Dify 报告生成工作流，基于已算好的指标写分析正文。

    严禁让 AI 自行编造数字：只把 metrics 传入，正文必须引用这些数字。
    """
    return ReportDifyClient().generate_report(report_code, metrics)
