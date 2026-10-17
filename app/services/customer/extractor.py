"""客户信息抽取服务：确定性提取 + 可选 Dify 语义抽取。

确定性提取负责电话、邮箱等可正则化字段；Dify 抽取仅辅助非结构化文本的
语义字段（姓名、学历、专业、行业、城市、收入、意向产品等），不替代规则裁决。
"""

import re
from typing import Any

from app.clients.customer.extract_dify import ExtractDifyClient
from app.core.common.security import normalize_phone
from app.core.common.logger import get_logger

logger = get_logger("app.services.customer")

# 抽取契约版本与字段 schema（开发阶段随甲方字段字典固化）
_EXTRACT_CONTRACT_VERSION = "v1"
_FIELD_SCHEMA: dict = {
    "full_name": {"type": "string", "description": "客户姓名"},
    "gender": {"type": "string", "description": "性别（男/女）"},
    "age": {"type": "integer", "description": "年龄"},
    "education_level": {"type": "string", "description": "学历层次（如：本科/硕士/博士/大专）"},
    "major": {"type": "string", "description": "专业"},
    "work_years": {"type": "integer", "description": "工作年限"},
    "industry": {"type": "string", "description": "所在行业"},
    "position_title": {"type": "string", "description": "职位"},
    "city": {"type": "string", "description": "所在城市"},
    "income_level": {"type": "string", "description": "收入/薪资层级"},
    "target_product_code": {"type": "string", "description": "意向产品编码"},
    "contact_email": {"type": "string", "description": "联系邮箱"},
    "phone": {"type": "string", "description": "联系电话"},
}

_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_AGE_RE = re.compile(r"(?:年龄|age)[^\d]{0,3}(\d{1,3})", re.IGNORECASE)


def _deterministic_extract(text: str) -> dict:
    """确定性提取电话、邮箱、年龄等可正则字段。"""
    result: dict = {}
    m = _PHONE_RE.search(text or "")
    if m:
        result["phone"] = m.group(1)
    m = _EMAIL_RE.search(text or "")
    if m:
        result["contact_email"] = m.group(0)
    m = _AGE_RE.search(text or "")
    if m:
        try:
            result["age"] = int(m.group(1))
        except ValueError:
            pass
    return result


def _coerce(fields: dict) -> dict:
    """数值字段规整为 int；电话 / 邮箱做基础清理。"""
    out = dict(fields)
    for key in ("age", "work_years"):
        v = out.get(key)
        if v is None:
            continue
        if isinstance(v, bool):
            continue
        try:
            out[key] = int(str(v).strip())
        except (ValueError, TypeError):
            out.pop(key, None)
    if out.get("phone"):
        norm = normalize_phone(str(out.get("phone")))
        out["phone"] = norm or None
    if not out.get("phone"):
        out.pop("phone", None)
    return out


class ExtractorService:
    def __init__(self) -> None:
        self.client = ExtractDifyClient()

    def coerce(self, fields: dict) -> dict:
        """Excel 等确定性列映射结果规整（数值 / 电话 / 邮箱清理）。"""
        return _coerce(fields)

    def extract(self, text: str) -> dict:
        """提取字段：确定性 + 可选 Dify 语义抽取，确定性电话/邮箱优先。"""
        det = _deterministic_extract(text)
        llm = self.client.extract_fields(text, _FIELD_SCHEMA, _EXTRACT_CONTRACT_VERSION)
        merged: dict = dict(llm or {})
        # 确定性电话 / 邮箱可信度更高，覆盖 LLM 结果
        for key in ("phone", "contact_email"):
            if det.get(key):
                merged[key] = det[key]
        if "age" not in merged and det.get("age") is not None:
            merged["age"] = det["age"]
        return _coerce(merged)
