"""报告生成 Dify Workflow 适配器：把已算好的指标交给报告工作流生成正文。

调用链（操作文档 0127）：report_service → report_metrics 固定取数 →
clients/report_dify.py → 公共 DifyHttpClient → 智能报告 Workflow。
POST /workflows/run、response_mode=blocking；inputs 含 report_code 及
json.dumps 后的 metrics；只在 data.status=succeeded 时读取
data.outputs[REPORT_DIFY_OUTPUT_KEY]（默认 report_text）的非空字符串。

失败分类（041）：
    - ReportDifyError            调用未发出或明确失败，可安全重试；
    - ReportModelOutcomeUnknown  请求已发出但结果不明（超时、响应不可解析），
                                  必须停止自动重发，按可信 workflow_run_id 核对。
"""
import json
import re
from typing import Any

import httpx

from app.config import settings
from app.core.common.dify import DifyHttpClient

# 默认调用用户标识；调度与人工来源由调用方显式传入可信标识。
DEFAULT_CALL_USER = "report-service"


def _strip_reasoning(text: str) -> str:
    """去掉推理模型输出的 <think>…</think> 思考过程，只保留报告正文。"""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)


class ReportDifyError(RuntimeError):
    """报告工作流调用失败（未发出或明确失败）。"""


class ReportModelOutcomeUnknown(ReportDifyError):
    """模型调用结果不明：请求可能已到达 Dify，不得自动重发。"""


class ReportDifyClient:
    """将「已算好的指标」映射为报告生成 Workflow 的契约并解析正文输出。

    关键约束：报告工作流只负责「对已算好的数字写摘要/趋势/归因/建议」，
    严禁让 AI 自行编造数字；因此这里只把 metrics 原样传入，正文必须引用这些数字。
    """

    def __init__(self, http: DifyHttpClient | None = None) -> None:
        base = settings.REPORT_DIFY_API_BASE or settings.DIFY_API_BASE
        self.http = http or DifyHttpClient(
            base, timeout=settings.DIFY_API_TIMEOUT_SECONDS
        )

    def generate_report(
        self, report_code: str, metrics: dict, user: str = DEFAULT_CALL_USER
    ) -> str:
        """同步调用报告生成工作流，返回报告正文。"""
        api_key = settings.REPORT_DIFY_API_KEY
        if not api_key:
            raise ReportDifyError(
                "未配置报告生成 Dify 工作流 API Key（REPORT_DIFY_API_KEY）"
            )

        try:
            response = self.http.post_json_sync(
                "/workflows/run",
                api_key=api_key,
                payload={
                    "inputs": {
                        "report_code": report_code,
                        # 指标以 JSON 字符串传入，工作流内按需解析后写分析。
                        "metrics": json.dumps(metrics, ensure_ascii=False, sort_keys=True),
                    },
                    "response_mode": "blocking",
                    "user": user,
                },
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            # 请求可能已到达 Dify 但结果不明：不得自动重发。
            raise ReportModelOutcomeUnknown(
                f"报告生成 Dify 调用结果不明：{type(exc).__name__}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ReportDifyError(f"报告生成 Dify 调用失败：{exc}") from exc
        except ValueError as exc:
            # 响应不是合法 JSON 对象：结果不明。
            raise ReportModelOutcomeUnknown(
                f"报告生成 Dify 响应不可解析：{exc}"
            ) from exc

        data = response.get("data")
        if not isinstance(data, dict) or data.get("status") != "succeeded":
            raise ReportDifyError("报告生成 Dify 工作流未成功完成")

        outputs: Any = data.get("outputs")
        output_key = settings.REPORT_DIFY_OUTPUT_KEY
        content = outputs.get(output_key) if isinstance(outputs, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ReportDifyError(f"报告生成工作流输出缺少有效字段 '{output_key}'")
        # DeepSeek 推理模型会把思考过程包在 <think>…</think> 里一起返回，
        # 报告正文不需要这段，先去掉再入库。
        return _strip_reasoning(content).strip()
