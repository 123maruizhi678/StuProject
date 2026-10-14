"""建表脚本：依据 ORM 模型在数据库中创建所有表。

用法：
    cd D:\AI\StuProject
    D:\anaconda3\envs\SST\python.exe scripts/init_db.py

说明：
    - 复用 app.database 的 engine 与 Base
    - 自动导入 app/models 下的所有模型模块并建表
    - 仅创建不存在的表，不会改动已有表结构
    - 连接参数来自项目根目录 .env（DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME）
    - 需要已安装 pymysql（环境已具备）
"""
import importlib
import pkgutil
import sys
from pathlib import Path

# 将项目根目录加入 sys.path，支持以脚本方式直接运行
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database import Base, engine  # noqa: E402


def _import_all_models() -> None:
    """导入 app.models 包及其下所有模型模块，确保注册到 Base.metadata。"""
    import app.models  # noqa: F401
    for mod in pkgutil.iter_modules(app.models.__path__):
        importlib.import_module(f"app.models.{mod.name}")


def main() -> None:
    _import_all_models()

    if not Base.metadata.tables:
        print("未发现任何模型（app/models 下为空），无需建表。")
        return

    Base.metadata.create_all(bind=engine)
    print(f"建表完成，共创建 {len(Base.metadata.tables)} 张表：")
    for name in Base.metadata.tables.keys():
        print(f"  - {name}")


if __name__ == "__main__":
    main()
