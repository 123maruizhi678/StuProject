"""智能报告模块仓储：可信范围、请求/业务键、唯一任务及原子发布。

所有查询均参数化；可变写使用条件更新（行版本栅栏），旧执行者不得覆盖
新结果（041）。本层不理解业务规则，只提供数据访问原语。

范围说明（006/043 增量尚未部署）：
    report_record 现有 37 字段基线没有部门范围列，部门范围过滤在列部署后
    生效；部署前 `record_scope_predicate` 对部门范围返回「不匹配任何行」，
    即部门主管暂时看不到任何部门报告（部门报告由可信内部调度按第006项
    生成，不能声称部门生成已可用），平台管理员范围不受影响。
"""
import json
from datetime import datetime
from typing import Any

from sqlalchemy import delete, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.report import ReportConfig, ReportMetric, ReportRecord, utcnow

# 部门范围列（006 拟新增）：部署前不存在，部门过滤不生效。
_SCOPE_COLUMN = "scope_department_id"
_COLUMN_CACHE: dict[tuple[str, str], bool] = {}


def load_employee_scope(db: Session, employee_id: int | None) -> dict | None:
    """读取员工状态、受控角色与有效主部门；账号未绑定员工时返回 None。"""
    if employee_id is None:
        return None
    row = db.execute(
        text(
            "SELECT status, role_codes, department_id "
            "FROM employee WHERE employee_id = :employee_id"
        ),
        {"employee_id": employee_id},
    ).mappings().one_or_none()
    if row is None:
        return None
    role_codes = row["role_codes"]
    if isinstance(role_codes, str):
        try:
            role_codes = json.loads(role_codes)
        except ValueError:
            role_codes = []
    if not isinstance(role_codes, list):
        role_codes = []
    return {
        "status": row["status"],
        "role_codes": [str(code) for code in role_codes],
        "department_id": row["department_id"],
    }


def get_config_by_code(db: Session, report_code: str) -> ReportConfig | None:
    """按报告代码查询配置。"""
    return db.scalar(
        select(ReportConfig).where(ReportConfig.report_code == report_code)
    )


def list_configs(db: Session) -> list[ReportConfig]:
    """返回全部报告配置，按 report_code 排序（035 契约）。"""
    return list(
        db.scalars(select(ReportConfig).order_by(ReportConfig.report_code))
    )


def update_config(
    db: Session,
    report_code: str,
    *,
    report_name: str,
    cron_expr: str | None,
    enabled: bool,
    expected_row_version: int,
) -> tuple[ReportConfig | None, str | None]:
    """按代码更新配置。

    返回 (config, None) 成功；(None, "not_found") 配置不存在；
    (None, "conflict") row_version 不匹配（409）。成功时 row_version 加 1。
    """
    config = get_config_by_code(db, report_code)
    if config is None:
        return None, "not_found"
    if config.row_version != expected_row_version:
        return None, "conflict"

    result = db.execute(
        update(ReportConfig)
        .where(
            ReportConfig.report_config_id == config.report_config_id,
            ReportConfig.row_version == expected_row_version,
        )
        .values(
            report_name=report_name,
            cron_expr=cron_expr,
            enabled=enabled,
            row_version=expected_row_version + 1,
            updated_at=utcnow(),
        )
    )
    if result.rowcount != 1:
        return None, "conflict"
    db.commit()
    db.refresh(config)
    return config, None


def get_record(db: Session, report_record_id: int) -> ReportRecord | None:
    """按主键查询报告记录。"""
    return db.get(ReportRecord, report_record_id)


def find_record_by_key(db: Session, idempotency_key: str) -> ReportRecord | None:
    """按报告业务键查询已有记录（同键同口径复用）。"""
    return db.scalar(
        select(ReportRecord).where(
            ReportRecord.idempotency_key == idempotency_key
        )
    )


def insert_record(db: Session, record: ReportRecord) -> ReportRecord:
    """插入报告记录并提交；唯一键竞争由调用方回滚后按业务键复核。"""
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(record)
    return record


