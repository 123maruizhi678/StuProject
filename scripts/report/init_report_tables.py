"""智能报告三张表的初始化脚本（report_config / report_record / report_metric）。

用法（在项目根目录执行）：
    python scripts/report/init_report_tables.py --dry-run   只打印将执行的 DDL，不连接数据库
    python scripts/report/init_report_tables.py --check     连接并核对 MySQL 版本、三张表是否已存在
    python scripts/report/init_report_tables.py --apply     建表并写入 5 条报告配置种子数据

说明：
    - 只操作智能报告模块的三张已部署表，不触碰其它业务表；041 拟新增的
      report_task 执行任务表不由此脚本创建（尚未部署，须开发评审后受控增量）。
    - 建表前不删除任何已有表；create_all 默认 checkfirst，重复执行是幂等的。
    - 种子数据只在 report_config 为空时写入，不会覆盖你改过的配置。
    - 需要 MySQL 8.0.16+（表使用 utf8mb4_0900_ai_ci 排序规则）。
    - 目标数据库（默认 education_agent）需先存在，脚本不负责创建数据库。

调度口径（操作文档 0230）：daily_report 每天 17:00，其余四类每周五 17:00，
时区 Asia/Shanghai；cron 为含秒六字段方言。存量库中的旧 18:30/09:00 种子
按受控增量 UPDATE 至 17:00 并递增 row_version，保留五类 code，不 DROP 重建；
参见 scripts/sql/report/README.md。
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from typing import cast

from sqlalchemy import Table, func, select, text
from sqlalchemy.dialects.mysql import dialect as mysql_dialect
from sqlalchemy.schema import CreateTable

from app.database import SessionLocal, engine
from app.models.report.report import REPORT_TABLES as _REPORT_TABLES
from app.models.report.report import ReportConfig

# SQLAlchemy 类型桩把 __table__ 标成 FromClause，这里显式收敛为 Table，
# 便于 CreateTable / get_table_names / create_all 使用，消除静态检查告警。
REPORT_TABLES: tuple[Table, ...] = cast("tuple[Table, ...]", _REPORT_TABLES)

# 报告配置种子数据：与 scripts/sql/all.sql 中的 5 条 INSERT 口径一致；
# cron 为目标调度时刻（含秒六字段，东八区 17:00）。
SEED_CONFIGS = [
    ("customer_overview", "全域客户经营分析报告", "week", "0 0 17 * * 5", True),
    ("daily_report", "员工日报汇总报告（日）", "day", "0 0 17 * * *", True),
    ("weekly_report", "员工日报汇总报告（周）", "week", "0 0 17 * * 5", True),
    ("mental_weekly", "学生心理健康周报", "week", "0 0 17 * * 5", True),
    ("complaint_weekly", "投诉处理周报", "week", "0 0 17 * * 5", True),
]

MIN_MYSQL = (8, 0, 16)


def parse_mysql_version(version: str) -> tuple[int, ...] | None:
    """解析 `SELECT VERSION()` 的结果；MariaDB 返回 None。"""
    if "mariadb" in version.lower():
        return None
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    return tuple(map(int, match.groups())) if match else None


def print_ddl() -> None:
    """打印三张表的 MySQL DDL，不连接数据库。"""
    # DDL 含中文表注释：固定以 UTF-8 输出，避免 Windows 控制台代码页
    # （cp936）导致调用方按 UTF-8 解码失败。
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    mysql = mysql_dialect()
    for table in REPORT_TABLES:
        print(CreateTable(table).compile(dialect=mysql).string.strip())
        print()


def check_database() -> int:
    """连接数据库，核对版本与三张表是否存在。返回退出码。"""
    with engine.connect() as conn:
        version = conn.execute(text("SELECT VERSION()")).scalar()
        parsed = parse_mysql_version(str(version))
        print(f"MySQL 版本：{version}")
        if parsed is None:
            print("[失败] 检测到 MariaDB，或无法识别版本；请使用 MySQL 8.0.16+。")
            return 2
        if parsed < MIN_MYSQL:
            print(f"[失败] 需要 MySQL 8.0.16+，当前 {version}。")
            return 2

        existing = set(engine.dialect.get_table_names(conn))
        print()
        for table in REPORT_TABLES:
            mark = "已存在" if table.name in existing else "缺失"
            print(f"  {table.name:18s} {mark}")

        missing = [t.name for t in REPORT_TABLES if t.name not in existing]
        if missing:
            print(f"\n[提示] 缺失表：{', '.join(missing)}（用 --apply 创建）")
        else:
            print("\n三张表均已存在。")
    return 0


def apply() -> int:
    """建表并写入种子配置。"""
    # 连接统一使用 UTC 会话时区，与 all.sql 约定一致。
    with engine.connect() as conn:
        conn.execute(text("SET SESSION time_zone = '+00:00'"))
        conn.commit()

    # 只创建智能报告的三张已部署表；checkfirst 保证重复执行安全。
    from app.database import Base

    Base.metadata.create_all(bind=engine, tables=list(REPORT_TABLES))
    print("已创建/核对三张表：report_config / report_record / report_metric")

    with SessionLocal() as session:
        count = session.scalar(select(func.count()).select_from(ReportConfig))
        if count:
            print(f"report_config 已有 {count} 条配置，跳过种子数据。")
        else:
            session.add_all(
                ReportConfig(
                    report_code=code,
                    report_name=name,
                    report_period=period,
                    cron_expr=cron,
                    enabled=enabled,
                )
                for code, name, period, cron, enabled in SEED_CONFIGS
            )
            session.commit()
            print("已写入 5 条报告配置种子数据。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="智能报告三张表初始化脚本")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="只打印 DDL，不连接数据库")
    group.add_argument("--check", action="store_true", help="连接并核对版本与表是否存在")
    group.add_argument("--apply", action="store_true", help="建表并写入种子配置")
    args = parser.parse_args()

    if args.check:
        return check_database()
    if args.apply:
        return apply()
    # 默认（或 --dry-run）
    print_ddl()
    return 0


if __name__ == "__main__":
    sys.exit(main())
