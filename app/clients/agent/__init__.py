"""客服 Agent 场景客户端（mock / real 及 Workflow 适配）。

对齐《开发文档/操作文档.md》：real 目标为本地 Dify「客服Agent」Workflow，
经公共 `app/core/dify.py` 的 `DifyHttpClient` 传输；mock 阶段用关键词
硬编码覆盖 7 大场景，接口与数据流不变。
"""
from app.clients.agent.dify_client import (
    ChatResult,
    DifyClient,
    MockDifyClient,
    RealDifyClient,
    get_dify_client,
)

__all__ = [
    "ChatResult",
    "DifyClient",
    "MockDifyClient",
    "RealDifyClient",
    "get_dify_client",
]
