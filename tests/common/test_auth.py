"""密码、JWT攻击面和真实身份回归。"""
import time
import jwt
from sqlalchemy import update
from sqlalchemy.orm import Session
from app.config import settings
from app.models.common import UserAccount, employee, org_department, student_profile
from app.services.common.auth_service import decode_access_token, verify_password, hash_password
from tests.common.support import AuthCase


class AuthTests(AuthCase):
    def test_login_and_access(self):
        result = self.client.post("/api/v1/auth/login",json={"username":"admin","password":"test-password-123"})
        self.assertEqual(result.status_code,200)
        data=result.json()["data"]
        self.assertEqual(data["expires_in"],7200)
        self.assertEqual(data["token_type"],"bearer")
        self.assertEqual(result.headers["cache-control"],"no-store")
        payload=jwt.decode(data["access_token"],settings.AUTH_SECRET_KEY,algorithms=["HS256"])
        self.assertEqual(set(payload),{"sub","iat","exp"})
        access=self.client.get("/api/v1/auth/me/access",headers={"Authorization":"Bearer "+data["access_token"]})
        self.assertEqual(access.json()["data"]["identity_type"],"admin")
        self.assertNotIn("password",access.text)
        self.assertNotIn("password_hash",access.text)

    def test_password_is_salted_and_not_plaintext(self):
        first=hash_password("same-password")
        second=hash_password("same-password")
        self.assertNotEqual(first,second)
        self.assertTrue(verify_password("same-password",first))
        self.assertFalse(verify_password("wrong",first))
        self.assertFalse(verify_password("same-password","same-password"))

    def test_invalid_credentials_are_indistinguishable(self):
        results=[self.client.post("/api/v1/auth/login",json={"username":u,"password":p})
                 for u,p in [("admin","bad"),("missing","bad"),("Admin","test-password-123")]]
        self.assertTrue(all(r.status_code==401 for r in results))
        self.assertTrue(all(r.json()==results[0].json() for r in results))
        self.assertEqual(results[0].headers["www-authenticate"],"Bearer")

    def test_invalid_request_never_echoes_secrets(self):
        for payload in [{"username":"admin","password":"sensitive-value","identity_type":"admin"},
                        {"username":" admin","password":"sensitive-value"},
                        {"username":"admin","password":12345678},
                        {"username":"","password":"sensitive-value"}]:
            with self.subTest(payload=payload.keys()):
                response=self.client.post("/api/v1/auth/login",json=payload)
                self.assertEqual(response.status_code,400)
                self.assertNotIn("sensitive-value",response.text)
                self.assertNotIn("12345678",response.text)

    def test_missing_malformed_or_wrong_scheme_token(self):
        for value in [None,"Bearer invalid","Basic abc","Bearer"]:
            with self.subTest(value=value):
                r=self.client.get("/api/v1/auth/me/access",headers={"Authorization":value} if value else {})
                self.assertEqual(r.status_code,401)
                self.assertEqual(r.json()["code"],401)

    def test_invalid_token_claims(self):
        now=int(time.time())
        valid={"sub":"1","iat":now,"exp":now+300}
        variants=[
            {k:v for k,v in valid.items() if k!=claim} for claim in ("sub","iat","exp")
        ]+[dict(valid,sub=value) for value in ["0","-1","1.0","01","abc",str(2**63),1,True]
        ]+[dict(valid,exp=now-1,iat=now-100),dict(valid,iat=now+100),
           dict(valid,exp=now,iat=now),dict(valid,iat=str(now)),dict(valid,exp=True)]
        for claims in variants:
            with self.subTest(claims=claims):
                token=jwt.encode(claims,settings.AUTH_SECRET_KEY,algorithm="HS256")
                self.assertIsNone(decode_access_token(token))
        for algorithm in ["HS384","HS512"]:
            token=jwt.encode(valid,settings.AUTH_SECRET_KEY,algorithm=algorithm)
            self.assertIsNone(decode_access_token(token))
        token=jwt.encode(valid,"wrong-secret-key-12345678901234567890",algorithm="HS256")
        self.assertIsNone(decode_access_token(token))

    def test_nonexistent_account_is_rejected(self):
        now=int(time.time())
        token=jwt.encode({"sub":"99999","iat":now,"exp":now+300},settings.AUTH_SECRET_KEY,algorithm="HS256")
        self.assertEqual(self.client.get("/api/v1/auth/me/access",headers={"Authorization":"Bearer "+token}).status_code,401)

    def test_claimed_roles_cannot_grant_permissions(self):
        now=int(time.time())
        token=jwt.encode({"sub":"120","iat":now,"exp":now+300,"role_codes":["manager"],"identity_type":"admin"},
                         settings.AUTH_SECRET_KEY,algorithm="HS256")
        response=self.client.get("/api/v1/auth/me/access",headers={"Authorization":"Bearer "+token})
        data=response.json()["data"]
        self.assertEqual(data["identity_type"],"employee")
        self.assertNotIn("report.read",data["permissions"])

    def test_same_token_observes_role_and_department_changes(self):
        headers=self.headers(120)
        def access(): return self.client.get("/api/v1/auth/me/access",headers=headers)
        self.assertNotIn("report.read",access().json()["data"]["permissions"])
        with Session(self.engine) as db:
            db.execute(update(employee).where(employee.c.employee_id==20).values(role_codes=["manager"]))
            db.commit()
        self.assertIn("report.read",access().json()["data"]["permissions"])
        with Session(self.engine) as db:
            db.execute(update(employee).where(employee.c.employee_id==20).values(role_codes=["employee"]))
            db.commit()
        self.assertNotIn("report.read",access().json()["data"]["permissions"])
        with Session(self.engine) as db:
            db.execute(update(org_department).values(status="disabled"))
            db.commit()
        self.assertEqual(access().status_code,403)

    def test_disabled_employee_unknown_role_and_archived_student(self):
        for values in [{"status":"disabled"},{"role_codes":["superuser"]}]:
            with Session(self.engine) as db:
                db.execute(update(employee).where(employee.c.employee_id==20).values(**values))
                db.commit()
            response=self.client.post("/api/v1/auth/login",json={"username":"employee20","password":"test-password-123"})
            self.assertEqual(response.status_code,401)
        headers=self.headers(2)
        with Session(self.engine) as db:
            db.execute(update(student_profile).values(is_archived=True))
            db.commit()
        self.assertEqual(self.client.get("/api/v1/auth/me/access",headers=headers).status_code,403)

    def test_permission_query_cannot_select_another_user(self):
        r=self.client.get("/api/v1/auth/me/access?user_id=1&identity_type=admin",headers=self.headers(2))
        self.assertEqual(r.json()["data"]["user_id"],2)
        self.assertEqual(r.json()["data"]["identity_type"],"student")
