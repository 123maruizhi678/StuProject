"""平台admin与员工admin均为最高管理员，使用相同账户管理权限。"""
from fastapi import Depends,HTTPException
from app.core.auth import get_current_account
from app.database import get_db
from app.core.common.system_admin import is_system_admin

def require_platform_admin(account=Depends(get_current_account),db=Depends(get_db)):
    if not is_system_admin(db,account):
        raise HTTPException(status_code=403,detail='仅平台管理员可管理注册账户')
    return account
