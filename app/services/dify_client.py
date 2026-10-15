

"""客服 Agent 的 Dify Chatflow 客户端抽象与实现。

职责边界：Dify 只做「理解意图 + 生成话术」，不直接连业务库。
当前阶段使用 MockDifyClient（关键词硬编码 7 大场景），Dify 就绪后
将 .env 的 DIFY_CLIENT 切为 real，后端接口与数据流不变。
"""
from dataclasses import dataclass
from typing import Protocol

from app.config import settings


@dataclass
class ChatResult:
    """Dify 返回的统一结构。"""

    intent: str
    reply: str
    action: dict | None = None


class DifyClient(Protocol):
    """客服 Chatflow 客户端接口（mock 与 real 均实现）。"""

    def chat(self, session_id: str, message: str) -> ChatResult: ...


class MockDifyClient:
    """按关键词硬编码意图与回复，覆盖 7 大场景的典型问法。"""

    def chat(self, session_id: str, message: str) -> ChatResult:
        m = message or ""

        if any(k in m for k in ("讲座", "活动", "分享会", "见面会", "报名")):
            return ChatResult(
                intent="event_query",
                reply="近期有以下留学讲座，您可以直接在下方报名～",
                action={"type": "show_events", "payload": {}},
            )
        if any(k in m for k in ("课程", "项目", "雅思", "托福", "PTE", "多邻国", "推荐", "提升")):
            return ChatResult(
                intent="course_recommend",
                reply="根据您的背景和意向，为您推荐以下课程～",
                action={"type": "show_courses", "payload": {}},
            )
        if any(k in m for k in ("政策", "签证", "移民", "申请门槛", "院校")):
            return ChatResult(intent="policy_query", reply="最新的留学政策已为您整理如下。")
        if any(k in m for k in ("费用", "收费", "退费", "流程", "多久", "多少钱")):
            return ChatResult(intent="faq", reply="这个问题为您找到标准答复，请参考。")
        if any(k in m for k in ("业务", "服务", "留学申请", "语言培训")):
            return ChatResult(intent="business_query", reply="我们提供留学申请、背景提升、语言培训等服务。")
        if any(k in m for k in ("公司", "机构", "品牌", "校区", "你们", "我们")):
            return ChatResult(intent="company_info", reply="我们是专业的留学服务机构，校区覆盖多地。")

        return ChatResult(
            intent="chat",
            reply="好呀，很高兴陪您聊～ 想了解留学申请、课程还是近期活动呢？",
        )


class RealDifyClient:
    """Dify Chatflow 就绪后在此实现：走 Dify /chat-messages，返回 intent + reply + action。"""

    def __init__(self) -> None:
        raise NotImplementedError("Dify Chatflow 尚未接入，请将 .env 的 DIFY_CLIENT 设为 mock")


def get_dify_client() -> DifyClient:
    """根据 .env 的 DIFY_CLIENT 返回 mock 或 real 客户端。"""
    if settings.DIFY_CLIENT == "real":
        return RealDifyClient()
    return MockDifyClient()
