"""智能报告调度进程入口：恢复过期租约 → 扫描缺失窗口 → 执行待生成报告。

用法（在项目根目录执行）：
    python scripts/report/run_report_tasks.py --once             单轮：扫描并执行一轮
    python scripts/report/run_report_tasks.py --interval 300     每 300 秒一轮（循环）
    python scripts/report/run_report_tasks.py --dry-run          只打印将生成的窗口，不写库
    python scripts/report/run_report_tasks.py --max-tasks 10     单轮最多执行 10 个报告

边界（操作文档 0127/0230/041）：
    - 只执行 report_config 中 enabled=1 且 cron_expr 非空的配置；设置 enabled
      或 cron 不代表任务已经启用，上游、指标、范围授权、审计、任务与已发布
      应用就绪后，才由平台管理员受控启用。
    - 生成复用授权生成链路（report_service.run_generation），不是另一个对外
      公开模型入口；本期只生成公司范围报告，部门范围依赖未就绪时不降级。
    - failed / MODEL_OUTCOME_UNKNOWN 记录不会被补偿扫描当作缺失窗口重发；
      report_task 持久任务表（041 拟新增）未部署时，执行所有权回退为
      report_record 行版本栅栏，跨进程卡死的 running 记录不自动重发。
    - 本进程不访问模型供应商，也不校验 Dify 发布状态；真实调用由生成链路
      经 REPORT_DIFY_API_KEY 完成。
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.core.logger import get_logger, init_logger
from app.database import SessionLocal
from app.tasks.report.report_tasks import (
    ReportTaskQueue,
    drain,
    run_once,
    scheduler_scan,
)

init_logger()
logger = get_logger("report-tasks")


def _print(summary: dict) -> None:
    print(json.dumps(summary, ensure_ascii=False, default=str, indent=2))


def dry_run() -> int:
    """只扫描将生成的窗口，不写库、不执行。"""
    try:
        with SessionLocal() as db:
            queue = ReportTaskQueue(db)
            scan = scheduler_scan(db)
            _print({"backend": queue.backend, "scan": scan, "dry_run": True})
    except Exception as exc:  # noqa: BLE001 - 数据库不可达时给出明确退出码
        print(f"[失败] 无法连接数据库读取报告配置：{type(exc).__name__}")
        return 2
    return 0


def single_round(max_tasks: int) -> int:
    """单轮：恢复 → 扫描 → 执行。"""
    with SessionLocal() as db:
        queue = ReportTaskQueue(db)
        scan = scheduler_scan(db)
        result = drain(db, max_tasks=max_tasks)
        _print(
            {
                "backend": queue.backend,
                "recover": queue.recover_stalled(),
                "scan": scan,
                "drain": result,
            }
        )
    return 0


def loop(interval: int, max_tasks: int) -> int:
    logger.info("报告调度进程启动：interval=%ss max_tasks=%s", interval, max_tasks)
    try:
        while True:
            with SessionLocal() as db:
                run_once(db)
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("报告调度进程已停止")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="智能报告调度进程")
    parser.add_argument("--once", action="store_true", help="单轮后退出（默认）")
    parser.add_argument("--interval", type=int, default=300, help="循环模式间隔秒数")
    parser.add_argument("--max-tasks", type=int, default=10, help="单轮最多执行报告数")
    parser.add_argument("--dry-run", action="store_true", help="只扫描不写库不执行")
    args = parser.parse_args()

    if args.dry_run:
        return dry_run()
    if args.interval and not args.once and "--interval" in sys.argv:
        return loop(args.interval, args.max_tasks)
    return single_round(args.max_tasks)


if __name__ == "__main__":
    sys.exit(main())
