"""日志输出工具。

特性：
    - 全局唯一初始化（init_logger 幂等，重复调用安全）
    - 日志等级由 .env 的 LOG_LEVEL 控制（可变）
    - 日志目录默认 <项目根>/app/logs，可由 .env 的 LOG_DIR 覆盖
    - 同时输出到控制台与 app/logs/app.log（按天滚动，保留 15 天）
    - 任意模块通过 get_logger(__name__) 获取 logger
    - 在 main.py 最开始调用 init_logger() 完成加载

使用：
    from app.core.common.logger import get_logger
    logger = get_logger(__name__)
    logger.info("启动完成")
"""
import logging
from datetime import date
from pathlib import Path

from app.config import LOG_DIR, settings

# 确保日志目录存在
LOG_DIR.mkdir(parents=True, exist_ok=True)
# 日志文件名按日期：YYYY-MM-DD.log（每天一个文件，自动留存历史）
LOG_FILE = LOG_DIR / f"{date.today():%Y-%m-%d}.log"

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized = False


def _resolve_level(level: str) -> int:
    """将 .env 中的等级字符串转为 logging 常量。"""
    return getattr(logging, str(level).upper(), logging.INFO)


def init_logger(to_console: bool = True, to_file: bool = True) -> None:
    """初始化全局日志配置（幂等，建议最早调用）。"""
    global _initialized
    if _initialized:
        return

    level = _resolve_level(settings.LOG_LEVEL)
    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    if to_console:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)

    if to_file:
        file_handler = logging.FileHandler(filename=str(LOG_FILE), encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    _initialized = True


def get_logger(name: str = "app") -> logging.Logger:
    """获取 logger；首次调用自动初始化。"""
    init_logger()
    return logging.getLogger(name)
