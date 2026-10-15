"""应用配置：从项目根目录 .env 读取日志、数据库和各业务 Dify 应用设置。"""

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
    # Dify API 地址；同一 Dify 服务下各应用可分别使用独立 API Key。
    DIFY_API_BASE: str = "http://127.0.0.1/v1"
    # 旧版 NL2SQL 通用密钥保留为兼容回退；新配置建议使用按场景密钥。
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



class StudentLeaveDifySettings(BaseSettings):
    """学生请假 Workflow 的专用连接配置，使用独立 API Key 和版本标识。"""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    STUDENT_DIFY_LEAVE_KEY: SecretStr = Field(default=SecretStr(""), repr=False)
    STUDENT_DIFY_LEAVE_TIMEOUT: float = 60.0
    STUDENT_DIFY_LEAVE_VERSION: str = "student-leave-v1"


student_leave_dify_settings = StudentLeaveDifySettings()

settings = Settings()
LOG_DIR = Path(settings.LOG_DIR) if settings.LOG_DIR else (BASE_DIR / "app" / "logs")
