"""配置管理：从项目根目录 .env 读取环境变量。

使用 pydantic-settings，所有配置集中在此，供 logger / database 等模块共享。
新增配置只需在 .env 添加对应字段并在 Settings 中声明即可。
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（StuProject），.env 置于此
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 日志
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = ""  # 为空则使用默认 app/logs

    # 数据库（后续 database.py 使用）
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "12345"
    DB_NAME: str = "education_agent"
    DB_ECHO: bool = False


settings = Settings()

# 日志目录：优先使用 .env 中的 LOG_DIR，否则默认 <根>/app/logs
LOG_DIR = Path(settings.LOG_DIR) if settings.LOG_DIR else (BASE_DIR / "app" / "logs")
