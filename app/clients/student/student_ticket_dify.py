"""旧导入路径兼容；实现已归入 legacy，不创建独立 Dify 应用。"""
from .legacy.student_ticket_dify import StudentTicketDifyError, get_ticket_workflow

__all__ = ["StudentTicketDifyError", "get_ticket_workflow"]
