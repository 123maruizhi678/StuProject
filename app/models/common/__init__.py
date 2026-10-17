"""公共身份表使用同一个 Base.metadata。"""
from app.models.common.org_department import org_department
from app.models.common.employee import employee
from app.models.common.customer_profile import customer_profile
from app.models.common.student_profile import student_profile
from app.models.common.user_account import UserAccount
from app.models.common.operation_log import operation_log

__all__ = ["UserAccount", "org_department", "employee", "customer_profile", "student_profile", "operation_log"]
