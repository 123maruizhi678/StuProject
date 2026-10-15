"""兼容SQL归档目录调整，仅定位学生模块所需的既有脚本。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def enterprise_sql_path():
    for directory in (
        ROOT / "scripts/sql/bk/企业智能助手",
        ROOT / "scripts/sql/企业智能助手",
    ):
        candidate = directory / "企业智能助手_建表.sql"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("找不到学生模块依赖的企业共享表DDL")


def student_sql_directory():
    base = ROOT / "scripts/sql"
    return base / "bk/学生智能助手" if (base / "bk").is_dir() else base / "学生智能助手"
