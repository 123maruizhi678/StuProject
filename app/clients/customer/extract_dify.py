"""可选字段抽取（独立应用，仅辅助，不替代规则裁决）。"""

import json
from typing import Any, Optional

from app.config import settings
from app.core.common.dify import DifyHttpClient, check_workflow_succeeded
from app.core.common.logger import get_logger

logger = get_logger("app.clients.customer")


class ExtractDifyClient:
    """客户研判字段抽取适配：调用独立 Workflow，输出规整字段字典。"""

    def __init__(self) -> None:
        self.client = DifyHttpClient()

    def extract_fields(self, text: str, field_schema: dict, contract_version: str) -> Optional[Any]:
        """调用独立抽取应用；Key 缺失返回 None（确定性路径可继续）。"""
        if not settings.CUSTOMER_EXTRACT_DIFY_API_KEY:
            return None
        payload = {
            "inputs": {
                "text": text,
                "field_schema": json.dumps(field_schema, ensure_ascii=False),
                "contract_version": contract_version,
            },
            "response_mode": "blocking",
            "user": "customer-extract",
        }
        try:
            result = self.client.post_json_sync(
                "/workflows/run",
                api_key=settings.CUSTOMER_EXTRACT_DIFY_API_KEY,
                payload=payload,
            )
        except Exception as exc:  # 网络/HTTP 错误不影响确定性路径
            logger.warning("客户抽取 Dify 调用失败: %s", exc)
            return None
        if not check_workflow_succeeded(result):
            logger.warning("客户抽取 Workflow 未成功: %s", result)
            return None
        outputs = (result.get("data") or {}).get("outputs") or {}
        # 结束节点输出为 fields（对象）；兼容字符串 JSON 形态
        fields = outputs.get("fields")
        if isinstance(fields, str):
            try:
                fields = json.loads(fields)
            except json.JSONDecodeError:
                fields = None
        return fields
