"""配置管理：读取项目根目录 .env，环境变量可覆盖同名默认值。

当前 Settings 字段：LOG_LEVEL（日志等级，默认 INFO）、LOG_DIR（日志目录，留空时使用 app/logs）、DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME（MySQL 连接参数）、DB_ECHO（SQL 调试回显）、DIFY_API_BASE/DIFY_API_KEY/DIFY_SQL_OUTPUT_KEY（Dify NL2SQL 地址、凭据和 SQL 输出变量名）。未声明的 .env 字段会被忽略；密码和 API Key 在对象表示中隐藏。"""

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

    # 日志：LOG_LEVEL 指定等级（如 INFO），LOG_DIR 留空时采用 app/logs。
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = ""
    # DB_* 字段共同指定 MySQL 主机、端口、账号、密码、库名及 SQL 回显选项。
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = Field(default="12345", repr=False)
    DB_NAME: str = "education_agent"
    DB_ECHO: bool = False
    # Dify NL2SQL API 地址、访问密钥和工作流 SQL 输出字段名。
    DIFY_API_BASE: str = "http://127.0.0.1/v1"
    DIFY_API_KEY: str = Field(default="", repr=False)
    DIFY_SQL_OUTPUT_KEY: str = "sql"


settings = Settings()
LOG_DIR = Path(settings.LOG_DIR) if settings.LOG_DIR else (BASE_DIR / "app" / "logs")
