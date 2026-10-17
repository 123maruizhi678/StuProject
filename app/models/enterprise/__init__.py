"""唯一模型导出。"""
from .customer_followup import customer_followup
from .employee_daily_report import employee_daily_report
from .knowledge_entry import knowledge_entry
__all__ = ['customer_followup', 'employee_daily_report', 'knowledge_entry']
from .local_course import enterprise_course,enterprise_student_course
__all__ += ['enterprise_course','enterprise_student_course']
