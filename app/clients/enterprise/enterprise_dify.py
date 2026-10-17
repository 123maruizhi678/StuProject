"""企业统一 Workflow：一个应用 Key，按 scene 分流；业务返回结构保持不变。"""
import json

from fastapi.encoders import jsonable_encoder

from app.config import settings
from app.core.common.dify import DifyHttpClient
from app.core.common.response import BusinessException
from app.core.enterprise.enterprise_authorization import error

RESULT_TYPES = {
    "extract": {"action": str, "target": dict, "fields": dict, "missing_fields": list, "needs_clarification": bool},
    "query": {"schema_version": str, "sql_template": str, "params": dict, "referenced_tables": list, "referenced_columns": list},
    "knowledge": {"answer": str, "citations": list, "mode": str},
    "summary": {"summary": str},
}


class EnterpriseDifyClient:
    def __init__(self, transport=None):
        self.transport = transport

    def run(self, scene, inputs, user_id):
        if not isinstance(scene, str) or scene not in RESULT_TYPES:
            error(400, "不支持的企业工作流场景")
        if not isinstance(inputs, dict):
            error(400, "企业工作流输入须为对象")
        version = settings.ENTERPRISE_DIFY_CONTRACT_VERSION
        if inputs.get("contract_version", version) != version:
            error(400, "企业工作流输入版本不匹配")
        key = settings.ENTERPRISE_DIFY_API_KEY
        if not key or "PLACEHOLDER" in key:
            error(503, "企业统一工作流尚未配置有效应用 Key")
        try:
            encoded = {"scene": scene, "payload": json.dumps(
                jsonable_encoder({**inputs, "contract_version": version}), ensure_ascii=False, allow_nan=False)}
            client = self.transport or DifyHttpClient(
                settings.ENTERPRISE_DIFY_API_BASE or settings.DIFY_API_BASE, settings.DIFY_API_TIMEOUT_SECONDS)
            response = client.post_json_sync("/workflows/run", api_key=key,
                payload={"inputs": encoded, "response_mode": "blocking", "user": f"enterprise:{user_id}"})
            data = response.get("data", {})
            if data.get("status") != "succeeded":
                error(503, "企业统一 Workflow 未成功完成")
            outputs = data.get("outputs", {})
            if outputs.get("scene") != scene:
                error(503, "工作流返回的业务场景不匹配")
            result = outputs.get("result")
            if isinstance(result, str):
                result = json.loads(result)
            if not isinstance(result, dict) or result.get("contract_version") != version:
                error(503, "工作流输出契约无效")
            if any(not isinstance(result.get(name), kind) for name, kind in RESULT_TYPES[scene].items()):
                error(503, "工作流输出字段类型无效")
            if scene == "query" and result["schema_version"] != "enterprise-query-v1":
                error(503, "查询 Schema 版本不匹配")
            if scene == "knowledge" and result["mode"] != inputs.get("mode"):
                error(503, "知识问答模式不匹配")
            return result
        except BusinessException:
            raise
        except Exception:
            error(503, "企业模型服务不可用或输出不合法")