def _column_exists(db: Session, table: str, column: str) -> bool:
    """探测目标库表列是否存在（MySQL / SQLite 均适用）；结果按进程缓存。"""
    key = (table, column)
    cached = _COLUMN_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        columns = inspect(db.get_bind()).get_columns(table)
        exists = any(col["name"] == column for col in columns)
    except Exception:  # noqa: BLE001 - 探测失败按未部署处理，避免写库报错
        exists = False
    _COLUMN_CACHE[key] = exists
    return exists


def _department_scope_clause(db: Session, scope) -> tuple[str, dict]:
    """部门范围条件：列存在时等值过滤，否则不匹配任何行（006 未部署）。

    返回 (SQL 片段, 参数)；部门报告尚未可生成时主管看不到任何行，
    但不能因此把全公司报告放行给主管。
    """
    if _column_exists(db, "report_record", _SCOPE_COLUMN):
        return (
            "report_record.scope_department_id = :scope_department_id",
            {"scope_department_id": scope.department_id},
        )
    return "1 = 0", {}


def list_records(
    db: Session,
    scope,
    *,
    report_code: str | None,
    status: str | None,
    page: int,
    page_size: int,
) -> tuple[int, list[tuple[ReportRecord, str]]]:
    """按范围分页列出报告记录（只给元数据），稳定排序。

    排序：created_at DESC, report_record_id DESC；total 与 items 使用相同
    授权过滤，total 同样受范围约束。
    """
    conditions: list[str] = []
    params: dict[str, Any] = {}
    if report_code:
        conditions.append("report_record.report_code = :report_code")
        params["report_code"] = report_code
    if status:
        conditions.append("report_record.status = :status")
        params["status"] = status
    if scope.kind == "department":
        clause, scope_params = _department_scope_clause(db, scope)
        conditions.append(clause)
        params.update(scope_params)
    where_sql = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    total = db.execute(
        text("SELECT COUNT(*) FROM report_record" + where_sql), params
    ).scalar() or 0

    params.update({"limit": page_size, "offset": (page - 1) * page_size})
    rows = db.execute(
        text(
            "SELECT report_record.*, report_config.report_name AS report_name "
            "FROM report_record "
            "JOIN report_config ON report_config.report_config_id "
            "= report_record.report_config_id"
            + where_sql
            + " ORDER BY report_record.created_at DESC, "
            "report_record.report_record_id DESC "
            "LIMIT :limit OFFSET :offset"
        ),
        params,
    ).mappings().all()

    items = []
    for row in rows:
        record = ReportRecord(
            report_record_id=row["report_record_id"],
            report_config_id=row["report_config_id"],
            report_code=row["report_code"],
            idempotency_key=row["idempotency_key"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            timezone=row["timezone"],
            data_snapshot_at=row["data_snapshot_at"],
            report_version=row["report_version"],
            source_record_count=row["source_record_count"],
            report_content=row["report_content"],
            metric_json=row["metric_json"],
            status=row["status"],
            fail_reason=row["fail_reason"],
            generated_at=row["generated_at"],
            row_version=row["row_version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        items.append((record, row["report_name"]))
    return int(total), items


def record_visible_in_scope(db: Session, record: ReportRecord, scope) -> bool:
    """对象级范围校验：猜 ID 直接读跨部门报告必须被拒绝（与列表同过滤）。

    平台管理员范围全部可见；部门范围按 scope_department_id 相等判断，
    列未部署时部门报告尚不存在，一律不可见（404，不泄露对象是否存在）。
    """
    if scope.kind == "all":
        return True
    clause, params = _department_scope_clause(db, scope)
    row = db.execute(
        text(
            "SELECT 1 FROM report_record "
            f"WHERE report_record_id = :id AND {clause}"
        ),
        {**params, "id": record.report_record_id},
    ).first()
    return row is not None


def claim_record(db: Session, report_record_id: int) -> ReportRecord | None:
    """原子领取执行权：pending → running（行版本栅栏）。

    返回领取后的记录（携带新 row_version 作为后续写回的栅栏）；
    已被其他执行者领取或状态非 pending 时返回 None。
    """
    result = db.execute(
        update(ReportRecord)
        .where(
            ReportRecord.report_record_id == report_record_id,
            ReportRecord.status == "pending",
        )
        .values(status="running", updated_at=utcnow())
    )
    if result.rowcount != 1:
        db.rollback()
        return None
    db.commit()
    # 批量更新不刷新身份映射：过期后重取，确保调用方拿到新的行版本栅栏。
    db.expire_all()
    return get_record(db, report_record_id)


def save_frozen_input(
    db: Session,
    record: ReportRecord,
    *,
    metric_json: dict,
    data_snapshot_at: datetime | None,
    source_record_count: int,
) -> int:
    """保存受控冻结输入（独立写事务，状态仍为 running，不发布半成品）。

    返回新的 row_version；版本栅栏不匹配返回 -1（旧执行者放弃）。
    """
    expected = record.row_version
    result = db.execute(
        update(ReportRecord)
        .where(
            ReportRecord.report_record_id == record.report_record_id,
            ReportRecord.row_version == expected,
        )
        .values(
            metric_json=metric_json,
            data_snapshot_at=data_snapshot_at,
            source_record_count=source_record_count,
            row_version=expected + 1,
            updated_at=utcnow(),
        )
    )
    if result.rowcount != 1:
        db.rollback()
        return -1
    db.commit()
    return expected + 1


def publish_record(
    db: Session,
    record: ReportRecord,
    *,
    expected_row_version: int,
    report_content: str,
    metric_json: dict,
    data_snapshot_at: datetime | None,
    source_record_count: int,
    metric_entries: list[dict],
) -> bool:
    """原子发布：同一事务写正式 metric_json、全部明细、正文与成功状态。

    任何一步失败整体回滚，已冻结输入仍可用于诊断/恢复；旧执行者
    （行版本不匹配）不得覆盖新结果。
    """
    result = db.execute(
        update(ReportRecord)
        .where(
            ReportRecord.report_record_id == record.report_record_id,
            ReportRecord.row_version == expected_row_version,
            ReportRecord.status == "running",
        )
        .values(
            report_content=report_content,
            metric_json=metric_json,
            data_snapshot_at=data_snapshot_at,
            source_record_count=source_record_count,
            status="success",
            fail_reason=None,
            generated_at=utcnow(),
            row_version=expected_row_version + 1,
            updated_at=utcnow(),
        )
    )
    if result.rowcount != 1:
        db.rollback()
        return False

    db.execute(
        delete(ReportMetric).where(
            ReportMetric.report_record_id == record.report_record_id
        )
    )
    db.add_all(
        [
            ReportMetric(
                report_record_id=record.report_record_id,
                metric_code=entry["metric_code"],
                metric_name=entry["metric_name"],
                metric_value=entry.get("metric_value"),
                metric_text=entry.get("metric_text"),
                metric_unit=entry.get("metric_unit"),
                calc_rule=entry.get("calc_rule"),
                period_type=entry.get("period_type"),
            )
            for entry in metric_entries
        ]
    )
    db.commit()
    return True


def mark_failed(
    db: Session,
    record: ReportRecord,
    *,
    expected_row_version: int,
    fail_reason: str,
    model_outcome_unknown: bool = False,
) -> bool:
    """把运行中的记录标记为失败并写入脱敏原因。

    model_outcome_unknown=True 时在原因前标注 MODEL_OUTCOME_UNKNOWN，
    调度补偿扫描不得把该记录当作缺失窗口重发模型（041）。
    """
    reason = fail_reason
    if model_outcome_unknown:
        reason = f"MODEL_OUTCOME_UNKNOWN: {fail_reason}"
    result = db.execute(
        update(ReportRecord)
        .where(
            ReportRecord.report_record_id == record.report_record_id,
            ReportRecord.row_version == expected_row_version,
            ReportRecord.status == "running",
        )
        .values(
            status="failed",
            fail_reason=reason,
            row_version=expected_row_version + 1,
            updated_at=utcnow(),
        )
    )
    if result.rowcount != 1:
        db.rollback()
        return False
    db.commit()
    return True


def report_task_table_exists(db: Session) -> bool:
    """探测 041 拟新增 report_task 执行任务表是否已部署。"""
    return _column_exists(db, "report_task", "lease_owner")
