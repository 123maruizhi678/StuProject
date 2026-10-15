"""通用 Dify API 客户端：按业务场景调用 Workflow 或 Chat 应用。"""

from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.config import settings


@dataclass(frozen=True)
class DifyAppConfig:
    """单个 Dify 应用的连接参数和应用类型。"""

    api_key: str
    app_type: Literal["workflow", "chat"]
    output_key: str | None = None


class DifyConfigurationError(RuntimeError):
    """Dify 应用没有配置 API Key 或注册信息。"""


# 业务场景名映射到独立应用凭据和输出字段；模型选择留在 Dify 工作流内部。
_APP_CONFIGS: dict[str, DifyAppConfig] = {
    "nl2sql": DifyAppConfig(
        api_key=settings.DIFY_NL2SQL_API_KEY or settings.DIFY_API_KEY,
        app_type="workflow",
        output_key=settings.DIFY_NL2SQL_OUTPUT_KEY or settings.DIFY_SQL_OUTPUT_KEY,
    ),
    "customer_judgement": DifyAppConfig(
        api_key=settings.DIFY_CUSTOMER_API_KEY,
        app_type="workflow",
        output_key=settings.DIFY_CUSTOMER_OUTPUT_KEY,
    ),
    "report_summary": DifyAppConfig(
        api_key=settings.DIFY_REPORT_API_KEY,
        app_type="workflow",
        output_key=settings.DIFY_REPORT_OUTPUT_KEY,
    ),
    "chat_assistant": DifyAppConfig(
        api_key=settings.DIFY_CHAT_API_KEY,
        app_type="chat",
    ),
}


def get_dify_app_config(app_name: str) -> DifyAppConfig:
    """按场景取得应用配置；未注册或未配置密钥时给出明确错误。"""
    config = _APP_CONFIGS.get(app_name)
    if config is None:
        raise DifyConfigurationError(f"未知的 Dify 应用场景: {app_name}")
    if not config.api_key:
        raise DifyConfigurationError(f"未配置 Dify 应用密钥: {app_name}")
    return config


class DifyClient:
    """统一封装 Dify Workflow 与 Chat blocking API 调用。"""

    def __init__(self, api_base: str | None = None, timeout: float | None = None):
        self.api_base = (api_base or settings.DIFY_API_BASE).rstrip("/")
        self.timeout = timeout or settings.DIFY_API_TIMEOUT_SECONDS

    async def _post(self, app_name: str, endpoint: str, payload: dict[str, Any]) -> dict:
        config = get_dify_app_config(app_name)
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_base}/{endpoint.lstrip('/')}",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()
        if not isinstance(result, dict):
            raise ValueError(f"Dify 返回格式无效: {app_name}")
        return result

    async def run_workflow(
        self,
        app_name: str,
        inputs: dict[str, Any],
        user: str = "stuproject",
        output_key: str | None = None,
    ) -> Any:
        """运行 Workflow；指定输出字段时返回该值，否则返回完整 outputs。"""
        config = get_dify_app_config(app_name)
        if config.app_type != "workflow":
            raise DifyConfigurationError(f"{app_name} 不是 Workflow 应用")

        response = await self._post(
            app_name,
            "/workflows/run",
            {"inputs": inputs, "response_mode": "blocking", "user": user},
        )
        data = response.get("data") or {}
        outputs = data.get("outputs") or {}
        key = output_key or config.output_key
        if key:
            value = outputs.get(key)
            if value is None or value == "":
                raise ValueError(f"Dify 应用 {app_name} 输出缺少字段 '{key}'")
            return value.strip() if isinstance(value, str) else value
        return outputs

    async def chat(
        self,
        app_name: str,
        query: str,
        user: str = "stuproject",
        inputs: dict[str, Any] | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """调用 Chat 应用并返回 answer、conversation_id 和 message_id。"""
        config = get_dify_app_config(app_name)
        if config.app_type != "chat":
            raise DifyConfigurationError(f"{app_name} 不是 Chat 应用")

        payload: dict[str, Any] = {
            "inputs": inputs or {},
            "query": query,
            "response_mode": "blocking",
            "user": user,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        response = await self._post(app_name, "/chat-messages", payload)
        answer = response.get("answer")
        if not isinstance(answer, str):
            raise ValueError(f"Dify Chat 应用 {app_name} 未返回 answer")
        return {
            "answer": answer,
            "conversation_id": response.get("conversation_id"),
            "message_id": response.get("message_id"),
        }


_client = DifyClient()


async def run_workflow(
    app_name: str,
    inputs: dict[str, Any],
    user: str = "stuproject",
    output_key: str | None = None,
) -> Any:
    """通用 Workflow 函数入口，适合业务服务直接调用。"""
    return await _client.run_workflow(app_name, inputs, user, output_key)


async def run_chat(
    app_name: str,
    query: str,
    user: str = "stuproject",
    inputs: dict[str, Any] | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """通用 Chat 函数入口。"""
    return await _client.chat(app_name, query, user, inputs, conversation_id)


async def call_nl2sql(question: str, user: str = "stuproject") -> str:
    """兼容旧调用方：运行 NL2SQL Workflow 并返回 SQL 字符串。"""
    return await run_workflow("nl2sql", {"question": question}, user=user)