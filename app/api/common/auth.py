"""公共三个接口；账号通过受控脚本开通。"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.core.common.auth import get_current_account
from app.core.common.authorization import access_for, public_access
from app.core.common.response import ResponseModel, success
from app.database import get_db
from app.models.common.user_account import UserAccount
from app.schemas.common.auth import AccessResponse, LoginRequest, PublicAccessResponse, TokenResponse
from app.services.common.auth_service import authenticate, create_access_token

router = APIRouter(prefix="/auth", tags=["公共认证"])


@router.get("/public-access", response_model=ResponseModel[PublicAccessResponse])
def get_public_access():
    return success(public_access())


@router.post("/login", response_model=ResponseModel[TokenResponse])
def login(payload: LoginRequest, response: Response, db: Annotated[Session, Depends(get_db)]):
    account = authenticate(db, payload.username, payload.password)
    if account is None:
        raise HTTPException(status_code=401, detail="Invalid username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    token, expires_in = create_access_token(account)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return success({"access_token": token, "token_type": "bearer", "expires_in": expires_in})


@router.get("/me/access", response_model=ResponseModel[AccessResponse])
def get_my_access(response: Response, account: Annotated[UserAccount, Depends(get_current_account)]):
    response.headers["Cache-Control"] = "no-store"
    return success(access_for(account.identity_type, account.user_id,
                              role_codes=account.access_context.role_codes))
