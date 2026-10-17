"""客服 Agent 业务编排层。

导出 `agent_service` 子模块；路由层经 `from app.services.agent import
agent_service` 使用，导入路径与旧扁平结构保持一致。
"""
from app.services.agent import agent_service

__all__ = ["agent_service"]
