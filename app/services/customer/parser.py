"""多格式解析：文本 / PDF / Excel 的归一化与字段映射。

确定性解析优先：Excel/CSV 用 openpyxl / csv 逐行读取；PDF 文本层用 pypdf。
扫描件 OCR 本期不做，无文本层明确不支持，不输出空字段假成功。
"""

import csv
import io
import os
from typing import Any, List, Optional

from pypdf import PdfReader

from app.services.customer.errors import BadRequestError, NotFoundError

# 允许落入 customer_info 的受控字段白名单
_INFO_FIELDS = (
    "full_name", "gender", "age", "education_level", "major", "work_years",
    "industry", "position_title", "city", "income_level", "target_product_code",
    "contact_email", "phone",
)

# 文件扩展名 -> source_type
_EXT_SOURCE_TYPE = {
    ".pdf": "pdf",
    ".xlsx": "excel",
    ".csv": "excel",
    ".txt": "text",
    ".md": "text",
}

# 表头别名 -> 字段名（中英文）
_HEADER_ALIASES = {
    "姓名": "full_name", "名字": "full_name", "客户姓名": "full_name",
    "name": "full_name", "full_name": "full_name",
    "性别": "gender", "gender": "gender",
    "年龄": "age", "age": "age",
    "学历": "education_level", "教育背景": "education_level", "学历层次": "education_level",
    "education": "education_level", "education_level": "education_level",
    "专业": "major", "major": "major",
    "工作年限": "work_years", "工作年数": "work_years", "工龄": "work_years",
    "work_years": "work_years",
    "行业": "industry", "industry": "industry",
    "职位": "position_title", "岗位": "position_title",
    "position": "position_title", "position_title": "position_title",
    "城市": "city", "所在城市": "city", "city": "city",
    "收入": "income_level", "薪资": "income_level", "收入水平": "income_level",
    "income": "income_level", "income_level": "income_level",
    "意向产品": "target_product_code", "目标产品": "target_product_code", "产品": "target_product_code",
    "target_product_code": "target_product_code", "product": "target_product_code",
    "电话": "phone", "手机": "phone", "手机号": "phone", "联系方式": "phone",
    "phone": "phone",
    "邮箱": "contact_email", "邮件": "contact_email", "email": "contact_email",
    "contact_email": "contact_email",
}


def source_type_from_filename(file_name: Optional[str]) -> Optional[str]:
    if not file_name:
        return None
    ext = os.path.splitext(file_name)[1].lower()
    return _EXT_SOURCE_TYPE.get(ext)


def assert_allowed_file(file_name: Optional[str]) -> None:
    """校验文件扩展名白名单：pdf / xlsx / csv / txt / md。"""
    if not file_name:
        raise BadRequestError("缺少文件名")
    ext = os.path.splitext(file_name)[1].lower()
    if ext not in _EXT_SOURCE_TYPE:
        raise BadRequestError("文件格式不支持，仅允许 pdf / xlsx / csv / txt / md")


def read_pdf_text(path: str) -> str:
    try:
        reader = PdfReader(path)
        parts = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(parts).strip()
    except Exception:
        raise BadRequestError("PDF 解析失败或无文本层")
    if not text:
        raise BadRequestError("PDF 无文本层，请提供文本或补资料")
    return text


def read_plain_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def read_excel_records(path: str) -> List[dict]:
    """读取 xlsx / csv 为行记录列表（表头映射为字段名）。"""
    if path.lower().endswith(".csv"):
        with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)
    else:
        import openpyxl

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = [[cell for cell in row] for row in ws.iter_rows(values_only=True)]

    if not rows:
        return []

    header = [str(h).strip() if h is not None else "" for h in rows[0]]
    records: List[dict] = []
    for row in rows[1:]:
        if not any(row):
            continue
        record: dict = {}
        for idx, value in enumerate(row):
            if idx >= len(header):
                continue
            field = _HEADER_ALIASES.get(header[idx])
            if field is None:
                continue
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            record[field] = value
        if record:
            records.append(record)
    return records


def read_source_records(source) -> List[dict]:
    """把来源归一化为字段记录列表：文本/PDF 单条，Excel 逐行多条。"""
    if source.source_type == "text":
        return [{}]  # 文本类走抽取器，此处仅占位单条
    path = source.file_path
    if not path or not os.path.exists(path):
        raise NotFoundError("原文件不存在")
    if source.source_type == "pdf":
        return [{}]
    if source.source_type == "excel":
        return read_excel_records(path)
    return [{}]


def read_source_text(source) -> str:
    """取来源的纯文本（供抽取器使用）。"""
    if source.source_type == "text":
        return source.raw_content or ""
    path = source.file_path
    if not path or not os.path.exists(path):
        raise NotFoundError("原文件不存在")
    if source.source_type == "pdf":
        return read_pdf_text(path)
    if source.source_type == "excel":
        # Excel 走确定性列映射，文本形态仅作摘要；返回空由逐行处理
        return ""
    return read_plain_text(path)


def parse_fields(raw: Any) -> dict:
    """把 Dify/来源输出规整为字段字典。"""
    if raw is None:
        return {}
    if isinstance(raw, str):
        return {"raw": raw}
    if isinstance(raw, dict):
        return {k: v for k, v in raw.items() if k not in ("status", "error")}
    return {}


def map_to_info_fields(fields: dict) -> dict:
    """仅保留白名单字段作为 customer_info 列；其余不入库。"""
    return {k: fields[k] for k in _INFO_FIELDS if k in fields}
