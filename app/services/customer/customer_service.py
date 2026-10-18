"""客户研判编排：来源登记、解析入库、研判、规则发布、受控查询与原件下载。

接口只做编排，不写 SQL 与 HTTP；SQL 在 repository，HTTP 在 client。
电话不落明文：解析入库仅存加密与检索 token；邮箱仅存受控掩码。
"""

import os
import re
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.common.user_account import UserAccount as AccountContext
from app.core.common.logger import get_logger
from app.services.customer.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.core.common.security import (
    encrypt_phone,
    mask_email,
    normalize_phone,
    phone_lookup_token,
)
from app.repositories.customer import customer_repository
from app.schemas.customer.customer import (
    JudgeBatchRequest,
    JudgeRequest,
    ParseRequest,
    ResultListQuery,
    RuleUpdate,
)
from app.services.customer import parser as parser_mod
from app.services.customer.extractor import ExtractorService
from app.services.customer.judge_service import JudgeService

logger = get_logger("app.services.customer")

# 命中后允许落库的字段白名单
_COLUMN_FIELDS = (
    "full_name", "gender", "age", "education_level", "major", "work_years",
    "industry", "position_title", "city", "income_level", "target_product_code",
)


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


# ---- 序列化（明文电话 / 密文不返回）----
def serialize_source(s) -> dict:
    return {
        "id": s.id,
        "source_type": s.source_type,
        "file_name": s.file_name,
        "status": s.status,
        "row_version": s.row_version,
        "created_by": s.created_by,
        "created_at": _iso(s.created_at),
    }


def serialize_info(info) -> dict:
    return {
        "id": info.id,
        "source_id": info.source_id,
        "source_row_key": info.source_row_key,
        "customer_id": info.customer_id,
        "full_name": info.full_name,
        "gender": info.gender,
        "age": info.age,
        "education_level": info.education_level,
        "major": info.major,
        "work_years": info.work_years,
        "industry": info.industry,
        "position_title": info.position_title,
        "city": info.city,
        "income_level": info.income_level,
        "target_product_code": info.target_product_code,
        "phone_lookup_token": info.phone_lookup_token,
        "contact_email": info.contact_email,
    }


def serialize_result(r) -> dict:
    return {
        "id": r.id,
        "source_id": r.source_id,
        "customer_info_id": r.customer_info_id,
        "product_id": r.product_id,
        "rule_version": r.rule_version,
        "input_snapshot": r.input_snapshot,
        "matched": r.matched,
        "matched_fields": r.matched_fields,
        "unmatched_reasons": r.unmatched_reasons,
        "score": float(r.score) if r.score is not None else None,
        "created_by": r.created_by,
        "created_at": _iso(r.created_at),
    }


def serialize_rule(r, product_code: Optional[str] = None) -> dict:
    return {
        "id": r.id,
        "product_id": r.product_id,
        "product_code": product_code,
        "rule_version": r.rule_version,
        "rule_content": r.rule_content,
        "rule_description": r.rule_description,
        "is_active": r.is_active,
        "active_slot": r.active_slot,
        "effective_from": _iso(r.effective_from),
        "effective_to": _iso(r.effective_to),
        "created_by": r.created_by,
        "created_at": _iso(r.created_at),
    }


