"""Argon2 密码、HS256 JWT 与账号认证；JWT 不保存角色或权限快照。"""
import re
from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from app.config import settings
from app.core.common.response import BusinessException
from app.models.common.user_account import UserAccount
from app.repositories.common.account_repository import find_by_username, resolve_context

_password_hash = PasswordHash.recommended()
_JWT_ALGORITHM = "HS256"
_DUMMY_HASH = _password_hash.hash("dummy-password-not-an-account")
_SUBJECT = re.compile(r"[1-9][0-9]{0,18}\Z")
MAX_USER_ID = 2**63 - 1


def hash_password(password: str) -> str:
    if not isinstance(password, str) or not 1 <= len(password) <= 256:
        raise ValueError("密码长度须为 1—256 个字符")
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hash.verify(password, password_hash)
    except Exception:
        return False


def authenticate(db: Session, username: str, password: str) -> UserAccount | None:
    account = find_by_username(db, username)
    valid = verify_password(password, account.password_hash if account else _DUMMY_HASH)
    if account is None or not valid:
        return None
    context = resolve_context(db, account)
    if context is None:
        return None
    account.access_context = context
    return account


def _secret() -> str:
    value = settings.AUTH_SECRET_KEY
    if len(value.encode("utf-8")) < 32:
        raise BusinessException("登录服务密钥未配置", code=503)
    return value


def create_access_token(account: UserAccount) -> tuple[str, int]:
    user_id = account.user_id
    if type(user_id) is not int or not 0 < user_id <= MAX_USER_ID:
        raise ValueError("账号主键必须是有效正 BIGINT")
    expires_in = settings.AUTH_TOKEN_EXPIRE_MINUTES * 60
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(seconds=expires_in)},
        _secret(), algorithm=_JWT_ALGORITHM,
    )
    return token, expires_in


def decode_access_token(token: str) -> int | None:
    secret = _secret()
    if not isinstance(token, str) or len(token) > 8192:
        return None
    try:
        claims = jwt.decode(
            token, secret, algorithms=[_JWT_ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
        subject = claims["sub"]
        if not isinstance(subject, str) or not _SUBJECT.fullmatch(subject):
            return None
        if any(type(claims[k]) not in (int, float) for k in ("iat", "exp")):
            return None
        if claims["exp"] <= claims["iat"]:
            return None
        user_id = int(subject)
        return user_id if user_id <= MAX_USER_ID else None
    except (jwt.InvalidTokenError, TypeError, ValueError, OverflowError):
        return None
