"""受控账号开通：关联真实主档，账号与审计在同一事务写入。"""
import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.models.common import UserAccount, operation_log
from app.repositories.common.account_repository import resolve_context
from app.schemas.common.auth import LoginRequest
from app.services.common.auth_service import hash_password


def create_account(db: Session, *, username: str, password: str, identity_type: str,
                   business_id: int | None = None, actor: UserAccount | None = None,
                   bootstrap: bool = False) -> UserAccount:
    LoginRequest(username=username, password=password)
    if len(password) < 8:
        raise ValueError("新账号密码至少需要 8 个字符")
    if identity_type not in {"admin", "employee", "customer", "student"}:
        raise ValueError("不支持的账号身份")
    if (identity_type == "admin") != (business_id is None):
        raise ValueError("平台管理员不绑定业务主键；其他身份必须关联已有真实主档")
    if business_id is not None and (type(business_id) is not int or not 0 < business_id < 2**63):
        raise ValueError("业务主键必须是有效正 BIGINT")
    if bootstrap:
        if actor is not None or identity_type != "admin" or db.scalar(select(func.count()).select_from(UserAccount)):
            raise ValueError("首次初始化仅适用于完全没有账号的数据库")
    elif actor is None or actor.identity_type != "admin" or resolve_context(db, actor) is None:
        raise ValueError("只有经认证的平台管理员可以开通账号")
    if db.scalar(select(UserAccount.user_id).where(UserAccount.username == username)):
        raise ValueError("用户名已存在")
    links = {key + "_id": business_id if identity_type == key else None
             for key in ("employee", "customer", "student")}
    account = UserAccount(username=username, password_hash=hash_password(password),
                          identity_type=identity_type, **links)
    if identity_type != "admin":
        # 校验还未落库的新账号所关联主档，不创建或猜测员工/学生资料。
        context = resolve_context(db, account)
        if context is None:
            raise ValueError("关联主档不存在、已停用、已归档或员工部门/角色不可用")
    db.add(account)
    db.flush()
    actor_id = account.user_id if bootstrap else actor.user_id
    request_key = uuid4().hex
    snapshot = {"user_id": account.user_id, "identity_type": identity_type, **links}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.execute(insert(operation_log).values(
        operation_key=hashlib.sha256((str(actor_id) + ":auth.account.create:" + request_key).encode()).hexdigest(),
        actor_account_id=actor_id, action_code="auth.account.bootstrap" if bootstrap else "auth.account.create",
        entity_type="user_account", entity_id=account.user_id, request_key=request_key,
        parameters_hash=hashlib.sha256(str(sorted(snapshot.items())).encode()).hexdigest(),
        after_data=snapshot, operation_status="succeeded",
        result_reference={"user_id": account.user_id}, row_version=1,
        created_at=now, updated_at=now, finished_at=now,
    ))
    return account
