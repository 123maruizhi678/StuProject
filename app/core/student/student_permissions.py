"""学生协作动作权限，复用公共角色策略并叠加受控分派配置。"""
from app.config import settings
from app.core.common.authorization import permissions_for

def employee_permissions(db, employee_id):
    """员工动作权限按当前有效角色计算；数据范围仍由业务逐次校验。"""
    from sqlalchemy import select
    from app.models.common import employee
    row = db.execute(select(employee).where(employee.c.employee_id == employee_id)).mappings().first()
    if not row or row['status'] != 'active':
        return set()
    from app.models.common import org_department
    if db.scalar(select(org_department.c.status).where(org_department.c.department_id==row['department_id']))!='active':
        return set()
    permissions = permissions_for('employee', row['role_codes'] or [])
    if settings.STUDENT_LEAVE_ASSIGNMENT_SCOPES.get(employee_id):
        permissions.add('student.admin_service.assign')
    if employee_id in settings.STUDENT_WARNING_ASSIGNER_IDS:
        permissions.add('student.warning.assign')
    return permissions
