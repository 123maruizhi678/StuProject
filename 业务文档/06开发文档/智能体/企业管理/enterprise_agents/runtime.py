"""Dify Workflow 调用；不依赖 app、不读取数据库、不执行模型返回的工具。"""

from dataclasses import dataclass, field
import hashlib
import json
import math
import os
import re
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from .contracts import Task


class AgentError(Exception):
    """可映射到项目统一错误信封；不包含密钥、输入原文或依赖异常原文。"""

    def __init__(self, message: str, code: str = "AGENT_OUTPUT_INVALID"):
        self.code = code
        super().__init__(message)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def object_json(value):
    if isinstance(value, str):
        value = value.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", value)
        if fenced:
            value = fenced.group(1)
        value = json.loads(value, object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


@dataclass(frozen=True)
class DifyConfig:
    api_base: str = "http://127.0.0.1/v1"
    api_key: str = field(default="", repr=False)
    task_keys: dict[str, str] = field(default_factory=dict, repr=False)
    timeout_seconds: float = 60.0
    max_response_bytes: int = 2 * 1024 * 1024
    max_payload_bytes: int = 256 * 1024

    def __post_init__(self):
        url = urlsplit(self.api_base)
        if url.scheme not in ("http", "https") or not url.netloc or url.username or url.password or url.query or url.fragment:
            raise ValueError("invalid Dify API base URL")
        if not math.isfinite(self.timeout_seconds) or not 1 <= self.timeout_seconds <= 120:
            raise ValueError("timeout must be between 1 and 120 seconds")
        if self.max_response_bytes < 1 or self.max_payload_bytes < 1:
            raise ValueError("payload limits must be positive")

    @classmethod
    def from_env(cls):
        tasks = ("chat", "command", "daily_prepare", "daily_summary", "knowledge", "nl2sql")
        return cls(
            api_base=os.getenv("ENTERPRISE_AGENT_DIFY_BASE", "http://127.0.0.1/v1"),
            api_key=os.getenv("ENTERPRISE_AGENT_DIFY_KEY", ""),
            task_keys={t: os.getenv("ENTERPRISE_AGENT_" + t.upper() + "_KEY", "") for t in tasks},
            timeout_seconds=float(os.getenv("ENTERPRISE_AGENT_TIMEOUT", "60")),
        )


@dataclass(frozen=True)
class WorkflowOutput:
    data: dict
    run_id: str | None = None


class Runtime(Protocol):
    async def run(self, task: Task, *, prompt: str, payload: dict, schema: dict, subject: str) -> WorkflowOutput: ...


class DifyWorkflowRuntime:
    def __init__(self, config: DifyConfig | None = None, client: httpx.AsyncClient | None = None):
        self.config = config or DifyConfig.from_env()
        self.client = client

    async def run(self, task: Task, *, prompt: str, payload: dict, schema: dict, subject: str) -> WorkflowOutput:
        key = self.config.task_keys.get(task) or self.config.api_key
        if not key:
            raise AgentError("尚未配置对应 Dify Workflow Key", "AGENT_NOT_CONFIGURED")
        try:
            body = {
                "inputs": {
                    "task": task,
                    "system_prompt": prompt,
                    "payload_json": json.dumps(payload, ensure_ascii=False, allow_nan=False),
                    "schema_json": json.dumps(schema, ensure_ascii=False),
                },
                "response_mode": "blocking",
                "user": "enterprise-" + hashlib.sha256(subject.encode("utf-8")).hexdigest(),
            }
            if len(json.dumps(body, ensure_ascii=False).encode("utf-8")) > self.config.max_payload_bytes:
                raise AgentError("输入上下文过大，请由后端缩小范围或分批", "AGENT_CONTEXT_TOO_LARGE")
            if self.client is not None:
                result = await self._post(self.client, body, key)
            else:
                async with httpx.AsyncClient(follow_redirects=False) as client:
                    result = await self._post(client, body, key)
            data = result.get("data")
            if not isinstance(data, dict) or data.get("status") != "succeeded":
                raise AgentError("Dify Workflow 未成功完成", "AGENT_WORKFLOW_FAILED")
            outputs = data.get("outputs")
            if not isinstance(outputs, dict) or "result" not in outputs:
                raise AgentError("Dify Workflow 缺少 result 输出")
            parsed = object_json(outputs["result"])
            run_id = result.get("workflow_run_id") or data.get("id")
            if run_id is not None and not isinstance(run_id, str):
                raise ValueError("invalid workflow run ID")
            return WorkflowOutput(parsed, run_id)
        except AgentError:
            raise
        except httpx.TimeoutException:
            raise AgentError("智能体调用超时，请稍后重试", "AGENT_TIMEOUT") from None
        except httpx.HTTPError:
            raise AgentError("智能体服务暂不可用", "AGENT_UNAVAILABLE") from None
        except (ValueError, TypeError, KeyError, RecursionError):
            raise AgentError("智能体返回格式不符合约定") from None

    async def _post(self, client, body, key):
        async with client.stream(
            "POST", self.config.api_base.rstrip("/") + "/workflows/run",
            headers={"Authorization": "Bearer " + key}, json=body,
            timeout=self.config.timeout_seconds, follow_redirects=False,
        ) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise AgentError("智能体服务返回非预期状态", "AGENT_UNAVAILABLE")
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > self.config.max_response_bytes:
                    raise AgentError("智能体返回数据过大", "AGENT_OUTPUT_TOO_LARGE")
                chunks.append(chunk)
            return object_json(b"".join(chunks).decode("utf-8"))
