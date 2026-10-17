"""登录及每次JWT访问校验真实档案，归档／停用后旧Token也不继续授权。"""
from fastapi import HTTPException
from sqlalchemy import select
from app.models import common as t

def ensure_account_active(db,account):
    def reject():raise HTTPException(status_code=403,detail='账户关联档案或所属部门已失效')
    if account.identity_type=='admin':return
    if account.identity_type=='employee':
        row=db.execute(select(t.employee).where(t.employee.c.employee_id==account.employee_id)).mappings().first()
        if not row or row['status']!='active':reject()
    elif account.identity_type=='student':
        row=db.execute(select(t.student_profile).where(t.student_profile.c.student_id==account.student_id)).mappings().first()
        if not row or row['is_archived'] or row['status']!='active':reject()
    elif account.identity_type=='customer':
        row=db.execute(select(t.customer_profile).where(t.customer_profile.c.customer_id==account.customer_id)).mappings().first()
        if not row or row['is_archived']:reject()
    else:reject()
    if db.scalar(select(t.org_department.c.status).where(t.org_department.c.department_id==row['department_id']))!='active':reject()
