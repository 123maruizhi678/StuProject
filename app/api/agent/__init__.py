"""客服 Agent HTTP 接入层。

路由自 `app.api.agent.agent` 导出；`app/main.py` 中
`from app.api.agent import router` 的导入路径保持不变。
"""
from app.api.agent.agent import router

__all__ = ["router"]
