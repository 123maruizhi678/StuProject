"""统一账号查询，不缓存账号身份或权限。"""
from sqlalchemy import insert, select, update
from fastapi import HTTPException
from sqlalchemy.orm import Session
from hashlib import sha256
from uuid import uuid4
from app.models.common._types import utc_now

from app.models.common import UserAccount, customer_profile, employee, student_profile, operation_log
from app.core.common.system_admin import admin_actor, ensure_admin_actor

PROFILES = {
    "employee": (employee, "employee_id"),
    "student": (student_profile, "student_id"),
    "customer": (customer_profile, "customer_id"),
}


class AccountRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> UserAccount | None:
        return self.db.get(UserAccount, user_id, populate_existing=True)

    def get_by_username(self, username: str) -> UserAccount | None:
        return self.db.scalar(select(UserAccount).where(UserAccount.username == username))

    def display_name(self, account: UserAccount) -> str:
        """读取当前账号已有正式档案姓名；管理员复用既有员工操作档案。"""
        if account.identity_type == "admin":
            actor = admin_actor(self.db, account.user_id)
            return (actor["full_name"].strip() or account.username) if actor else account.username
        profile = PROFILES.get(account.identity_type)
        if profile:
            table, key = profile
            name = self.db.scalar(
                select(table.c.full_name).where(table.c[key] == getattr(account, key))
            )
            if name and name.strip():
                return name.strip()
        return account.username

    def update_full_name(self, account: UserAccount, name: str, expected_name: str) -> str:
        # 对象编号只来自已认证账号，不能由请求指定。正式档案沿用版本字段。
        self.db.execute(select(UserAccount.user_id).where(UserAccount.user_id == account.user_id).with_for_update()).one()
        if self.display_name(account) != expected_name:
            raise HTTPException(status_code=409, detail="姓名已更新，请刷新页面后重试。")
        if account.identity_type == "admin":
            table, key = employee, "employee_id"
            had_admin_profile = admin_actor(self.db, account.user_id) is not None
            object_id = ensure_admin_actor(self.db, account)[key]
        else:
            table, key = PROFILES[account.identity_type]
            object_id = getattr(account, key)
        row = self.db.execute(select(table).where(table.c[key] == object_id).with_for_update()).mappings().one()
        if account.identity_type == "customer" and row["authority_source"] != "local":
            raise HTTPException(status_code=409, detail="该姓名由外部权威档案维护，请联系管理员更新。")
        if (account.identity_type != "admin" or had_admin_profile) and (row["full_name"].strip() or account.username) != expected_name:
            raise HTTPException(status_code=409, detail="姓名已更新，请刷新页面后重试。")
        result = self.db.execute(update(table).where(table.c[key] == object_id, table.c.row_version == row["row_version"]).values(
            full_name=name, row_version=row["row_version"] + 1, updated_at=utc_now()))
        if result.rowcount != 1:
            raise HTTPException(status_code=409, detail="档案已更新，请刷新页面后重试。")
        request_key = uuid4().hex
        self.db.execute(insert(operation_log).values(
            operation_key=sha256(request_key.encode()).hexdigest(), service_code="auth.self_profile",
            action_code="auth.profile.rename", entity_type=table.name, entity_id=object_id,
            request_key=request_key, parameters_hash=sha256(name.encode()).hexdigest(),
            before_data={"user_id": account.user_id, "full_name": row["full_name"], "row_version": row["row_version"]},
            after_data={"user_id": account.user_id, "full_name": name, "row_version": row["row_version"] + 1},
            change_reason="用户在个人中心修改本人正式姓名", operation_status="succeeded", finished_at=utc_now(),
        ))
        self.db.commit()
        return name
