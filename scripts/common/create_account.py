"""仅在受控终端开通账号；密码交互输入，不使用默认密码或公开注册。"""
import argparse
import getpass
import hashlib
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.database import SessionLocal, engine
from app.services.common.account_service import create_account
from app.services.common.auth_service import authenticate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--identity", choices=["admin", "employee", "customer", "student"], default="admin")
    parser.add_argument("--business-id", type=int)
    parser.add_argument("--bootstrap-admin", action="store_true")
    parser.add_argument("--operator", help="现有平台管理员用户名；首次初始化不填写")
    args = parser.parse_args()
    if args.bootstrap_admin and (args.identity != "admin" or args.operator or args.business_id is not None):
        parser.error("首次初始化仅创建无业务绑定的平台管理员")
    if not args.bootstrap_admin and not args.operator:
        parser.error("非首次初始化必须提供 --operator")
    if "actor_account_id" not in {c["name"] for c in inspect(engine).get_columns("operation_log")}:
        parser.error("请先执行 scripts/common/check_shared_schema.py --apply-account-audit")
    operator_password = getpass.getpass("现有平台管理员密码：") if args.operator else None
    password = getpass.getpass("新账号密码（至少8位）：")
    if password != getpass.getpass("再次输入新账号密码："):
        parser.error("两次密码不一致")
    # 同库所有受控开通共享命名锁，防止空库首次初始化并发。
    lock_key = "common-account:" + hashlib.sha256(settings.DB_NAME.encode()).hexdigest()[:40]
    with engine.connect() as connection:
        if connection.execute(text("SELECT GET_LOCK(:name, 10)"), {"name": lock_key}).scalar() != 1:
            raise ValueError("账号初始化繁忙，请稍后重试")
        connection.commit()
        try:
            with SessionLocal(bind=connection) as db, db.begin():
                actor = authenticate(db, args.operator, operator_password) if args.operator else None
                if args.operator and (actor is None or actor.identity_type != "admin"):
                    raise ValueError("管理员凭据无效")
                account = create_account(
                    db, username=args.username, password=password, identity_type=args.identity,
                    business_id=args.business_id, actor=actor, bootstrap=args.bootstrap_admin,
                )
                user_id = account.user_id
            print("账号已开通，user_id=" + str(user_id) + "；密码未写入日志")
        finally:
            connection.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_key})
            connection.commit()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, IntegrityError) as exc:
        print(str(exc) if isinstance(exc, ValueError) else "用户名或身份主档已绑定账号，事务已回滚", file=sys.stderr)
        raise SystemExit(1)
