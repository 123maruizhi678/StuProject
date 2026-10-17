"""公共模块的唯一配置入口。"""
from pathlib import Path
from typing import Literal
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env.sample"), env_file_encoding="utf-8", extra="ignore")
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
    STUDENT_COURSES_FILE: Path = BASE_DIR / "scripts" / "student" / "student_courses.json"
    STUDENT_LEAVE_ASSIGNMENT_SCOPES: dict[int, list[int]] = {}
    STUDENT_WARNING_ASSIGNER_IDS: list[int] = []
    STUDENT_WARNING_ASSIGNMENT_SCOPES: dict[int, list[int]] = {}

    @field_validator('STUDENT_COURSES_FILE','STUDENT_KNOWLEDGE_FILE')
    @classmethod
    def student_paths(cls,value):
        return value if value.is_absolute() else BASE_DIR/value


    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = Field(default=3306, ge=1, le=65535)
    DB_USER: str = "root"
    DB_PASSWORD: str = Field(default="", repr=False)
    DB_NAME: str = "education_agent"
    DB_ECHO: bool = False
    AUTH_SECRET_KEY: str = Field(default="", repr=False)
    AUTH_TOKEN_EXPIRE_MINUTES: int = Field(default=120, ge=1)
    ACCESS_CONTROL_FILE: Path = BASE_DIR / "app" / "access_control.yaml"
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = ""
    CORS_ORIGINS: list[str] = []
    DIFY_API_BASE: str = "http://127.0.0.1/v1"
    DIFY_API_TIMEOUT_SECONDS: float = Field(default=60, gt=0)

    @field_validator("ACCESS_CONTROL_FILE")
    @classmethod
    def resolve_policy(cls, value: Path) -> Path:
        return value if value.is_absolute() else BASE_DIR / value


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
LOG_DIR = Path(settings.LOG_DIR) if settings.LOG_DIR else BASE_DIR / "app" / "logs"
