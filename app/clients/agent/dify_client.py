"""客服 Agent 的 Dify Workflow 客户端抽象与实现。

职责边界：Dify 只做「理解意图 + 生成话术」，不直接连业务库。
当前阶段使用 MockDifyClient（关键词硬编码 7 大场景），Dify 就绪后
将 .env 的 DIFY_CLIENT 切为 real，后端接口与数据流不变。
"""
import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.config import settings
from app.core.dify import DifyHttpClient
from app.core.logger import get_logger

logger = get_logger(__name__)

# 意图 -> 前端动作：由后端按 intent 推导，不依赖 Dify 输出
_INTENT_ACTION_MAP = {
    "course_recommend": {"type": "show_courses", "payload": {}},
    "event_query": {"type": "show_events", "payload": {}},
}

# 推理模型（deepseek-reasoner 等）会把思维链混进 LLM 输出文本，需在返回前剥掉，
# 避免客户看到 AI 的内部推理过程。匹配 <think>...</think> 整块及其中的 reasoning 标记。
_REASONING_BLOCK = re.compile(
    r"<think>\s*(?:<!--[\w.-]*reasoning[\w.-]*-->.*?)?</think>\s*", re.DOTALL
)
_REASONING_MARKER = re.compile(r"<!--[\w.-]*reasoning[\w.-]*-->")


def _strip_reasoning(text: str) -> str:
    """剥除回复中的思维链块与残留 reasoning 标记，仅保留面向客户的正文。"""
    if not text:
        return text
    cleaned = _REASONING_BLOCK.sub("", text)
    cleaned = _REASONING_MARKER.sub("", cleaned)
    return cleaned.strip()


@dataclass
class ChatResult:
    """Dify 返回的统一结构。"""

    intent: str
    reply: str
    action: dict | None = None


class DifyClient(Protocol):
    """客服 Workflow 客户端接口（mock 与 real 均实现）。"""

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
    """Dify 客服工作流客户端：POST /workflows/run，读取 data.outputs。

    对应 Dify 应用「客服Agent」（Workflow 模式）：
        入参 inputs.query = 访客消息
        出参 outputs.intent = 意图英文 slug，outputs.reply = 话术
    action 由本模块按 intent 推导，与 mock 行为保持一致。
    """

    def __init__(self) -> None:
        self.key = settings.DIFY_AGENT_API_KEY
        if not self.key:
            raise ValueError("未配置 DIFY_AGENT_API_KEY，无法启用 real 客户端（请将 .env 的 DIFY_CLIENT 设为 mock）")
        self._http = DifyHttpClient(api_base=settings.DIFY_API_BASE, timeout=settings.DIFY_API_TIMEOUT_SECONDS)

    def chat(self, session_id: str, message: str) -> ChatResult:
        payload = {
            "inputs": {"query": message},
            "response_mode": "blocking",
            "user": f"visitor-{session_id}",
        }
        data = self._http.post_json_sync("workflows/run", api_key=self.key, payload=payload)
        outputs: dict[str, Any] = data.get("data", {}).get("outputs") or {}
        intent = outputs.get("intent") or "chat"
        reply = _strip_reasoning(outputs.get("reply") or "")
        if not reply:
            logger.warning("Dify 工作流返回 reply 为空: outputs=%s", outputs)
        return ChatResult(intent=intent, reply=reply, action=_INTENT_ACTION_MAP.get(intent))


def get_dify_client() -> DifyClient:
    """根据 .env 的 DIFY_CLIENT 返回 mock 或 real 客户端。"""
    if settings.DIFY_CLIENT == "real":
        return RealDifyClient()
    return MockDifyClient()
