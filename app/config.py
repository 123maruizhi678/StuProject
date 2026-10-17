"""应用配置：从 .env.sample 默认值和系统环境变量读取日志、数据库和各业务 Dify 应用设置。"""

from pathlib import Path

from typing import Literal
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录；公共模板提供默认值，同名系统环境变量优先。
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env.sample"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 学生统一应用：真实密钥仅通过系统环境变量注入。
    STUDENT_DIFY_KEY: SecretStr = Field(default=SecretStr(''), repr=False)
    STUDENT_TOKEN_ISSUER: str = 'stuproject'
    STUDENT_ACTION_TTL_SECONDS: int = Field(default=300, ge=300, le=300)
    STUDENT_ANALYSIS_VERSION: str = 'student-assistant-v1'
    STUDENT_HTTP_TIMEOUT: float = Field(default=30, gt=0, le=120)
    STUDENT_QUERY_BACKEND: Literal['local','group'] = 'local'
    STUDENT_NL2SQL_URL: str = ''
    STUDENT_NL2SQL_TOKEN: str = Field(default='', repr=False)
    STUDENT_EDUCATION_URL: str = ''
    STUDENT_EDUCATION_TOKEN: str = Field(default='', repr=False)
    STUDENT_CRM_URL: str = ''
    STUDENT_CRM_TOKEN: str = Field(default='', repr=False)
    STUDENT_SYNC_TOKEN: SecretStr = Field(default=SecretStr(''), repr=False)
    STUDENT_NOTIFICATION_MAX_ATTEMPTS: int = Field(default=5, ge=1, le=20)
    STUDENT_NOTIFICATION_LEASE_SECONDS: int = Field(default=60, ge=60, le=60)
    STUDENT_NOTIFICATION_URL: str = ''
    STUDENT_NOTIFICATION_TOKEN: str = Field(default='', repr=False)
    STUDENT_SYNC_INTERVAL_SECONDS: int = Field(default=300, ge=30)
    STUDENT_KNOWLEDGE_FILE: Path = BASE_DIR / 'dify/student/knowledge.json'
    STUDENT_ACTION_SECRET: str = Field(default="", repr=False)
    STUDENT_SYNC_ENABLED: bool = False
    STUDENT_SYNC_ALLOWED_SOURCES: list[str] = []
    STUDENT_SYNC_ALLOWED_STUDENT_IDS: list[int] = []
    STUDENT_COURSES_FILE: Path = BASE_DIR / "app" / "student_courses.json"
    STUDENT_LEAVE_ASSIGNMENT_SCOPES: dict[int, list[int]] = {}
    STUDENT_WARNING_ASSIGNER_IDS: list[int] = []
    STUDENT_WARNING_ASSIGNMENT_SCOPES: dict[int, list[int]] = {}

    @field_validator('STUDENT_COURSES_FILE','STUDENT_KNOWLEDGE_FILE')
    @classmethod
    def student_paths(cls,value):
        return value if value.is_absolute() else BASE_DIR/value

    # 日志
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = ""
    # DB_* 字段共同指定 MySQL 连接目标和认证信息。
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = Field(default="", repr=False)
    DB_NAME: str = "education_agent"
    DB_ECHO: bool = False
    # Dify API 地址；同一 Dify 服务下各应用可分别使用独立 API Key。
    DIFY_API_BASE: str = "http://127.0.0.1/v1"
    # 旧版 NL2SQL 通用密钥保留为兼容回退；新配置建议使用按场景密钥。
    DIFY_API_KEY: str = Field(default="", repr=False)
    DIFY_SQL_OUTPUT_KEY: str = "sql"
    # Dify HTTP 请求超时秒数（NL2SQL / 报告工作流共用）。
    DIFY_API_TIMEOUT_SECONDS: float = 60.0
    # 报告生成工作流专用配置；地址为空时回退 DIFY_API_BASE。
    REPORT_DIFY_API_BASE: str = ""
    REPORT_DIFY_API_KEY: str = Field(default="", repr=False)
    REPORT_DIFY_OUTPUT_KEY: str = "report_text"
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
    """学生请假 Workflow 的专用连接配置，保留旧字段兼容，真实值仅通过系统环境变量注入。"""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env.sample"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    STUDENT_DIFY_LEAVE_KEY: SecretStr = Field(default=SecretStr(""), repr=False)
    STUDENT_DIFY_LEAVE_TIMEOUT: float = 60.0
    STUDENT_DIFY_LEAVE_VERSION: str = "student-leave-v1"


student_leave_dify_settings = StudentLeaveDifySettings()

settings = Settings()
LOG_DIR = Path(settings.LOG_DIR) if settings.LOG_DIR else (BASE_DIR / "app" / "logs")
