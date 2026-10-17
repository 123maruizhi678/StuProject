"""公共身份与共享业务表使用同一个 Base.metadata。"""
from app.models.common.org_department import org_department
from app.models.common.employee import employee
from app.models.common.customer_profile import customer_profile
from app.models.common.student_profile import student_profile
from app.models.common.user_account import UserAccount
from app.models.common.operation_log import operation_log
from app.models.common.student_staff_binding import student_staff_binding
from app.models.common.student_score import student_score
from app.models.common.student_admin_service import student_admin_service
from app.models.common.service_ticket import service_ticket
from app.models.common.service_ticket_record import service_ticket_record
from app.models.common.business_notification import business_notification

__all__ = [
    "UserAccount", "org_department", "employee", "customer_profile", "student_profile", "operation_log",
    "student_staff_binding", "student_score", "student_admin_service", "service_ticket",
    "service_ticket_record", "business_notification",
]
