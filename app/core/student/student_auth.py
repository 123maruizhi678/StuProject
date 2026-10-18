"""学生模块签名身份与短期操作凭证；生产由统一登录服务签发同契约 JWT。"""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Literal
from fastapi import Header, Depends
from app.database import get_db
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings
from app.core.common.response import BusinessException


@dataclass(frozen=True)
class Principal:
    actor_type: Literal["student", "employee", "service"]
    actor_id: int | None = None
    service_code: str | None = None
    scopes: tuple[str, ...] = ()
    user_id: int | None = None

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
    secret = settings.STUDENT_ACTION_SECRET
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


def verify_token(token, audience="student-api", *, allow_expired=False):
    secret = settings.STUDENT_ACTION_SECRET
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
            or (data["exp"] <= now and not allow_expired)
            or data.get("iat", now + 1) > now + 30
        ):
            raise ValueError()
        return data
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise BusinessException("身份或操作凭证无效、已过期", 401) from None



from fastapi import Request
from app.core.common.auth import get_current_account
from app.core.common.authorization import permissions_for

def get_principal(request: Request, account=Depends(get_current_account), db=Depends(get_db)) -> Principal:
    if account.identity_type not in ('student','employee'):
        raise BusinessException('此入口仅限学生或负责老师', 403)
    actor_id = account.student_id if account.identity_type == 'student' else account.employee_id
    if not actor_id:
        raise BusinessException('账号未关联有效业务档案', 403)
    permissions=permissions_for(account.identity_type)
    if account.identity_type == "employee":
        from app.core.student.student_permissions import employee_permissions
        permissions=employee_permissions(db, account.employee_id)
    required=ENDPOINT_PERMISSIONS.get(request.scope['endpoint'].__name__)
    if not required or required not in permissions:
        raise BusinessException('当前身份无权访问此学生业务',403)
    return Principal(account.identity_type, actor_id, scopes=tuple(permissions), user_id=account.user_id)

def request_key(value: str = Header(alias='Idempotency-Key', min_length=8, max_length=128, pattern=r'^[!-~]{8,128}$')):
    return value

def get_sync_principal(authorization: str = Header(default='')):
    if not settings.STUDENT_SYNC_ENABLED:
        raise BusinessException('外部同步当前未启用',503)
    scheme,_,supplied = authorization.partition(' ')
    if scheme.lower() != 'bearer':
        raise BusinessException('同步服务需要Bearer身份',401)
    expected = settings.STUDENT_SYNC_TOKEN.get_secret_value()
    if len(expected) < 32 or not hmac.compare_digest(supplied, expected):
        raise BusinessException('同步服务身份不可用', 401)
    return Principal('service', service_code='student_sync', scopes=('student:sync',))

ENDPOINT_PERMISSIONS={
    'withdraw_leave':'student.admin_service.withdraw_own','list_leave':'student.admin_service.read_own','get_leave':'student.admin_service.read_own',
    'reply_ticket':'student.ticket.reply_own','confirm_ticket':'student.ticket.confirm_own','rate_ticket':'student.ticket.rate_own',
    'mental_monitor':'student.mental.create_own','set_reminder':'student.reminder.manage_own','cancel_reminder':'student.reminder.manage_own',
    'read_notification':'student.notification.read_own','student_chat':'student.chat','confirm_action':'student.action.confirm',
    'get_academic':'student.academic.read_own','get_progress':'student.progress.read_own','get_reminders':'student.reminder.manage_own','get_notifications':'student.notification.read_own',
    'teacher_leave_list':'student.admin_service.review','teacher_leave_detail':'student.admin_service.review','teacher_leave_decision':'student.admin_service.review',
    'teacher_notifications':'student.notification.read','teacher_read_notification':'student.notification.read',
    'teacher_warning_list':'student.warning.read','warning_detail':'student.warning.read',
    'ack_warning':'student.warning.handle','follow_warning':'student.warning.handle','close_warning':'student.warning.handle',
}

ENDPOINT_PERMISSIONS.update({"submit_leave":"student.admin_service.create","submit_complaint":"service_ticket.create","tickets":"service_ticket.read_own","ticket_detail":"service_ticket.read_own","ticket_records":"service_ticket.read_own","get_courses":"student.course.read_own","get_scores":"student.score.read_own","notification_detail":"student.notification.read_own","leave_assignments":"student.admin_service.assign","assign_leave":"student.admin_service.assign","warning_assignments":"student.warning.assign","assign_warning":"student.warning.assign","maintain_academic":"student.academic.maintain","maintain_progress":"student.progress.maintain"})

ENDPOINT_PERMISSIONS.update({'chat_history':'student.chat','chat_history_detail':'student.chat','own_profile':'student.profile.read_own'})
