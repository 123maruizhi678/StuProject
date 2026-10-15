"""配置管理：从项目根目录 .env 读取环境变量。"""

from pathlib import Path

from typing import Literal
from pydantic import Field
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
    LOG_DIR: str = ""
    # DB_* 字段共同指定 MySQL 连接目标和认证信息。
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = Field(default="12345", repr=False)
    DB_NAME: str = "education_agent"
    DB_ECHO: bool = False
    # DIFY_API_BASE、DIFY_API_KEY、DIFY_SQL_OUTPUT_KEY 配置 NL2SQL 工作流。
    DIFY_API_BASE: str = "http://127.0.0.1/v1"
    DIFY_API_KEY: str = Field(default="", repr=False)
    DIFY_SQL_OUTPUT_KEY: str = "sql"
    AUTH_SECRET_KEY: str = Field(default="", repr=False)
    AUTH_TOKEN_EXPIRE_MINUTES: int = Field(default=120, ge=1)
    ACCESS_CONTROL_FILE: Path = BASE_DIR / "app" / "access_control.yaml"
    ENTERPRISE_COURSES_FILE: Path = BASE_DIR / "app" / "enterprise_courses.yaml"
    # local 表示本机成绩表为测试事实源；外部只读权威模式拒绝所有本地写入。
    ENTERPRISE_SCORE_AUTHORITY: Literal["local", "external_readonly"] = "local"
    ENTERPRISE_STUDENT_MAINTAINER_IDS: list[int] = []
    STUDENT_SCORE_DIFY_BASE: str = "http://localhost/v1"
    STUDENT_SCORE_DIFY_KEY: str = Field(default="", repr=False)


settings = Settings()
LOG_DIR = Path(settings.LOG_DIR) if settings.LOG_DIR else (BASE_DIR / "app" / "logs")
