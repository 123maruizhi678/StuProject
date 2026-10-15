"""智能报告 HTTP 接口（最小闭环：报告配置管理）。

接口挂载在 /api/v1/report 下：
    GET  /report/configs                查询全部配置
    GET  /report/configs/{report_code}  查询单个配置
    PUT  /report/configs/{report_code}  更新配置（乐观锁）

报告生成等接口待接入 NL2SQL/Dify 后补充。
"""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import success
from app.database import get_db
from app.schemas.report import ReportConfigOut, UpdateReportConfigRequest
from app.services import report_service

router = APIRouter(prefix="/report", tags=["智能报告"])


@router.get("/configs")
def list_configs(db: Annotated[Session, Depends(get_db)]):
    """查询全部报告配置。"""
    configs = report_service.list_configs(db)
    return success(
        [ReportConfigOut.model_validate(c).model_dump(mode="json") for c in configs]
    )


@router.get("/configs/{report_code}")
def get_config(report_code: str, db: Annotated[Session, Depends(get_db)]):
    """按报告代码查询单个配置。"""
    config = report_service.get_config(db, report_code)
    return success(ReportConfigOut.model_validate(config).model_dump(mode="json"))


@router.put("/configs/{report_code}")
def update_config(
    report_code: str,
    payload: UpdateReportConfigRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """更新报告配置；row_version 不匹配时返回 409。"""
    config = report_service.update_config(db, report_code, payload)
    return success(ReportConfigOut.model_validate(config).model_dump(mode="json"))
