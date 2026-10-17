"""跨模块共享表及学业事实；所有定义复用唯一 Base.metadata。"""
from .user_account import UserAccount
from .org_department import org_department
from .employee import employee
from .customer_profile import customer_profile
from .student_profile import student_profile
from .student_score import student_score
from .student_staff_binding import student_staff_binding
from .student_admin_service import student_admin_service
from .business_notification import business_notification
from .operation_log import operation_log
from .service_ticket import service_ticket
from .service_ticket_record import service_ticket_record
from .student_local_education import (
    student_academic_event, student_academic_reminder, student_application_progress,
)

__all__ = ['UserAccount', 'org_department', 'employee', 'customer_profile', 'student_profile', 'student_score', 'student_staff_binding', 'student_admin_service', 'business_notification', 'operation_log', 'service_ticket', 'service_ticket_record']
__all__ += ['student_academic_event', 'student_academic_reminder', 'student_application_progress']
