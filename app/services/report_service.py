"""智能报告业务逻辑层：报告配置的查询与更新（最小闭环）。

后续接入报告生成时，再在本模块补充生成任务、轮询状态、指标落库等函数；
那些函数会复用 nl2sql_service 取数、Dify 生成正文，这里先只做配置读写。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.response import BusinessException, ResultCode
from app.models.report import ReportConfig
from app.schemas.report import UpdateReportConfigRequest


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