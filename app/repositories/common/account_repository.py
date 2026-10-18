"""统一账号查询，不缓存账号身份或权限。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.common import UserAccount


class AccountRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> UserAccount | None:
        return self.db.get(UserAccount, user_id, populate_existing=True)

    def get_by_username(self, username: str) -> UserAccount | None:
        return self.db.scalar(select(UserAccount).where(UserAccount.username == username))
