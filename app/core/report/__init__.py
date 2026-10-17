"""智能报告模块技术约束包（复用公共认证，不建立第二套 JWT）。"""

from app.core.report.report_auth import (
    REPORT_ACTIONS,
    ReportAccess,
    ReportScope,
    require_report_action,
    resolve_report_access,
)

__all__ = [
    "REPORT_ACTIONS",
    "ReportAccess",
    "ReportScope",
    "require_report_action",
    "resolve_report_access",
]
