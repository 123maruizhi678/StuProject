"""公共身份表使用同一个 Base.metadata。"""
from app.models.common.org_department import org_department
from app.models.common.employee import employee
from app.models.common.customer_profile import customer_profile
from app.models.common.student_profile import student_profile
from app.models.common.user_account import UserAccount
from app.models.common.operation_log import operation_log

__all__ = ["UserAccount", "org_department", "employee", "customer_profile", "student_profile", "operation_log"]

from .student_staff_binding import student_staff_binding
from .student_score import student_score
from .student_admin_service import student_admin_service
from .service_ticket import service_ticket
from .service_ticket_record import service_ticket_record
from .business_notification import business_notification
__all__ += ["student_staff_binding","student_score","student_admin_service","service_ticket","service_ticket_record","business_notification"]
from app.database import Base
metadata = shared_metadata = Base.metadata
