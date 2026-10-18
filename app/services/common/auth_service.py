"""认证服务：验证 Argon2/bcrypt 密码哈希、查询账号、生成和解码 JWT 访问令牌。"""
from datetime import datetime, timedelta, timezone

import jwt
import bcrypt
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.config import settings
from app.models.common.user_account import UserAccount
from app.repositories.common.account_repository import AccountRepository

_password_hash = PasswordHash.recommended()
_JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a new account password; never store the plaintext password."""
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """验证用户输入的密码是否与数据库哈希匹配。"""
    try:
        if password_hash.startswith(("$2a$", "$2b$", "$2y$")):
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
        return _password_hash.verify(password, password_hash)
    except Exception:
        return False


def authenticate(db: Session, username: str, password: str) -> UserAccount | None:
    """按用户名查询账号并验证密码；无效时返回 None。"""
    account = AccountRepository(db).get_by_username(username)
    if account is None or not verify_password(password, account.password_hash):
        return None
    from app.core.common.account_state import ensure_account_active
    ensure_account_active(db, account)
    return account


def create_access_token(account: UserAccount) -> tuple[str, int]:
    """使用 AUTH_SECRET_KEY 签发 HS256 JWT 并计算有效时间。"""
    secret = settings.AUTH_SECRET_KEY
    if not secret or len(secret.encode("utf-8")) < 32:
        raise RuntimeError("AUTH_SECRET_KEY must be configured with at least 32 bytes")

    expires_in = settings.AUTH_TOKEN_EXPIRE_MINUTES * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(account.user_id),
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, secret, algorithm=_JWT_ALGORITHM)
    return token, expires_in


def decode_access_token(token: str) -> int | None:
    """验证 JWT 签名和有效期，返回令牌中的用户 ID。"""
    secret = settings.AUTH_SECRET_KEY
    if not secret:
        return None

    try:
        payload = jwt.decode(token, secret, algorithms=[_JWT_ALGORITHM])
        subject = payload.get("sub")
        return int(subject) if subject is not None else None
    except (jwt.InvalidTokenError, TypeError, ValueError):
        return None
