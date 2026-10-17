"""公共模块的唯一配置入口。"""
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env.sample"), env_file_encoding="utf-8", extra="ignore")
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


settings = Settings()
LOG_DIR = Path(settings.LOG_DIR) if settings.LOG_DIR else BASE_DIR / "app" / "logs"
