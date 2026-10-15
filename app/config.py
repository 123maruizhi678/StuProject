"""应用配置：从项目根目录 .env 读取日志、数据库和各业务 Dify 应用设置。"""

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
    # Dify API 地址；同一 Dify 服务下各应用可分别使用独立 API Key。
    DIFY_API_BASE: str = "http://127.0.0.1/v1"
    # 旧版 NL2SQL 通用密钥保留为兼容回退；新配置建议使用按场景密钥。
    DIFY_API_KEY: str = Field(default="", repr=False)
    DIFY_API_TIMEOUT_SECONDS: float = 60.0
    # NL2SQL Workflow
    DIFY_NL2SQL_API_KEY: str = Field(default="", repr=False)
    DIFY_NL2SQL_OUTPUT_KEY: str = ""
    # 客户研判 Workflow
    DIFY_CUSTOMER_API_KEY: str = Field(default="", repr=False)
    DIFY_CUSTOMER_OUTPUT_KEY: str = "result"
    # 报告摘要 Workflow
    DIFY_REPORT_API_KEY: str = Field(default="", repr=False)
    DIFY_REPORT_OUTPUT_KEY: str = "summary"
    # 对话型 Dify 应用
    DIFY_CHAT_API_KEY: str = Field(default="", repr=False)


settings = Settings()
LOG_DIR = Path(settings.LOG_DIR) if settings.LOG_DIR else (BASE_DIR / "app" / "logs")
