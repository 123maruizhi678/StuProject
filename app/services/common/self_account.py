"""当前账号自助改密及学生联系方式；不接受客户端指定档案编号。"""
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import select, update
from app.config import settings
from app.models.common import student_profile
from app.models.common.user_account import UserAccount
from app.models.common._types import utc_now
from app.core.common.phone_protection import phone_fields
from app.services.common.auth_service import hash_password, verify_password


def change_password(db, account, payload):
    current = payload.current_password.get_secret_value()
    new = payload.new_password.get_secret_value()
    if not verify_password(current, account.password_hash):
        raise HTTPException(400, "原密码不正确。")
    if verify_password(new, account.password_hash):
        raise HTTPException(400, "新密码不能与原密码相同。")
    changed = db.execute(update(UserAccount).where(
        UserAccount.user_id == account.user_id, UserAccount.password_hash == account.password_hash
    ).values(password_hash=hash_password(new), updated_at=utc_now()),
        execution_options={"synchronize_session": False})
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "账号已更新，请重新登录后再试。")
    db.commit()
    return {"password_changed": True, "reauthenticate": True}


def student_contact(db, account):
    if account.identity_type != "student" or not account.student_id:
        raise HTTPException(403, "此联系方式入口仅供本人学生账号使用。")
    row = db.execute(select(student_profile).where(
        student_profile.c.student_id == account.student_id
    )).mappings().first()
    if not row:
        raise HTTPException(404, "学生档案不存在。")
    phone = None
    if row["phone_ciphertext"]:
        if not settings.ENTERPRISE_PHONE_ENCRYPTION_KEY:
            raise HTTPException(503, "手机号保护密钥未配置，请联系管理员。")
        try:
            phone = Fernet(settings.ENTERPRISE_PHONE_ENCRYPTION_KEY.encode()).decrypt(bytes(row["phone_ciphertext"])).decode()
        except (InvalidToken, ValueError, UnicodeError):
            raise HTTPException(503, "手机号暂时无法读取，请联系管理员。") from None
    return {"phone": phone, "row_version": row["row_version"]}


def update_student_contact(db, account, payload):
    student_contact(db, account)
    if not verify_password(payload.current_password.get_secret_value(), account.password_hash):
        raise HTTPException(400, "原密码不正确。")
    values = phone_fields(payload.phone)
    # 学生表沿用已有加密手机号列，不增加检索字段。
    changed = db.execute(update(student_profile).where(
        student_profile.c.student_id == account.student_id,
        student_profile.c.row_version == payload.expected_version
    ).values(phone_ciphertext=values["phone_ciphertext"],
        row_version=student_profile.c.row_version + 1, updated_at=utc_now()))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "个人资料已更新，请刷新后重试。")
    db.commit()
    return student_contact(db, account)
