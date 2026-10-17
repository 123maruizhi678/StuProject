"""Dify 通用 HTTP 传输层：只负责 JSON POST、Bearer 鉴权、超时和 HTTP 响应。"""

from typing import Any

import httpx


class DifyHttpClient:
    """Dify JSON API 的同步/异步 HTTP 传输工具，不理解任何业务输入或输出。"""

    def __init__(
        self,
        api_base: str,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
        async_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self.transport = transport
        self.async_transport = async_transport

    def _url(self, path: str) -> str:
        return f"{self.api_base}/{path.lstrip('/')}"

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _json_object(response: httpx.Response) -> dict[str, Any]:
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Dify API 响应必须是 JSON 对象")
        return result

    def post_json_sync(
        self,
        path: str,
        *,
        api_key: str,
        payload: dict[str, Any],
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """同步 POST JSON 并返回响应对象；请求体及响应字段由调用方定义。"""
        with httpx.Client(
            timeout=httpx.Timeout(timeout or self.timeout, connect=5.0),
            transport=self.transport,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            response = client.post(
                self._url(path), json=payload, headers=self._headers(api_key)
            )
            response.raise_for_status()
            return self._json_object(response)

    async def post_json(
        self,
        path: str,
        *,
        api_key: str,
        payload: dict[str, Any],
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """异步 POST JSON 并返回响应对象；请求体及响应字段由调用方定义。"""
        async with httpx.AsyncClient(
            timeout=timeout or self.timeout,
            transport=self.async_transport,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            response = await client.post(
                self._url(path), json=payload, headers=self._headers(api_key)
            )
            response.raise_for_status()
            return self._json_object(response)
