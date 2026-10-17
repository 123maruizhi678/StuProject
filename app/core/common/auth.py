"""人员 JWT 依赖：逐请求重读账号、角色与有效状态。"""
from typing import Annotated
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.common.user_account import UserAccount
from app.repositories.common.account_repository import find_by_id, resolve_context
from app.services.common.auth_service import decode_access_token

_bearer = HTTPBearer(auto_error=False, scheme_name="PublicJWT")


def get_current_account(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> UserAccount:
    unauthorized = HTTPException(status_code=401, detail="Invalid or missing access token",
                                 headers={"WWW-Authenticate": "Bearer"})
    if credentials is None:
        raise unauthorized
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise unauthorized
    account = find_by_id(db, user_id)
    if account is None:
        raise unauthorized
    context = resolve_context(db, account)
    if context is None:
        raise HTTPException(status_code=403, detail="Account or linked profile is unavailable")
    account.access_context = context
    return account
