"""受控开通、真实操作者审计、无公开注册与事务回滚。"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.common import UserAccount, operation_log
from app.services.common.account_service import create_account
from app.services.common.auth_service import verify_password
from tests.common.support import AuthCase


class AccountTests(AuthCase):
    def test_platform_admin_can_create_and_audit_account(self):
        with Session(self.engine) as db, db.begin():
            account=create_account(db,username="another-admin",password="new-password-123",identity_type="admin",
                                   actor=db.get(UserAccount,1))
            user_id=account.user_id
        with Session(self.engine) as db:
            account=db.get(UserAccount,user_id)
            self.assertTrue(verify_password("new-password-123",account.password_hash))
            audit=db.execute(select(operation_log)).mappings().one()
            self.assertEqual(audit["actor_account_id"],1)
            self.assertIsNone(audit["service_code"])
            self.assertEqual(audit["entity_id"],user_id)
            self.assertNotIn("password",str(audit["after_data"]))

    def test_audit_and_account_rollback_together(self):
        with Session(self.engine) as db:
            try:
                with db.begin():
                    create_account(db,username="rollback-admin",password="new-password-123",identity_type="admin",
                                   actor=db.get(UserAccount,1))
                    raise RuntimeError("simulate commit failure")
            except RuntimeError:
                pass
        with Session(self.engine) as db:
            self.assertIsNone(db.scalar(select(UserAccount).where(UserAccount.username=="rollback-admin")))
            self.assertEqual(db.scalar(select(func.count()).select_from(operation_log)),0)

    def test_employee_admin_cannot_open_accounts(self):
        with Session(self.engine) as db, db.begin():
            with self.assertRaises(ValueError):
                create_account(db,username="forbidden-admin",password="new-password-123",identity_type="admin",
                               actor=db.get(UserAccount,122))

    def test_bootstrap_refuses_nonempty_database(self):
        with Session(self.engine) as db, db.begin():
            with self.assertRaises(ValueError):
                create_account(db,username="bootstrap",password="new-password-123",identity_type="admin",bootstrap=True)

    def test_bootstrap_empty_database_has_real_self_actor(self):
        from sqlalchemy import delete
        with Session(self.engine) as db, db.begin():
            db.execute(delete(UserAccount))
            account=create_account(db,username="first-admin",password="new-password-123",identity_type="admin",bootstrap=True)
            audit=db.execute(select(operation_log)).mappings().one()
            self.assertEqual(audit["actor_account_id"],account.user_id)
            self.assertEqual(audit["action_code"],"auth.account.bootstrap")

    def test_missing_master_and_duplicate_name_are_rejected(self):
        with Session(self.engine) as db, db.begin():
            for kwargs in [
                {"username":"admin","identity_type":"admin"},
                {"username":"no-master","identity_type":"student","business_id":999},
                {"username":"no-link","identity_type":"employee"},
                {"username":"fake-service","identity_type":"service"},
            ]:
                with self.assertRaises(ValueError):
                    create_account(db,password="new-password-123",actor=db.get(UserAccount,1),**kwargs)

    def test_no_public_registration_endpoint(self):
        self.assertEqual(self.client.post("/api/v1/auth/register",json={}).status_code,404)
