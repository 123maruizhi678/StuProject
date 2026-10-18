"""Bearer Token 认证依赖：解析访问令牌、查询账号并为受保护接口提供当前登录账号。"""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.common.user_account import UserAccount
from app.services.common.auth_service import decode_access_token, token_matches_credential
from app.repositories.common.account_repository import AccountRepository

_bearer = HTTPBearer(auto_error=False)


def get_current_account(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> UserAccount:
    """验证 Bearer JWT，并从数据库读取当前账号和身份。"""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise unauthorized

    account = AccountRepository(db).get_by_id(user_id)
    if account is None or not token_matches_credential(credentials.credentials, account):
        raise unauthorized

    from app.core.common.account_state import ensure_account_active
    ensure_account_active(db, account)

    # Load lazily to avoid a module import cycle with permission dependencies.
    from app.core.common.authorization import load_access_control

    if account.identity_type not in load_access_control()["roles"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Identity has no access policy",
        )
    return account
