"""配置管理：从项目根目录 .env 读取环境变量。

使用 pydantic-settings，所有配置集中在此，供 logger / database 等模块共享。
新增配置只需在 .env 添加对应字段并在 Settings 中声明即可。
"""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

# 项目根目录（StuProject），.env 置于此
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR / ".env"), str(BASE_DIR / ".env.student.local")),
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
    DB_PASSWORD: str = Field(default="12345", repr=False)
    DB_NAME: str = "education_agent"
    DB_ECHO: bool = False

    # Dify NL2SQL 工作流
    DIFY_API_BASE: str = "http://127.0.0.1/v1"
    DIFY_API_KEY: str = Field(default="", repr=False)
    DIFY_SQL_OUTPUT_KEY: str = "sql"

    # 学生接口只接受签名身份；未配置密钥时关闭身份入口，不信任前端 student_id。
    STUDENT_AUTH_SECRET: str = Field(default="", repr=False)
    STUDENT_TOKEN_ISSUER: str = "stuproject"
    STUDENT_ACTION_TTL_SECONDS: int = 300
    STUDENT_DIFY_CHAT_KEY: str = Field(default="", repr=False)
    STUDENT_DIFY_MENTAL_KEY: str = Field(default="", repr=False)
    STUDENT_DIFY_TICKET_KEY: str = Field(default="", repr=False)
    STUDENT_ANALYSIS_VERSION: str = "student-v1"
    STUDENT_HTTP_TIMEOUT: float = Field(default=30.0, gt=0, le=120)
    STUDENT_QUERY_BACKEND: Literal["group", "local"] = "group"
    STUDENT_NL2SQL_URL: str = ""
    STUDENT_NL2SQL_TOKEN: str = Field(default="", repr=False)
    STUDENT_EDUCATION_URL: str = ""
    STUDENT_EDUCATION_TOKEN: str = Field(default="", repr=False)
    STUDENT_CRM_URL: str = ""
    STUDENT_CRM_TOKEN: str = Field(default="", repr=False)
    STUDENT_NOTIFICATION_URL: str = ""
    STUDENT_NOTIFICATION_TOKEN: str = Field(default="", repr=False)
    STUDENT_NOTIFICATION_MAX_ATTEMPTS: int = Field(default=5, ge=1, le=100)
    STUDENT_NOTIFICATION_LEASE_SECONDS: int = Field(default=120, ge=5, le=3600)
    STUDENT_FALLBACK_EMPLOYEE_ID: int | None = None
    STUDENT_TICKET_RESPONSE_HOURS: int = Field(default=24, ge=1)
    STUDENT_TICKET_RESOLUTION_HOURS: int = Field(default=72, ge=1)
    STUDENT_SYNC_INTERVAL_SECONDS: int = Field(default=300, ge=1)

    @field_validator("STUDENT_FALLBACK_EMPLOYEE_ID", mode="before")
    @classmethod
    def optional_fallback(cls, value):
        return None if value in (None, "") else value


settings = Settings()

# 日志目录：优先使用 .env 中的 LOG_DIR，否则默认 <根>/app/logs
LOG_DIR = Path(settings.LOG_DIR) if settings.LOG_DIR else (BASE_DIR / "app" / "logs")
