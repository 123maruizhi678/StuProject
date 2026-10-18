"""独立客户字段 Workflow 适配：状态、版本、严格 Schema 全部通过才接受。"""
import json
import httpx
from pydantic import ValidationError
from app.config import settings
from app.core.common.dify import DifyHttpClient
from app.core.common.logger import get_logger
from app.schemas.customer.extraction import CustomerExtractFields, EXTRACT_CONTRACT_VERSION, FIELD_SCHEMA, MAX_TEXT_BYTES

logger = get_logger("app.clients.customer")

class ExtractDifyClient:
    def __init__(self, client: DifyHttpClient | None = None) -> None:
        self.client = client or DifyHttpClient(api_base=settings.CUSTOMER_EXTRACT_DIFY_API_BASE or settings.DIFY_API_BASE, timeout=settings.CUSTOMER_EXTRACT_DIFY_TIMEOUT_SECONDS)

    def extract_fields(self, text: str, field_schema: dict = FIELD_SCHEMA, contract_version: str = EXTRACT_CONTRACT_VERSION) -> dict | None:
        if field_schema != FIELD_SCHEMA or contract_version != EXTRACT_CONTRACT_VERSION:
            raise ValueError("Unsupported customer extraction contract")
        if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_TEXT_BYTES:
            raise ValueError("Customer extraction text exceeds 100 KiB")
        if not text.strip():
            return {}
        key = settings.CUSTOMER_EXTRACT_DIFY_API_KEY.get_secret_value()
        if not key:
            return None
        payload = {
            "inputs": {"text": text, "field_schema": json.dumps(FIELD_SCHEMA, ensure_ascii=False), "contract_version": EXTRACT_CONTRACT_VERSION},
            "response_mode": "blocking", "user": "customer-extract",
        }
        try:
            result = self.client.post_json_sync("/workflows/run", api_key=key, payload=payload)
            data = result.get("data")
            if not isinstance(data, dict) or data.get("status") != "succeeded":
                logger.warning("客户抽取工作流未成功，使用确定性抽取")
                return None
            outputs = data.get("outputs")
            if not isinstance(outputs, dict) or outputs.get("contract_version") != EXTRACT_CONTRACT_VERSION:
                logger.warning("客户抽取契约版本无效，使用确定性抽取")
                return None
            fields = outputs.get("fields")
            if isinstance(fields, str):
                fields = json.loads(fields)
            return CustomerExtractFields.model_validate(fields).model_dump(exclude_none=True)
        except (httpx.HTTPError, ValueError, TypeError, ValidationError):
            logger.warning("客户抽取依赖失败或输出校验未通过，使用确定性抽取")
            return None
