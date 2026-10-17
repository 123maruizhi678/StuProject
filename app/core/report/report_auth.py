"""智能报告授权：报告动作、管理员/主管范围校验。

契约来源（操作文档第二章「智能报告授权方案」）：
    - 平台管理员 identity_type=admin：report.generate / report.read /
      report.config.read / report.config.write，数据范围为全公司及所有部门；
      报告内心理数据仍为匿名聚合，不授心理原文。
    - 部门主管：有效员工且 employee.role_codes 含 manager，仅 report.read，
      仅本人有效主部门；不生成、不读/改配置，不自动包含子部门或全公司报告。
    - 普通员工及其他员工角色（consultant/teacher/academic/analyst/reviewer、
      员工 admin）不授报告权限；兼任有效 manager 时只按 manager 计算。
    - 客户、学生、匿名访客不授报告权限。
    - 精确权限不依赖未验证的 report.* 通配；report.mental_detail.read 默认不授。

实现约束：
    - 复用公共 JWT 账号上下文（app.core.auth.get_current_account），不建立
      第二套 JWT；角色、有效部门及数据范围由服务端读取，不信任前端或模型
      传入的角色/部门。
    - 平台管理员分支与 employee+manager 分支均需可到达；不得先强制
      identity_type=admin 将主管拒绝，也不得只检查 employee 放行其他员工。
    - 部门过滤发生在取数、聚合和模型输入前，并延续到详情与列表；仅过滤列表
      不能防止直接猜 ID 读取跨部门报告，因此详情同样逐对象校验范围。
"""
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_account
from app.core.common.response import BusinessException, ResultCode
from app.database import get_db
from app.models.user_account import UserAccount
from app.repositories.report.report_repository import load_employee_scope

# 报告精确动作权限（不依赖 report.* 通配）。
REPORT_GENERATE = "report.generate"
REPORT_READ = "report.read"
REPORT_CONFIG_READ = "report.config.read"
REPORT_CONFIG_WRITE = "report.config.write"
REPORT_MENTAL_DETAIL_READ = "report.mental_detail.read"  # 默认不授，不创建明细接口

REPORT_ACTIONS = (
    REPORT_GENERATE,
    REPORT_READ,
    REPORT_CONFIG_READ,
    REPORT_CONFIG_WRITE,
)

# 有效主管角色代码（受控角色，由后端固定配置解释）。
MANAGER_ROLE_CODE = "manager"

# 员工有效状态。
EMPLOYEE_ACTIVE_STATUS = "active"


@dataclass(frozen=True)
class ReportScope:
    """报告数据范围。

    kind=all        平台管理员：全公司汇总及所有部门报告；
    kind=department 部门主管：仅本人有效主部门报告。
    """

    kind: Literal["all", "department"]
    department_id: int | None = None

    @classmethod
    def all_company(cls) -> "ReportScope":
        return cls(kind="all")

    @classmethod
    def department(cls, department_id: int) -> "ReportScope":
        return cls(kind="department", department_id=department_id)


@dataclass(frozen=True)
class ReportAccess:
    """当前账号在报告模块的动作集合与数据范围。"""

    account: UserAccount
    actions: frozenset[str]
    scope: ReportScope

    def can(self, action: str) -> bool:
        return action in self.actions


def resolve_report_access(db: Session, account: UserAccount) -> ReportAccess:
    """按公共 JWT 账号上下文解析报告动作与数据范围；无任何报告权限抛 403。"""
    if account.identity_type == "admin":
        # 平台管理员分支：全部报告动作 + 全公司范围。
        return ReportAccess(
            account=account,
            actions=frozenset(REPORT_ACTIONS),
            scope=ReportScope.all_company(),
        )

    if account.identity_type == "employee":
        # employee + manager 分支：仅 report.read + 本部门范围。
        # 角色、状态与有效部门由服务端从员工表读取，不信任前端传入。
        employee = load_employee_scope(db, account.employee_id)
        if (
            employee is not None
            and employee["status"] == EMPLOYEE_ACTIVE_STATUS
            and MANAGER_ROLE_CODE in employee["role_codes"]
        ):
            department_id = employee["department_id"]
            if department_id is not None:
                return ReportAccess(
                    account=account,
                    actions=frozenset({REPORT_READ}),
                    scope=ReportScope.department(department_id),
                )

    # 普通员工、客户、学生、匿名访客及其余身份不授报告权限。
    raise BusinessException("无报告访问权限", code=ResultCode.FORBIDDEN)


def require_report_action(action: str) -> Annotated:
    """FastAPI 依赖：校验当前账号的报告动作权限并返回 ReportAccess。

    动作与允许人群（操作文档第一章五接口表）：
        report.generate      仅平台管理员（部门主管禁止手动生成）
        report.read          平台管理员、部门主管（主管限本部门）
        report.config.read   仅平台管理员
        report.config.write  仅平台管理员
    """
    if action not in REPORT_ACTIONS:
        raise ValueError(f"未知报告动作：{action}")

    def dependency(
        account: Annotated[UserAccount, Depends(get_current_account)],
        db: Annotated[Session, Depends(get_db)],
    ) -> ReportAccess:
        access = resolve_report_access(db, account)
        if not access.can(action):
            raise BusinessException(
                "报告动作权限不足", code=ResultCode.FORBIDDEN
            )
        return access

    return dependency
