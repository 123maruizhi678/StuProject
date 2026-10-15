"""配置管理：从项目根目录 .env 读取环境变量。"""

from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr
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


settings = Settings()
LOG_DIR = Path(settings.LOG_DIR) if settings.LOG_DIR else (BASE_DIR / "app" / "logs")


class StudentLeaveDifySettings(BaseSettings):
    """学生请假专用工作流配置，不复用组长的NL2SQL应用Key。"""
    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR / ".env"), str(BASE_DIR / ".env.student.local")),
        env_file_encoding="utf-8", extra="ignore",
    )
    STUDENT_DIFY_LEAVE_BASE: AnyHttpUrl = "http://127.0.0.1/v1"
    STUDENT_DIFY_LEAVE_KEY: SecretStr = Field(default=SecretStr(""), repr=False)
    STUDENT_DIFY_LEAVE_TIMEOUT: float = Field(default=60, gt=0, le=120)
    STUDENT_DIFY_LEAVE_VERSION: str = Field(default="student-leave-v1", min_length=1, max_length=64)


student_leave_dify_settings = StudentLeaveDifySettings()


class StudentTicketSettings(BaseSettings):
    """学生投诉专用配置；模型密钥与NL2SQL、JWT分开。"""
    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR / ".env"), str(BASE_DIR / ".env.student.local")),
        env_file_encoding="utf-8", extra="ignore",
    )
    STUDENT_DIFY_TICKET_BASE: AnyHttpUrl = "http://127.0.0.1/v1"
    STUDENT_DIFY_TICKET_KEY: SecretStr = Field(default=SecretStr(""), repr=False)
    STUDENT_DIFY_TICKET_TIMEOUT: float = Field(default=15, gt=0, le=60)
    STUDENT_DIFY_TICKET_VERSION: str = Field(default="student-ticket-v1", min_length=1, max_length=64)
    # 不配置时使用学生档案的服务归属部门；任何非空ID仍须检查数据库。
    STUDENT_TICKET_DEPARTMENT_ID: int | None = Field(default=None, gt=0)
    STUDENT_TICKET_RESPONSE_HOURS: int = Field(default=24, ge=1, le=720)
    STUDENT_TICKET_RESOLUTION_HOURS: int = Field(default=72, ge=1, le=2160)


student_ticket_settings = StudentTicketSettings()
