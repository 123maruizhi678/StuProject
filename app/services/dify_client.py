

"""客服 Agent 的 Dify Workflow 适配器。

职责边界：Dify 只做「理解意图 + 生成话术」，不直接连业务库。
Mock 仅用于明确选择的模拟模式；real 调用已发布 Workflow，不自动降级。
"""
from dataclasses import dataclass
import re
from typing import Protocol

import httpx

from app.config import settings
from app.core.common.dify import DifyHttpClient

INTENTS = frozenset({"company_info", "business_query", "policy_query", "course_recommend", "event_query", "faq", "chat"})
_ACTION_TYPES = {"event_query": "show_events", "course_recommend": "show_courses"}


class AgentDifyError(RuntimeError):
    """仅含可公开错误信息；调用方负责回滚业务事务。"""

    def __init__(self, message: str, code: int = 503):
        self.code = code
        super().__init__(message)


@dataclass
class ChatResult:
    """Dify 返回的统一结构。"""

    intent: str
    reply: str
    action: dict | None = None


class DifyClient(Protocol):
    """客服客户端接口（mock 与 real 均实现）。"""

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
    """通过公共 HTTP 工具调用客服 Workflow 并校验 intent/reply。"""

    def __init__(self, http: DifyHttpClient | None = None) -> None:
        self.http = http or DifyHttpClient(settings.DIFY_API_BASE, timeout=settings.DIFY_API_TIMEOUT_SECONDS)

    def chat(self, session_id: str, message: str) -> ChatResult:
        key = settings.DIFY_AGENT_API_KEY.get_secret_value()
        if not key:
            raise AgentDifyError("客服 Dify 应用尚未配置，请联系维护人员")

        try:
            response = self.http.post_json_sync(
                "/workflows/run",
                api_key=key,
                payload={"inputs": {"query": message}, "response_mode": "blocking", "user": "visitor-" + session_id},
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code in (401, 403):
                raise AgentDifyError("客服 Dify 应用鉴权失败，请联系维护人员") from None
            raise AgentDifyError("客服服务暂不可用，请稍后重试") from None
        except httpx.RequestError:
            # 结果可能已经在 Dify 生成；本适配器不自动重发。
            raise AgentDifyError("客服连接失败或响应超时，请稍后核实") from None
        except ValueError:
            raise AgentDifyError("客服工作流返回了无法解析的结果", code=502) from None

        data = response.get("data")
        if not isinstance(data, dict) or data.get("status") != "succeeded":
            raise AgentDifyError("客服工作流未成功完成", code=502)
        outputs = data.get("outputs")
        if not isinstance(outputs, dict):
            raise AgentDifyError("客服工作流缺少输出结果", code=502)
        intent, reply = outputs.get("intent"), outputs.get("reply")
        if not isinstance(intent, str) or intent.strip() not in INTENTS:
            raise AgentDifyError("客服工作流返回的意图不符合约定", code=502)
        if not isinstance(reply, str):
            raise AgentDifyError("客服工作流缺少有效回复", code=502)
        reply = re.sub(r"<think\b[^>]*>.*?</think\s*>", "", reply, flags=re.DOTALL | re.IGNORECASE).strip()
        if not reply or re.search(r"</?think\b", reply, re.IGNORECASE):
            raise AgentDifyError("客服工作流缺少有效回复", code=502)
        intent = intent.strip()
        action_type = _ACTION_TYPES.get(intent)
        action = {"type": action_type, "payload": {}} if action_type else None
        return ChatResult(intent=intent, reply=reply, action=action)


def get_dify_client() -> DifyClient:
    """根据 .env 的 DIFY_CLIENT 返回 mock 或 real 客户端。"""
    if settings.DIFY_CLIENT == "real":
        return RealDifyClient()
    return MockDifyClient()
