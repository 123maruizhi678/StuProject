"""报告 Dify 工作流联调验证：真实调用本地 Dify，按操作文档 044/041 验收。

验收标准（不以 HTTP 200 为成功）：
    1. POST {REPORT_DIFY_API_BASE 或 DIFY_API_BASE}/workflows/run 可调通；
    2. data.status=succeeded 且 data.outputs[REPORT_DIFY_OUTPUT_KEY] 非空；
    3. 返回正文已剥离 <think>…</think> 推理内容；
    4. 正文中的数字全部可映射到传入指标（复用服务同款对账逻辑）；
    5. 超时/网络错误按 ReportModelOutcomeUnknown 归类（不得自动重发）。

用法：
    python scripts/report/verify_report_dify.py [--report-code daily_report]

--report-code 支持模块全部五种报告类型（customer_overview / daily_report /
weekly_report / mental_weekly / complaint_weekly），各自使用对应口径的内置样本。

说明：默认使用 app/config.py 读取的本机 .env 配置；样本指标为固定假数据，
仅用于验证链路契约，不代表真实取数结果。
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.clients.report import (  # noqa: E402
    ReportDifyClient,
    ReportDifyError,
    ReportModelOutcomeUnknown,
)
from app.config import settings  # noqa: E402
from app.services.report.report_anonymizer import (  # noqa: E402
    ContentReconciliationError,
    reconcile_content,
)

# 样本指标：各报告类型的固定假数据（内部冻结格式，不含保留区）。
# 字段结构与 report_metrics 产出的 entries 一致（value/unit/availability/calc_rule）。
SAMPLE_ENTRIES = {
    "daily_report": {
        "daily_submitted_count": {
            "value": 18,
            "unit": "条",
            "availability": "available",
            "calc_rule": "submitted_at 位于窗口内的日报条数",
        },
        "daily_author_count": {
            "value": 16,
            "unit": "人",
            "availability": "available",
            "calc_rule": "窗口内提交过的 distinct employee_id",
        },
        "daily_void_count": {
            "value": None,
            "availability": "unavailable",
            "reason": "缺可信作废事件历史，不按 report_date 倒推",
            "calc_rule": "窗口内作废事件条数",
        },
    },
    "weekly_report": {
        "daily_submitted_count": {
            "value": 96,
            "unit": "条",
            "availability": "available",
            "calc_rule": "submitted_at 位于窗口内的日报条数",
        },
        "daily_author_count": {
            "value": 42,
            "unit": "人",
            "availability": "available",
            "calc_rule": "窗口内提交过的 distinct employee_id",
        },
        "daily_void_count": {
            "value": None,
            "availability": "unavailable",
            "reason": "缺可信作废事件历史，不按 report_date 倒推",
            "calc_rule": "窗口内作废事件条数",
        },
    },
    "customer_overview": {
        "customer_total": {"value": 128, "unit": "个", "availability": "available", "calc_rule": "去快照 distinct customer_id"},
        "customer_state_signed": {"value": 45, "unit": "个", "availability": "available", "calc_rule": "按 status 分类的 distinct customer_id"},
        "customer_state_new": {"value": 38, "unit": "个", "availability": "available", "calc_rule": "按 status 分类的 distinct customer_id"},
        "customer_state_lost": {"value": 12, "unit": "个", "availability": "available", "calc_rule": "按 status 分类的 distinct customer_id"},
        "customer_archived_count": {"value": 7, "unit": "个", "availability": "available", "calc_rule": "is_archived=1 的 distinct customer_id"},
        "customer_new_count": {"value": 9, "unit": "个", "availability": "available", "calc_rule": "created_at 位于窗口内的 distinct customer_id"},
        "followup_count": {"value": 56, "unit": "次", "availability": "available", "calc_rule": "followup_at 位于窗口内的跟进次数"},
        "followup_customer_count": {"value": 31, "unit": "个", "availability": "available", "calc_rule": "窗口内被跟进的 distinct customer_id"},
        "customer_lost_event_count": {
            "value": None,
            "availability": "unavailable",
            "reason": "缺状态事件历史，不用当前 lost 数冒充",
            "calc_rule": "窗口内进入 lost 的事件条数",
        },
        "research_match_rate": {
            "value": None,
            "availability": "unavailable",
            "reason": "研判上游表未部署",
            "calc_rule": "命中研判的客户占比",
        },
    },
    "mental_weekly": {
        "mental_assessment_count": {"value": 23, "unit": "次", "availability": "available", "calc_rule": "observed_at 位于窗口内的评估次数"},
        "mental_risk_low_count": {"value": 15, "unit": "次", "availability": "available", "calc_rule": "按风险等级分类"},
        "mental_risk_medium_count": {"value": 5, "unit": "次", "availability": "available", "calc_rule": "按风险等级分类"},
        "mental_risk_high_count": {"value": 2, "unit": "次", "availability": "available", "calc_rule": "按风险等级分类"},
        "mental_risk_critical_count": {"value": 1, "unit": "次", "availability": "available", "calc_rule": "按风险等级分类"},
        "mental_warning_count": {"value": 3, "unit": "次", "availability": "available", "calc_rule": "窗口内预警次数"},
        "mental_warning_pending_count": {"value": 2, "unit": "次", "availability": "available", "calc_rule": "按跟进状态分类"},
        "mental_warning_closed_count": {"value": 1, "unit": "次", "availability": "available", "calc_rule": "按跟进状态分类"},
        "mental_assessment_change_rate": {"value": 15.0, "unit": "%", "availability": "available", "calc_rule": "与上一等长窗口比较的变化率"},
    },
    "complaint_weekly": {
        "complaint_new_count": {"value": 24, "unit": "件", "availability": "available", "calc_rule": "窗口内新建的投诉工单数"},
        "complaint_new_state_new_count": {"value": 2, "unit": "件", "availability": "available", "calc_rule": "新建投诉的当前状态分布"},
        "complaint_new_state_processing_count": {"value": 9, "unit": "件", "availability": "available", "calc_rule": "新建投诉的当前状态分布"},
        "complaint_new_state_awaiting_student_count": {"value": 4, "unit": "件", "availability": "available", "calc_rule": "新建投诉的当前状态分布"},
        "complaint_new_state_closed_count": {"value": 9, "unit": "件", "availability": "available", "calc_rule": "新建投诉的当前状态分布"},
        "complaint_category_teaching_count": {"value": 13, "unit": "件", "availability": "available", "calc_rule": "按类别分布"},
        "complaint_category_visa_count": {"value": 7, "unit": "件", "availability": "available", "calc_rule": "按类别分布"},
        "complaint_category_life_count": {"value": 4, "unit": "件", "availability": "available", "calc_rule": "按类别分布"},
        "complaint_open_count": {"value": 6, "unit": "件", "availability": "available", "calc_rule": "截至快照未关闭存量"},
        "complaint_first_response_hours": {"value": 6.5, "unit": "小时", "availability": "available", "calc_rule": "窗口内首次有效人工回应时长"},
        "complaint_first_response_timely_rate": {"value": 75.0, "unit": "%", "availability": "available", "calc_rule": "首次回应及时率"},
        "complaint_response_overdue_count": {"value": 3, "unit": "件", "availability": "available", "calc_rule": "超期未回应件数"},
        "complaint_solved_cycle_count": {"value": 18, "unit": "轮", "availability": "available", "calc_rule": "按轮次去重的给方案量"},
        "complaint_closed_cycle_count": {"value": 12, "unit": "轮", "availability": "available", "calc_rule": "按轮次去重的关闭量"},
        "complaint_closed_count": {"value": 11, "unit": "件", "availability": "available", "calc_rule": "最终关闭工单数"},
        "complaint_close_hours": {"value": 52.25, "unit": "小时", "availability": "available", "calc_rule": "最终关闭时长"},
        "complaint_satisfaction_avg": {"value": 4.2, "unit": "分", "availability": "available", "calc_rule": "最终关闭且已评分均值"},
        "complaint_satisfaction_rate": {"value": 72.7, "unit": "%", "availability": "available", "calc_rule": "满意率"},
        "complaint_rating_coverage_rate": {"value": 81.8, "unit": "%", "availability": "available", "calc_rule": "评分覆盖率"},
    },
}


def sample_for(report_code: str) -> dict:
    """取该报告类型的样本指标；未收录的类型给出明确失败而非静默用错数据。"""
    entries = SAMPLE_ENTRIES.get(report_code)
    if entries is None:
        raise SystemExit(
            f"[失败] 暂无 {report_code} 的内置样本；请改用真实链路或用 --report-code 指定已收录类型："
            f"{sorted(SAMPLE_ENTRIES)}"
        )
    return dict(entries)


def main() -> int:
    parser = argparse.ArgumentParser(description="报告 Dify 工作流联调验证")
    parser.add_argument("--report-code", default="daily_report")
    parser.add_argument(
        "--api-key",
        default=None,
        help="临时指定 API Key 进行验证（不修改 .env）；缺省用 REPORT_DIFY_API_KEY",
    )
    args = parser.parse_args()

    base = settings.REPORT_DIFY_API_BASE or settings.DIFY_API_BASE
    api_key = args.api_key or settings.REPORT_DIFY_API_KEY
    output_key = settings.REPORT_DIFY_OUTPUT_KEY

    print("== 配置 ==")
    print(f"  base        : {base}")
    print(f"  output_key  : {output_key}")
    print(f"  timeout     : {settings.DIFY_API_TIMEOUT_SECONDS}s")
    print(f"  api_key     : {'已配置（' + api_key[:8] + '…）' if api_key else '未配置'}")

    if not api_key:
        print("[失败] 未配置 REPORT_DIFY_API_KEY，无法联调")
        return 2

    if args.api_key:
        # 仅覆盖本次进程内的配置，不写回 .env。
        settings.REPORT_DIFY_API_KEY = args.api_key

    metrics = sample_for(args.report_code)
    print(f"  样本指标    : {len(metrics)} 项")
    client = ReportDifyClient()

    print(f"\n== 调用工作流（report_code={args.report_code}）==")
    started = time.monotonic()
    try:
        content = client.generate_report(args.report_code, metrics, user="verify-script")
    except ReportModelOutcomeUnknown as exc:
        print(f"[结果不明] {exc}")
        print("  → 按 041：请求可能已到达 Dify，不得自动重发；请稍后按 workflow_run_id 核对。")
        return 3
    except ReportDifyError as exc:
        print(f"[调用失败] {exc}")
        return 4
    elapsed = time.monotonic() - started

    timeout = settings.DIFY_API_TIMEOUT_SECONDS
    print(f"  耗时        : {elapsed:.2f}s（超时上限 {timeout}s）")
    if elapsed > timeout * 0.6:
        print("  [提醒] 耗时超过超时上限 60%，指标体量大时需评估调大 DIFY_API_TIMEOUT_SECONDS")
    print(f"  正文长度    : {len(content)} 字符")
    print(f"  推理残留    : {'有（异常）' if '<think>' in content else '无（已剥离）'}")

    if not content.strip():
        print("[失败] 正文为空")
        return 5

    print("\n== 正文预览（前 300 字）==")
    print("  " + content[:300].replace("\n", "\n  "))

    print("\n== 数字对账（044）==")
    try:
        reconcile_content(args.report_code, content, metrics)
        print("  通过：正文数字均可映射到受控指标")
    except ContentReconciliationError as exc:
        print(f"  失败：{exc}")
        print(
            f"RESULT report_code={args.report_code} elapsed={elapsed:.2f}s "
            f"content_len={len(content)} reconcile=fail"
        )
        return 6

    print("\n[通过] 报告 Dify 工作流联调验证成功")
    print(
        f"RESULT report_code={args.report_code} elapsed={elapsed:.2f}s "
        f"content_len={len(content)} reconcile=pass"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
