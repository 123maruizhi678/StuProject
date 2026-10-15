"""智能报告 HTTP 接口。

接口挂载在 /api/v1/report 下（对齐接口方案 RPT-01~RPT-05）：
    POST /report/generate            手动生成（异步，先返回 pending + 报告ID）
    GET  /report/list                分页列表（可按 report_code/status 过滤）
    GET  /report/{report_record_id}  查单份报告（含正文与指标）
    GET  /report/configs             查询全部配置
    PUT  /report/configs/{report_code} 更新配置（乐观锁）
"""
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.core.response import success
from app.database import get_db
from app.schemas.report import (
    GenerateReportRequest,
    ReportConfigOut,
    ReportListOut,
    ReportRecordOut,
    UpdateReportConfigRequest,
)
from app.services import report_service

router = APIRouter(prefix="/report", tags=["智能报告"])


@router.get("/configs")
def list_configs(db: Annotated[Session, Depends(get_db)]):
    """查询全部报告配置。"""
    configs = report_service.list_configs(db)
    return success(
        [ReportConfigOut.model_validate(c).model_dump(mode="json") for c in configs]
    )


@router.put("/configs/{report_code}")
def update_config(
    report_code: str,
    payload: UpdateReportConfigRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """更新报告配置；row_version 不匹配时返回 409。"""
    config = report_service.update_config(db, report_code, payload)
    return success(ReportConfigOut.model_validate(config).model_dump(mode="json"))


@router.post("/generate")
def generate_report(
    payload: GenerateReportRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
):
    """手动生成报告：立即返回 pending + 报告ID，后台异步算。"""
    data = report_service.generate_report(db, payload, background_tasks)
    return success(data)


@router.get("/list")
def list_reports(
    db: Annotated[Session, Depends(get_db)],
    report_code: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """分页列出报告记录（不含正文），可按类型/状态过滤。"""
    data = report_service.list_reports(db, report_code, status, page, page_size)
    return success(ReportListOut.model_validate(data).model_dump(mode="json"))


# 动态路由放在静态路由之后，避免 "list" 被当作 report_record_id 解析。
@router.get("/{report_record_id}")
def get_report(report_record_id: int, db: Annotated[Session, Depends(get_db)]):
    """按主键查单份报告（含正文与指标）。"""
    data = report_service.get_report(db, report_record_id)
    return success(ReportRecordOut.model_validate(data).model_dump(mode="json"))
