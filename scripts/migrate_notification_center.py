"""显式增量迁移：仅创建公共公告与已读记录，不修改已有表或业务数据。"""
from sqlalchemy import inspect
from app.database import engine
from app.models.common import platform_announcement, platform_notification_read


def main():
    if not inspect(engine).has_table("user_account"):
        raise RuntimeError("请先初始化项目的统一账号表")
    for table in (platform_announcement, platform_notification_read):
        table.create(engine, checkfirst=True)
        print(f"Ready: {table.name}")


if __name__ == "__main__":
    main()
