"""幂等日志设施；敏感字段脱敏，按天滚动，不记录请求正文。"""
import logging
import re
from logging.handlers import TimedRotatingFileHandler
from app.config import LOG_DIR, settings

_initialized = False
_SENSITIVE = re.compile(r"password|secret|token|authorization|api.?key|ciphertext", re.I)
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/\-=]+", re.I)
_PAIR = re.compile(r"(?i)\b(password|password_hash|api_key|auth_secret_key|access_token)\b(\s*[=:]\s*)([^\s,;]+)")


def redact(value):
    if isinstance(value, dict):
        return {k: "***" if _SENSITIVE.search(str(k)) else redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(redact(v) for v in value)
    if isinstance(value, str):
        value = _BEARER.sub("Bearer ***", value)
        return _PAIR.sub(r"\1\2***", value)
    return value


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        original_msg, original_args = record.msg, record.args
        record.msg, record.args = redact(record.msg), redact(record.args)
        try:
            return redact(super().format(record))
        finally:
            record.msg, record.args = original_msg, original_args


def init_logger(to_console: bool = True, to_file: bool = True) -> None:
    global _initialized
    if _initialized:
        return
    logger = logging.getLogger("app")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False
    formatter = RedactingFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    if to_console:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    if to_file:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler = TimedRotatingFileHandler(LOG_DIR / "app.log", when="midnight", backupCount=15, encoding="utf-8")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    _initialized = True


def get_logger(name: str = "app") -> logging.Logger:
    init_logger()
    return logging.getLogger(name if name.startswith("app") else "app." + name)
