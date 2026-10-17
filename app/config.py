"""应用配置：从项目根目录 .env 读取日志、数据库和各业务 Dify 应用设置。"""

from pathlib import Path

from typing import Literal
from pydantic import Field, SecretStr
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
    # Dify HTTP 请求超时秒数（客服 / NL2SQL / 报告工作流共用）。
    DIFY_API_TIMEOUT_SECONDS: float = 60.0
    # 客户研判独立字段抽取 Workflow；空密钥保留确定性解析能力。
    CUSTOMER_EXTRACT_DIFY_API_KEY: SecretStr = Field(default=SecretStr(""), repr=False)
    CUSTOMER_EXTRACT_DIFY_API_BASE: str = ""
    CUSTOMER_EXTRACT_DIFY_APP_ID: str = ""
    CUSTOMER_EXTRACT_DIFY_TIMEOUT_SECONDS: float = Field(default=60.0, gt=0, le=300)
    # 客服独立应用；real 模式不自动回退为 mock。
    DIFY_CLIENT: Literal["mock", "real"] = "mock"
    DIFY_AGENT_API_KEY: SecretStr = Field(default=SecretStr(""), repr=False)
    # 学生统一 Workflow 应用密钥，从 .env 或同名系统环境变量读取。
    STUDENT_DIFY_KEY: SecretStr = Field(default=SecretStr(""), repr=False)
    # 学生会话及办理确认凭证使用独立签名密钥。
    STUDENT_ACTION_SECRET: str = Field(default="", repr=False)
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

    # Enterprise module configuration; uses the sole root .env.
    ENTERPRISE_EXTRACT_DIFY_API_KEY: str = Field(default="", repr=False)
    ENTERPRISE_NL2SQL_DIFY_API_KEY: str = Field(default="", repr=False)
    ENTERPRISE_KNOWLEDGE_DIFY_API_KEY: str = Field(default="", repr=False)
    ENTERPRISE_SUMMARY_DIFY_API_KEY: str = Field(default="", repr=False)
    ENTERPRISE_DIFY_CONTRACT_VERSION: str = "enterprise-v1"
    ENTERPRISE_CONFIRM_SECRET: str = Field(default="", repr=False)
    ENTERPRISE_PHONE_ENCRYPTION_KEY: str = Field(default="", repr=False)
    ENTERPRISE_PHONE_LOOKUP_SECRET: str = Field(default="", repr=False)
    ENTERPRISE_READ_DB_USER: str = ""
    ENTERPRISE_READ_DB_PASSWORD: str = Field(default="", repr=False)
    ENTERPRISE_QUERY_TIMEOUT_MS: int = Field(default=3000, ge=100, le=10000)
    ASR_MODEL_PATH: str = ""
    ASR_BACKEND: Literal['faster_whisper'] = 'faster_whisper'
    ASR_MODEL_SIZE: str = "small"
    ASR_DEVICE: str = "cpu"
    ASR_COMPUTE_TYPE: str = "int8"
    ENTERPRISE_TASK_INTERVAL_SECONDS: int = Field(default=300,ge=1,le=3600)



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
