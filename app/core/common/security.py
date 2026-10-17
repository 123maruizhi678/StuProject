"""公共安全工具：密码哈希、电话加密与检索 token、脱敏过滤。

电话采用单点保护服务（AES-256-GCM 加密 + HMAC-SHA256 检索 token）。
"""

import base64
import hashlib
import hmac
import os
import re

import bcrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

_PHONE_WRAP_VERSION = "v1"
_DEFAULT_KEY_ID = "k1"


def hash_password(password: str) -> str:
    """账号密码以 bcrypt 哈希保存。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def normalize_phone(phone: str) -> str:
    """标准化本期大陆号码；格式错误返回空字符串。"""
    cleaned = re.sub(r"[\s\-()]", "", phone or "")
    if cleaned.startswith("+86"):
        cleaned = cleaned[3:]
    elif cleaned.startswith("0086"):
        cleaned = cleaned[4:]
    if re.fullmatch(r"[0-9]{11}", cleaned):
        return cleaned
    return ""


def _aes_key() -> bytes:
    key = settings.ENTERPRISE_PHONE_ENCRYPTION_KEY or ""
    return hashlib.sha256(key.encode("utf-8")).digest()


def encrypt_phone(normalized_phone: str) -> str:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_aes_key()).encrypt(nonce, normalized_phone.encode("utf-8"), None)
    return ":".join(
        [
            _PHONE_WRAP_VERSION,
            _DEFAULT_KEY_ID,
            base64.b64encode(nonce).decode("ascii"),
            base64.b64encode(ciphertext).decode("ascii"),
        ]
    )


def phone_lookup_token(normalized_phone: str) -> str:
    secret = settings.ENTERPRISE_PHONE_LOOKUP_SECRET or ""
    return hmac.new(
        secret.encode("utf-8"), normalized_phone.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def mask_email(email: str) -> str:
    if not email or "@" not in email:
        return ""
    local, domain = email.split("@", 1)
    masked = "*" if len(local) <= 1 else local[0] + "***"
    return f"{masked}@{domain}"


def mask_sensitive(text: str) -> str:
    if not text:
        return text
    text = re.sub(r"(?<!\d)(1[3-9]\d{9})(?!\d)", lambda m: m.group(1)[:3] + "****" + m.group(1)[-4:], text)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", lambda m: mask_email(m.group(0)), text)
    return text