class CustomerService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- 来源登记 ----
    def create_source(self, account: AccountContext, *, text: Optional[str] = None,
                      file_name: Optional[str] = None, file_bytes: Optional[bytes] = None):
        if text is not None:
            return self._create_text_source(account, text)
        if file_bytes is not None:
            return self._create_file_source(account, file_name, file_bytes)
        raise BadRequestError("需提供文本内容或上传文件")

    def _create_text_source(self, account: AccountContext, text: str):
        if not text or not text.strip():
            raise BadRequestError("文本内容不能为空")
        source = customer_repository.create_source(
            self.db,
            source_type="text",
            raw_content=text.strip(),
            status="pending",
            created_by=account.user_id,
        )
        self.db.commit()
        self.db.refresh(source)
        return source

    def _create_file_source(self, account: AccountContext, file_name: Optional[str],
                            file_bytes: bytes):
        parser_mod.assert_allowed_file(file_name)
        if not file_bytes:
            raise BadRequestError("文件内容为空")
        source_type = parser_mod.source_type_from_filename(file_name)
        upload_dir = os.path.abspath(settings.CUSTOMER_UPLOAD_DIR)
        os.makedirs(upload_dir, exist_ok=True)
        ext = os.path.splitext(file_name)[1].lower()
        file_path = os.path.join(upload_dir, f"{uuid.uuid4().hex}{ext}")
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        source = customer_repository.create_source(
            self.db,
            source_type=source_type,
            raw_content=None,
            file_name=file_name,
            file_path=file_path,
            status="pending",
            created_by=account.user_id,
        )
        self.db.commit()
        self.db.refresh(source)
        return source

    # ---- 解析 ----
    def parse_source(self, account: AccountContext, source_id: int,
                     req: ParseRequest):
        source = customer_repository.get_source(self.db, source_id)
        if source is None:
            raise NotFoundError("来源不存在")
        self._assert_owner_or_admin(account, source)
        if req.expected_version is not None and req.expected_version != source.row_version:
            raise ConflictError("来源版本已变化，请重新拉取后解析")
        if source.status == "parsed" and not req.force:
            infos = customer_repository.list_info_by_source(self.db, source.id)
            return source, infos

        parse_batch_id = int(datetime.now().timestamp() * 1000)
        try:
            records = self._extract_records(source)
        except Exception:
            source.status = "failed"
            self.db.commit()
            raise

        created = []
        for idx, fields in enumerate(records):
            created.append(self._create_info(source, fields, idx, parse_batch_id))

        source.status = "parsed"
        source.row_version += 1
        source.current_parse_batch_id = parse_batch_id
        self.db.commit()
        for info in created:
            self.db.refresh(info)
        self.db.refresh(source)
        return source, created

    def _extract_records(self, source) -> List[dict]:
        extractor = ExtractorService()
        if source.source_type == "excel":
            rows = parser_mod.read_excel_records(source.file_path)
            return [extractor.coerce(r) for r in rows]
        text = parser_mod.read_source_text(source)
        if not text or not text.strip():
            raise BadRequestError("无可解析内容")
        fields = extractor.extract(text)
        if not self._has_meaningful(fields):
            raise BadRequestError("未能提取到有效字段")
        return [fields]

    @staticmethod
    def _has_meaningful(fields: dict) -> bool:
        for k in _COLUMN_FIELDS:
            if fields.get(k) not in (None, ""):
                return True
        return bool(fields.get("phone")) or bool(fields.get("contact_email"))

    def _create_info(self, source, fields: dict, idx: int, parse_batch_id: int):
        phone = fields.get("phone")
        phone_ciphertext = None
        phone_token = None
        if phone:
            norm = normalize_phone(str(phone))
            if norm:
                phone_ciphertext = encrypt_phone(norm).encode("utf-8")
                phone_token = phone_lookup_token(norm)
        email = fields.get("contact_email")
        masked_email = mask_email(str(email)) if email else None
        raw = {k: v for k, v in fields.items() if k not in ("phone", "contact_email")}
        return customer_repository.create_info(
            self.db,
            source_id=source.id,
            parse_batch_id=parse_batch_id,
            source_row_key=f"{source.id}:{idx}",
            full_name=fields.get("full_name"),
            gender=fields.get("gender"),
            age=fields.get("age"),
            education_level=fields.get("education_level"),
            major=fields.get("major"),
            work_years=fields.get("work_years"),
            industry=fields.get("industry"),
            position_title=fields.get("position_title"),
            city=fields.get("city"),
            income_level=fields.get("income_level"),
            target_product_code=fields.get("target_product_code"),
            phone_ciphertext=phone_ciphertext,
            phone_lookup_token=phone_token,
            contact_email=masked_email,
            raw_fields=raw,
        )

    # ---- 研判 ----
    def judge(self, account: AccountContext, req: JudgeRequest):
        result = JudgeService(self.db).judge(
            req.customer_info_id, req.product_code, req.rule_version, operator_id=account.user_id
        )
        self.db.commit()
        self.db.refresh(result)
        return result

    def batch(self, account: AccountContext, req: JudgeBatchRequest):
        service = JudgeService(self.db)
        outcomes = []
        for info_id in req.customer_info_ids:
            savepoint = self.db.begin_nested()
            try:
                result = service.judge(info_id, req.product_code, operator_id=account.user_id)
                outcomes.append(serialize_result(result))
            except Exception as exc:  # 单条失败不影响整批
                savepoint.rollback()
                outcomes.append({
                    "customer_info_id": info_id,
                    "code": getattr(exc, "code", 500),
                    "message": getattr(exc, "message", str(exc)),
                })
        self.db.commit()
        return outcomes

    # ---- 结果查询 ----
    def list_sources(self, account, limit, offset):
        from app.core.common.research_access import research_department
        rows, total = customer_repository.list_sources(self.db, research_department(self.db, account), limit, offset)
        return {"items": [serialize_source(row) for row in rows], "total": total, "limit": limit, "offset": offset}

    def get_source_detail(self, account, source_id):
        from app.core.common.research_access import research_department
        department = research_department(self.db, account)
        source = customer_repository.get_source(self.db, source_id, department)
        if source is None:
            raise NotFoundError("资料来源不存在")
        return {"source": serialize_source(source), "fields": [serialize_info(row) for row in
            customer_repository.list_info_by_source(self.db, source_id, department)]}

    def get_result(self, account: AccountContext, result_id: int):
        from app.core.common.research_access import research_department
        result = customer_repository.get_result_by_id(self.db, result_id, research_department(self.db, account))
        if result is None:
            raise NotFoundError("研判结果不存在")
        return result

    def list_results(self, account: AccountContext, q: ResultListQuery):
        from app.core.common.research_access import research_department
        department = research_department(self.db, account)
        product_id = None
        if q.product_code:
            product = customer_repository.get_product_by_code(self.db, q.product_code)
            if product is None:
                raise NotFoundError("产品不存在")
            product_id = product.id
        total = customer_repository.count_results(self.db, product_id, q.matched, department_id=department)
        items = customer_repository.list_results(
            self.db, product_id, q.matched,
            offset=(q.page - 1) * q.page_size, limit=q.page_size,
            department_id=department,
        )
        return {"total": total, "page": q.page, "page_size": q.page_size, "items": items}

    # ---- 规则 ----
    def list_rules(self, account: AccountContext):
        return customer_repository.list_rules(self.db)

    def product_code_map(self) -> dict:
        return {p.id: p.product_code for p in customer_repository.list_products(self.db)}

    def update_rule(self, account: AccountContext, req: RuleUpdate):
        product = customer_repository.get_product_by_code(self.db, req.product_code)
        if product is None:
            raise NotFoundError("产品不存在")
        self._validate_rule_content(req.rule_content)
        customer_repository.deactivate_rules(self.db, product.id)
        rule = customer_repository.create_rule(
            self.db,
            product_id=product.id,
            rule_version=self._next_version(product.id),
            rule_content=req.rule_content,
            rule_description=req.rule_description,
            is_active=req.is_active,
            active_slot=1 if req.is_active else None,
            effective_from=self._parse_dt(req.effective_from),
            effective_to=self._parse_dt(req.effective_to),
            created_by=account.user_id,
        )
        self.db.commit()
        self.db.refresh(rule)
        return rule

    @staticmethod
    def _validate_rule_content(content) -> None:
        if not isinstance(content, dict):
            raise BadRequestError("rule_content 必须是对象")
        conditions = content.get("conditions")
        if conditions is None or not isinstance(conditions, list) or len(conditions) == 0:
            raise BadRequestError("rule_content.conditions 必须为非空数组")

    def _next_version(self, product_id: int) -> str:
        rules = customer_repository.list_rules(self.db, product_id)
        max_n = 0
        for r in rules:
            m = re.match(r"^v(\d+)$", r.rule_version or "")
            if m:
                max_n = max(max_n, int(m.group(1)))
        return f"v{max_n + 1}"

    @staticmethod
    def _parse_dt(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            raise BadRequestError("生效时间格式错误，应为 ISO8601")

    # ---- 原件下载 ----
    def get_source_file(self, account: AccountContext, source_id: int):
        source = customer_repository.get_source(self.db, source_id)
        if source is None:
            raise NotFoundError("来源不存在")
        self._assert_owner_or_admin(account, source)
        if not source.file_path or not os.path.exists(source.file_path):
            raise NotFoundError("无原件可下载")
        return source

    # ---- 数据归属 ----
    @staticmethod
    def _is_admin(account: AccountContext) -> bool:
        return account.identity_type == "admin"

    def _assert_owner_or_admin(self, account: AccountContext, source) -> None:
        if self._is_admin(account):
            return
        if source.created_by != account.user_id:
            raise ForbiddenError("无权访问该来源")
