"""统一最高管理员识别；平台身份的操作档案不改变账号身份外键约束。"""
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select,insert
from sqlalchemy.exc import IntegrityError
from app.models import common as t

def is_system_admin(db,account,*,lock=False):
    if account.identity_type=='admin':return True
    if account.identity_type!='employee' or not account.employee_id:return False
    query=select(t.employee.c.role_codes).join(t.org_department,t.org_department.c.department_id==t.employee.c.department_id).where(t.employee.c.employee_id==account.employee_id,t.employee.c.status=='active',t.org_department.c.status=='active')
    if lock:query=query.with_for_update()
    roles=db.scalar(query)
    return isinstance(roles,list) and 'admin' in roles

def admin_actor(db,user_id):
    return db.execute(select(t.employee).where(t.employee.c.login_provider=='platform_admin',t.employee.c.login_subject==str(user_id))).mappings().first()

def ensure_admin_actor(db,account):
    """与管理员创建/首次写入同事务；使用独立档案，不冒用现有员工ID。"""
    row=admin_actor(db,account.user_id)
    if row:return row
    code='SYSTEM_ADMIN'
    department=db.scalar(select(t.org_department.c.department_id).where(t.org_department.c.department_code==code))
    if department is None:
        try:
            with db.begin_nested():
                department=db.execute(insert(t.org_department).values(department_code=code,department_name='平台管理',status='active',function_description='平台管理员业务操作档案所属组织')).inserted_primary_key[0]
        except IntegrityError:
            department=db.scalar(select(t.org_department.c.department_id).where(t.org_department.c.department_code==code))
    try:
        with db.begin_nested():
            db.execute(insert(t.employee).values(employee_no='ADMIN_'+str(account.user_id),full_name='平台管理员 '+account.username,department_id=department,position_title='企业管理员',role_codes=['employee','admin'],status='active',joined_date=datetime.now(ZoneInfo('Asia/Shanghai')).date(),login_provider='platform_admin',login_subject=str(account.user_id)))
    except IntegrityError:
        if not admin_actor(db,account.user_id):raise
    return admin_actor(db,account.user_id)
