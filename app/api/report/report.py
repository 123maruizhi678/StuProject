"""智能报告 HTTP 接口。

接口挂载在 /api/v1/report 下（对齐接口方案 RPT-01~RPT-05）：
    GET  /report/configs                读取报告配置（平台管理员）
    PUT  /report/configs/{report_code}  修改报告配置（平台管理员，乐观锁）
    POST /report/generate               手动生成（异步，先返回 pending + 报告ID）
    GET  /report/list                   分页列表（可按 report_code/status 过滤）
    GET  /report/{report_record_id}     查单份报告（含正文与指标）

路由注册顺序固定：/configs、/configs/{report_code}、/generate、/list 在前，
/{report_record_id} 在后，动态 ID 另做整数校验，避免 /list、/configs 被动态
详情捕获。

访问模型：复用公共 JWT 账号上下文，逐动作授权 + 数据范围校验
（app/core/report/report_auth.py，不建立第二套 JWT）：
    - 平台管理员：生成/配置/读取，全公司及所有部门范围；
    - 部门主管：仅读取，仅本人有效主部门范围；
    - 普通员工、客户、学生与匿名访客一律拒绝。
除生成链路外，查询与配置操作不直接调用 Dify。
"""
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request
from sqlalchemy.orm import Session

from app.core.report import ReportAccess, require_report_action
from app.core.common.response import BusinessException, ResultCode, success
from app.database import get_db
from app.schemas.report import (
    REPORT_CODES,
    REPORT_STATUSES,
    GenerateReportRequest,
    ReportConfigOut,
    ReportListOut,
    ReportRecordOut,
    UpdateReportConfigRequest,
)
from app.services.report import report_service

router = APIRouter(prefix="/report", tags=["智能报告"])

# 列表接口允许的查询参数；出现未知参数按 400 拒绝。
_ALLOWED_LIST_PARAMS = {"report_code", "status", "page", "page_size"}


@router.get("/configs")
def list_configs(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[ReportAccess, Depends(require_report_action("report.config.read"))],
):
    """查询全部报告配置（仅平台管理员），按 report_code 排序。"""
    configs = report_service.list_configs(db)
    return success(
        [ReportConfigOut.model_validate(c).model_dump(mode="json") for c in configs]
    )


@router.put("/configs/{report_code}")
def update_config(
    report_code: str,
    payload: UpdateReportConfigRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[ReportAccess, Depends(require_report_action("report.config.write"))],
):
    """更新报告配置（仅平台管理员）；row_version 不匹配返回 409。"""
    if report_code not in REPORT_CODES:
        raise BusinessException(
            f"非法的报告代码：{report_code}", code=ResultCode.PARAM_ERROR
        )
    config = report_service.update_config(db, report_code, payload)
    return success(ReportConfigOut.model_validate(config).model_dump(mode="json"))


@router.post("/generate")
def generate_report(
    payload: GenerateReportRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    access: Annotated[
        ReportAccess, Depends(require_report_action("report.generate"))
    ],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """手动生成报告（仅平台管理员）：立即返回 pending + 报告ID，后台异步算。"""
    header_key = report_service.validate_idempotency_key(idempotency_key)
    data = report_service.generate_report(
        db, payload, header_key, access, background_tasks
    )
    return success(data)


@router.get("/list")
def list_reports(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    access: Annotated[
        ReportAccess, Depends(require_report_action("report.read"))
    ],
    # 枚举查询参数：OpenAPI 暴露 enum，前端（live.js）据此渲染下拉框；
    # 非法取值走 schema 层校验，由统一异常处理器转为 200 + code=400 信封。
    report_code: Literal[tuple(REPORT_CODES)] | None = None,
    status: Literal[tuple(REPORT_STATUSES)] | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """分页列出报告记录（不含正文），可按类型/状态过滤；范围与 total 一致。"""
    unknown = set(request.query_params) - _ALLOWED_LIST_PARAMS
    if unknown:
        raise BusinessException(
            f"未知查询参数：{', '.join(sorted(unknown))}", code=ResultCode.PARAM_ERROR
        )
    data = report_service.list_reports(
        db,
        access,
        report_code=report_code,
        status=status,
        page=page,
        page_size=page_size,
    )
    return success(ReportListOut.model_validate(data).model_dump(mode="json"))


# 动态路由放在静态路由之后，避免 "list" 被当作 report_record_id 解析。
@router.get("/{report_record_id}")
def get_report(
    report_record_id: int,
    db: Annotated[Session, Depends(get_db)],
    access: Annotated[
        ReportAccess, Depends(require_report_action("report.read"))
    ],
):
    """按主键查单份报告（含正文与指标）；不存在或超出范围返回 404。"""
    if report_record_id <= 0 or report_record_id >= 2**63:
        raise BusinessException(
            "report_record_id 须为正整数且在 BIGINT 范围内",
            code=ResultCode.PARAM_ERROR,
        )
    data = report_service.get_report(db, report_record_id, access)
    return success(ReportRecordOut.model_validate(data).model_dump(mode="json"))
