"""公共HTTP状态与业务信封边界、敏感信息保护。"""
import logging
import unittest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from app.core.common.logger import RedactingFormatter
from app.core.common.response import BusinessException, register_exception_handlers


class ResponseTests(unittest.TestCase):
    def setUp(self):
        self.app=FastAPI()
        register_exception_handlers(self.app)
        for prefix in ["/api/v1/auth","/api/v1/student","/api/v1/internal/student","/api/v1/enterprise","/api/v1/report"]:
            def denied():
                raise HTTPException(401,"unauthorized",headers={"WWW-Authenticate":"Bearer"})
            self.app.add_api_route(prefix+"/denied",denied)
        @self.app.get("/api/v1/auth/database-error")
        def db_error():
            raise OperationalError("sensitive SQL",{"password":"secret-db-value"},Exception("db-secret"))
        @self.app.get("/api/v1/auth/internal-error")
        def internal_error():
            raise RuntimeError("secret-internal-value")
        @self.app.get("/api/v1/auth/unavailable")
        def unavailable():
            raise BusinessException("登录服务暂不可用",503)
        @self.app.get("/api/v1/enterpriseX/denied")
        def other_prefix():
            raise HTTPException(403,"forbidden")
        self.client=TestClient(self.app,raise_server_exceptions=False)

    def tearDown(self):
        self.client.close()

    def test_public_login_keeps_actual_http_status(self):
        r=self.client.get("/api/v1/auth/denied")
        self.assertEqual(r.status_code,401)
        self.assertEqual(r.json(),{"code":401,"message":"unauthorized","data":None})
        self.assertEqual(r.headers["www-authenticate"],"Bearer")

    def test_business_paths_use_application_envelope(self):
        for prefix in ["/api/v1/student","/api/v1/internal/student","/api/v1/enterprise","/api/v1/report"]:
            r=self.client.get(prefix+"/denied")
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json()["code"],401)
        self.assertEqual(self.client.get("/api/v1/enterpriseX/denied").status_code,403)

    def test_unavailable_dependencies_and_errors_are_sanitized(self):
        for path,status in [("database-error",503),("internal-error",500),("unavailable",503)]:
            r=self.client.get("/api/v1/auth/"+path)
            self.assertEqual(r.status_code,status)
            self.assertNotIn("secret",r.text)
            self.assertEqual(set(r.json()),{"code","message","data"})

    def test_log_formatter_redacts_credentials(self):
        formatter=RedactingFormatter("%(message)s")
        record=logging.LogRecord("app.test",logging.INFO,"test",1,
                                 "credentials=%s Bearer abc.def.ghi",
                                 ({"password":"plain-password","api_key":"app-secret","user_id":7},),None)
        output=formatter.format(record)
        for secret in ["plain-password","app-secret","abc.def.ghi"]:
            self.assertNotIn(secret,output)
        self.assertIn("7",output)
