"""认证 HTTP 接口：提供公开页面清单、账号登录和当前用户页面/模块访问清单。"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_account
from app.core.authorization import access_for, public_access
from app.core.response import success
from app.database import get_db
from app.models.user_account import UserAccount
from app.schemas.auth import LoginRequest
from app.services.auth_service import authenticate, create_access_token

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/public-access")
def get_public_access():
    """Return public page metadata for clients before login."""
    return success(public_access())


@router.post("/login")
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """验证账号密码并签发访问令牌；失败时返回未授权错误。"""
    account = authenticate(db, payload.username, payload.password)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token, expires_in = create_access_token(account)
    return success(
        {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": expires_in,
        }
    )


@router.get("/me/access")
def get_my_access(
    account: Annotated[UserAccount, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
):
    """Return the user's allowed pages and modules for frontend navigation."""
    from app.core.common.system_admin import is_system_admin
    admin=is_system_admin(db,account)
    result=access_for('admin' if admin else account.identity_type,account.user_id)
    result.update(identity_type=account.identity_type,is_admin=admin)
    return success(result)
