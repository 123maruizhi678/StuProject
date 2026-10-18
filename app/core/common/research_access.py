"""研判只读授权：平台管理员或有效部门主管，复用现有员工及部门。"""
from fastapi import Depends
from app.core.common.auth import get_current_account
from app.core.common.authorization import permissions_for
from app.core.enterprise.enterprise_authorization import context_for
from app.database import get_db
from app.services.customer.errors import ForbiddenError

RESEARCH_READ = frozenset({"customer.source.read", "customer.result.read", "customer.rule.read"})


def research_department(db, account):
    if account.identity_type == "admin":
        return None
    if account.identity_type == "employee":
        context = context_for(db, account)
        if "manager" in context.roles:
            return context.department_id
    raise ForbiddenError("仅平台管理员和有效部门主管可查看客户研判")


def require_research_read(permission):
    if permission not in RESEARCH_READ:
        raise ValueError("未知研判只读权限")

    def dependency(account=Depends(get_current_account), db=Depends(get_db)):
        research_department(db, account)
        if account.identity_type == "admin" and permission not in permissions_for("admin"):
            raise ForbiddenError("没有客户研判查看权限")
        return account

    return dependency
