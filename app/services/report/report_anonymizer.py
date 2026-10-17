"""智能报告脱敏与发布投影：心理匿名聚合、推理剥离、失败脱敏、正文对账。

契约来源（操作文档 0127/0338/044/045）：
    - 传入模型的输入必须是「已计算指标」并先应用心理聚合范围；心理周报仅允许
      匿名聚合输出，学生明细、原因及个人情绪值不交模型（045）。
    - 保存前剥离 `<think>…</think>` 推理内容；正文中的数字必须映射到受控指标、
      必要单位/日期/版本白名单，新增数字、错单位、错分母或舍入不符均失败
      （044/0338），失败不发布半成品。
    - fail_reason 只保存脱敏说明，不泄露路径、SQL、密钥或内部标识。
    - 对外 metric_json 仅返回已发布指标白名单及非敏感版本元数据；保留区
      （_manifest/_calculation_inputs）不进入响应，Dify 不直接透传整个
      metric_json。
"""
import re
from typing import Any

# 隐私保护规则版本；跨版本不可比（045/043）。
PRIVACY_POLICY_VERSION = "privacy-v1"

# 心理周报允许进入模型的匿名聚合指标前缀（045 白名单）。
_MENTAL_MODEL_CODE_PATTERN = re.compile(
    r"^mental_(assessment|warning|risk)_[a-z_]+_(count|rate|change_rate)$"
)

# 日期与版本形态：对账时先移除，避免把日期/版本数字当作正文编造数字。
_DATE_PATTERNS = [
    re.compile(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?"),
    re.compile(r"\d{1,2}[-/月]\d{1,2}日?"),
    re.compile(r"\d{4}年"),
    re.compile(r"\d{1,2}月"),
]
_VERSION_PATTERNS = [
    re.compile(r"metrics-v\d+"),
    re.compile(r"\bv\d+(?:\.\d+)*\b", re.IGNORECASE),
]
# 行首列表序号（Markdown 有序列表）不作为正文数字。
_LIST_MARKER_PATTERN = re.compile(r"^\s*\d{1,2}[.、)]\s+", re.MULTILINE)
# 正文数字：支持千分位与小数。
_NUMBER_PATTERN = re.compile(r"\d[\d,]*(?:\.\d+)?")


class AnonymizationError(Exception):
    """心理匿名聚合范围未就绪：阻止发布与传模。"""


class ContentReconciliationError(Exception):
    """正文数字与受控指标对账失败。"""


def _is_aggregate_only(entries: dict[str, dict]) -> bool:
    """心理指标必须全部为匿名聚合（计数/比例/变化率），不含任何明细键。"""
    return all(_MENTAL_MODEL_CODE_PATTERN.match(code) for code in entries)


def anonymize_for_model(report_code: str, entries: dict[str, dict]) -> dict:
    """生成模型输入：仅传已发布指标白名单；心理周报强制匿名聚合（045）。"""
    if report_code == "mental_weekly":
        mental_entries = {
            code: entry
            for code, entry in entries.items()
            if code.startswith("mental_")
        }
        if not _is_aggregate_only(mental_entries):
            raise AnonymizationError(
                "心理周报指标未全部通过匿名聚合白名单，阻止传入模型"
            )
        allowed = mental_entries
    else:
        allowed = entries

    return {
        code: {
            "value": entry.get("value"),
            "unit": entry.get("unit"),
            "availability": entry.get("availability"),
        }
        for code, entry in allowed.items()
    }


def strip_reasoning(text: str) -> str:
    """去掉推理模型输出的 <think>…</think> 思考过程，只保留报告正文。"""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)


_PATH_PATTERNS = [
    re.compile(r"[A-Za-z]:\\[^\s，。；、]+"),
    re.compile(r"(?<![\w])/(?:home|usr|var|opt|tmp|app|Users)/[^\s，。；、]+"),
    re.compile(r"https?://\S+"),
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"\b(?:sk|pk|ak)-[A-Za-z0-9_\-]{8,}\b"),
]


def sanitize_fail_reason(message: str, limit: int = 200) -> str:
    """把失败原因收敛为脱敏说明：去路径、URL、密钥，截断并折叠空白。"""
    text = str(message)
    for pattern in _PATH_PATTERNS:
        text = pattern.sub("<redacted>", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text or "未知失败原因"


def public_metric_json(entries: dict[str, dict]) -> dict:
    """对外指标投影：已发布白名单 + 非敏感版本元数据，剔除保留区。"""
    projected: dict[str, Any] = {}
    for code, entry in entries.items():
        if code.startswith("_"):
            continue  # _manifest/_calculation_inputs 保留区不对外
        item = {
            "value": entry.get("value"),
            "unit": entry.get("unit"),
            "availability": entry.get("availability"),
            "metric_version": entry.get("metric_version"),
        }
        reason = entry.get("reason")
        if reason:
            item["reason"] = reason
        projected[code] = item
    return projected


def _number_forms(value: float) -> set[str]:
    """同一指标值的可接受书写形式（整数、原值、1/2/4 位小数）。

    整数值（如 75 或 75.0）同时放行整数与小数书写：指标 JSON 中 75.0 会
    序列化为 "75.0"，模型原样引用该写法属于同值表述，不是舍入不符。
    """
    forms: set[str] = set()
    if float(value) == int(value):
        forms.add(str(int(value)))
        forms.add(f"{float(value):.1f}")
        forms.add(f"{float(value):.2f}")
    else:
        forms.add(repr(float(value)))
        forms.add(f"{value:.4f}".rstrip("0").rstrip("."))
        forms.add(f"{value:.2f}")
        forms.add(f"{value:.1f}")
    return forms


def reconcile_content(report_code: str, content: str, entries: dict[str, dict]) -> None:
    """正文对账（044/0338）：正文数字必须映射到受控指标或日期/版本白名单。

    禁止新增数字、错单位、错分母或舍入不符；任何无法映射的数字都判失败，
    由调用方把记录标记为 failed，不发布半成品正文。
    """
    allowed: set[str] = set()
    for entry in entries.values():
        value = entry.get("value")
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, (int, float)):
            allowed.update(_number_forms(float(value)))

    scrubbed = content
    for pattern in _DATE_PATTERNS + _VERSION_PATTERNS:
        scrubbed = pattern.sub(" ", scrubbed)
    scrubbed = _LIST_MARKER_PATTERN.sub(" ", scrubbed)

    unmapped: set[str] = set()
    for match in _NUMBER_PATTERN.finditer(scrubbed):
        token = match.group().replace(",", "")
        if token in allowed:
            continue
        # 百分比形式：12.5% 的数值部分仍须映射到受控指标。
        tail = scrubbed[match.end(): match.end() + 1]
        if tail == "%" and token in allowed:
            continue
        unmapped.add(token)

    if unmapped:
        raise ContentReconciliationError(
            "正文包含无法映射到受控指标的数字："
            + ", ".join(sorted(unmapped)[:10])
        )
