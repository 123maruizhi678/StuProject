"""历史导入兼容：复用公共唯一Table，不再声明独立元数据。"""
from app.models.common import student_profile, employee, student_staff_binding, student_admin_service, business_notification, operation_log
from app.database import Base
metadata = Base.metadata
