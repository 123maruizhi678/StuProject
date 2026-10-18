"""认证 HTTP 接口：提供公开页面清单、账号登录和当前用户页面/模块访问清单。"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.common.auth import get_current_account
from app.core.common.authorization import public_access
from app.core.common.navigation import account_access, navigation_for
from app.core.common.response import success
from app.database import get_db
from app.models.common.user_account import UserAccount
from app.repositories.common.account_repository import AccountRepository
from app.schemas.common.auth import LoginRequest, UpdateProfileRequest, ChangePasswordRequest, UpdateContactRequest
from app.services.common import self_account
from app.services.common.auth_service import authenticate, create_access_token

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/public-access")
def get_public_access():
    """Return public page metadata for clients before login."""
    access = public_access()
    access["navigation"] = navigation_for(set(), None)
    return success(access)


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
            "username": account.username,
            "user_id": account.user_id,
            "identity_type": account.identity_type,
            "display_name": AccountRepository(db).display_name(account),
        }
    )


@router.get("/me/access")
def get_my_access(
    account: Annotated[UserAccount, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
):
    """Return the user's allowed pages and modules for frontend navigation."""
    access = account_access(db, account)
    access["display_name"] = AccountRepository(db).display_name(account)
    return success(access)


@router.patch("/me/profile")
def update_my_profile(
    payload: UpdateProfileRequest,
    account: Annotated[UserAccount, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
):
    name = AccountRepository(db).update_full_name(account, payload.full_name, payload.expected_full_name)
    return success({"user_id": account.user_id, "identity_type": account.identity_type, "display_name": name})


@router.post("/me/password")
def change_my_password(payload: ChangePasswordRequest,
    account: Annotated[UserAccount, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)]):
    return success(self_account.change_password(db, account, payload))


@router.get("/me/contact")
def get_my_contact(account: Annotated[UserAccount, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)]):
    return success(self_account.student_contact(db, account))


@router.patch("/me/contact")
def update_my_contact(payload: UpdateContactRequest,
    account: Annotated[UserAccount, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)]):
    return success(self_account.update_student_contact(db, account, payload))
