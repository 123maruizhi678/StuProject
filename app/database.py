"""数据库连接统一入口与生命周期管理器。

集中配置：
    - Base              所有 ORM 模型的声明基类
    - engine            本地 MySQL 同步引擎（pymysql 驱动）
    - SessionLocal      会话工厂
    - get_db            FastAPI 依赖（请求级会话，自动回滚/关闭）
    - dispose_db        应用关闭时释放连接池

注意：pymysql 为同步驱动，因此本模块使用同步引擎与会话。
建表由独立的迁移/初始化脚本负责，本模块不自动建表。
连接参数来自 .env（DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / DB_ECHO）。
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的声明基类。"""


# 本地 MySQL 连接串（pymysql 同步驱动，charset 统一 utf8mb4）
DATABASE_URL = URL.create("mysql+pymysql", username=settings.DB_USER, password=settings.DB_PASSWORD,
    host=settings.DB_HOST, port=settings.DB_PORT, database=settings.DB_NAME, query={"charset": "utf8mb4"})

# 同步引擎：连接池 + 健康检查，避免失效连接
engine = create_engine(
    DATABASE_URL,
    echo=settings.DB_ECHO,
    hide_parameters=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={"init_command": "SET time_zone = '+00:00'"},
)

# 会话工厂
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求一个会话，异常时回滚并关闭。"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def dispose_db() -> None:
    """应用关闭时释放引擎连接池。"""
    engine.dispose()
