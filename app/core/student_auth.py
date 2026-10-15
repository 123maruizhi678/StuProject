"""学生模块签名身份与短期操作凭证；生产由统一登录服务签发同契约 JWT。"""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Literal
from fastapi import Header, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings
from app.core.response import BusinessException


@dataclass(frozen=True)
class Principal:
    actor_type: Literal["student", "employee", "service"]
    actor_id: int | None = None
    service_code: str | None = None
    scopes: tuple[str, ...] = ()

    @property
    def key(self):
        return f"{self.actor_type}:{self.service_code if self.actor_type == 'service' else self.actor_id}"

    def require_scope(self, scope):
        if self.actor_type != "service" or scope not in self.scopes:
            raise BusinessException("服务权限不足", 403)


def _encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode(value):
    return base64.b64decode(
        value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
    )


def sign_token(claims, audience="student-api", lifetime=3600):
    secret = settings.STUDENT_AUTH_SECRET
    if len(secret.encode()) < 32:
        raise BusinessException("学生身份签名密钥未配置（至少32字节）", 503)
    payload = {
        **claims,
        "iss": settings.STUDENT_TOKEN_ISSUER,
        "aud": audience,
        "iat": int(time.time()),
        "exp": int(time.time()) + lifetime,
    }
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _encode(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    )
    raw = f"{header}.{body}"
    return (
        raw
        + "."
        + _encode(hmac.new(secret.encode(), raw.encode(), hashlib.sha256).digest())
    )


def verify_token(token, audience="student-api"):
    secret = settings.STUDENT_AUTH_SECRET
    if len(secret.encode()) < 32:
        raise BusinessException("学生身份签名密钥未配置（至少32字节）", 503)
    try:
        if len(token) > 64000:
            raise ValueError()
        header, body, signature = token.split(".")
        if json.loads(_decode(header)) != {"alg": "HS256", "typ": "JWT"}:
            raise ValueError()
        expected = hmac.new(
            secret.encode(), f"{header}.{body}".encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _decode(signature)):
            raise ValueError()
        data = json.loads(_decode(body))
        now = time.time()
        if (
            not isinstance(data, dict)
            or data.get("iss") != settings.STUDENT_TOKEN_ISSUER
            or data.get("aud") != audience
            or type(data.get("exp")) is not int
            or data["exp"] <= now
            or data.get("iat", now + 1) > now + 30
        ):
            raise ValueError()
        return data
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise BusinessException("身份或操作凭证无效、已过期", 401) from None


_bearer = HTTPBearer(auto_error=False)


def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise BusinessException("请先登录", 401)
    claims = verify_token(credentials.credentials)
    actor = claims.get("actor_type")
    actor_id = claims.get("actor_id")
    service = claims.get("service_code")
    scopes = claims.get("scopes", [])
    if not isinstance(scopes, list) or not all(isinstance(s, str) for s in scopes):
        raise BusinessException("身份格式无效", 401)
    if (
        actor in ("student", "employee")
        and type(actor_id) is int
        and actor_id > 0
        and service is None
    ):
        return Principal(actor, actor_id, scopes=tuple(scopes))
    if (
        actor == "service"
        and isinstance(service, str)
        and 1 <= len(service) <= 64
        and actor_id is None
    ):
        return Principal(actor, service_code=service, scopes=tuple(scopes))
    raise BusinessException("身份格式无效", 401)


def request_key(
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128)
):
    if not idempotency_key.isascii() or not all(
        33 <= ord(c) <= 126 for c in idempotency_key
    ):
        raise BusinessException("Idempotency-Key 必须是8至128位可见ASCII字符", 400)
    return idempotency_key
