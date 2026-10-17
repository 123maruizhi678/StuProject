"""旧导入路径兼容；实现已归入 legacy，不创建独立 Dify 应用。"""
from .legacy.student_leave_dify import StudentLeaveDifyError, get_leave_workflow

__all__ = ["StudentLeaveDifyError", "get_leave_workflow"]
