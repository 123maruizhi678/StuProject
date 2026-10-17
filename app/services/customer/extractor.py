"""确定性联系方式/年龄抽取优先；Dify 仅补充受控客户事实字段。"""
import re
from pydantic import ValidationError
from app.clients.customer.extract_dify import ExtractDifyClient
from app.core.common.security import normalize_phone
from app.schemas.customer.extraction import CustomerExtractFields, EXTRACT_CONTRACT_VERSION, FIELD_SCHEMA, MAX_TEXT_BYTES

_PHONE_RE = re.compile(r"(?<!\d)(?:\+86[ -]?)?(1[3-9]\d[ -]?\d{4}[ -]?\d{4})(?!\d)")
_EMAIL_RE = re.compile(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_AGE_RE = re.compile(r"(?:年龄|age)\s*[:：]?\s*(\d{1,3})|(?<!\d)(\d{1,3})\s*岁", re.IGNORECASE)

def _deterministic_extract(text: str) -> dict:
    result = {}
    if m := _PHONE_RE.search(text):
        result["phone"] = normalize_phone(m.group(1))
    if m := _EMAIL_RE.search(text):
        result["contact_email"] = m.group(0)
    if m := _AGE_RE.search(text):
        age = int(m.group(1) or m.group(2))
        if age <= 120:
            result["age"] = age
    return result

def _coerce(fields: dict) -> dict:
    """Excel 列值按字段校验；坏值丢弃，禁止 bool 冒充整数。"""
    result = {}
    for key, value in fields.items():
        if key not in CustomerExtractFields.model_fields or value is None:
            continue
        if key in ("age", "work_years"):
            if isinstance(value, bool):
                continue
            if isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
                value = int(value.strip())
            elif isinstance(value, float) and value.is_integer():
                value = int(value)
        elif key == "phone":
            if isinstance(value, bool):
                continue
            value = normalize_phone(str(value))
        try:
            result.update(CustomerExtractFields.model_validate({key: value}).model_dump(exclude_none=True))
        except ValidationError:
            continue
    return result

class ExtractorService:
    def __init__(self, client: ExtractDifyClient | None = None) -> None:
        self.client = client or ExtractDifyClient()

    def coerce(self, fields: dict) -> dict:
        return _coerce(fields)

    def extract(self, text: str) -> dict:
        if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_TEXT_BYTES:
            raise ValueError("Customer extraction text exceeds 100 KiB")
        deterministic = _deterministic_extract(text)
        fields = self.client.extract_fields(text, FIELD_SCHEMA, EXTRACT_CONTRACT_VERSION)
        if len(set(re.findall(r"客户([一二三四五六七八九十0-9]+)\s*[:：]", text))) > 1:
            return {}  # 明确分段的多客户文本不能混合成单客户资料。
        merged = dict(fields or {})
        merged.update(deterministic)
        return _coerce(merged)
