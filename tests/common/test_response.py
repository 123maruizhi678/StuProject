"""公共响应的契约回归：使用虚构数据，不连接数据库或 Dify。"""

import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.common import response
from app.core.common.response import (
    BusinessException,
    ResponseModel,
    ResultCode,
    fail,
    register_exception_handlers,
    success,
)


class Payload(BaseModel):
    count: int


def make_app():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/api/v1/report/success", response_model=ResponseModel[dict])
    def successful_report():
        return success({"count": 3})

    @app.post("/api/v1/report/validate")
    def validate_report(payload: Payload):
        return success(payload.model_dump())

    @app.get("/api/v1/report/http-error/{status}")
    def report_http_error(status: int):
        raise HTTPException(status, "测试错误", headers={"X-Test-Header": "kept"})

    @app.get("/api/v1/report/business-error")
    def business_error():
        raise BusinessException("依赖未就绪", ResultCode.UNAVAILABLE, {"retry": False})

    @app.get("/api/v1/report/unexpected")
    def unexpected_error():
        raise RuntimeError("fake-internal-detail")

    @app.get("/api/v1/auth/unauthorized")
    @app.get("/api/v1/agent/unauthorized")
    def unauthorized():
        raise HTTPException(401, "未登录", headers={"WWW-Authenticate": "Bearer"})

    @app.post("/api/v1/auth/validate")
    def validate_auth(payload: Payload):
        return success(payload.model_dump())

    @app.get("/api/v1/enterprise/forbidden")
    def enterprise_forbidden():
        raise HTTPException(403, "无权限")

    return app


class ResponseContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(make_app(), raise_server_exceptions=False)
        self.addCleanup(self.client.close)

    def test_helpers_and_generic_model(self):
        self.assertEqual(success(), {"code": 0, "message": "success", "data": None})
        expected = {"code": 409, "message": "重复提交", "data": {"id": 7}}
        self.assertEqual(fail(409, "重复提交", {"id": 7}), expected)
        self.assertEqual(ResponseModel[dict](**expected).model_dump(), expected)

    def test_successful_report(self):
        result = self.client.get("/api/v1/report/success")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), success({"count": 3}))

    def test_report_validation_has_envelope_without_raw_input(self):
        result = self.client.post("/api/v1/report/validate", json={"count": "fake-sensitive-input"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["code"], 400)
        self.assertEqual(set(result.json()), {"code", "message", "data"})
        self.assertNotIn("fake-sensitive-input", result.text)

    def test_report_http_failures_are_business_codes_and_keep_headers(self):
        for status in (401, 403, 404, 409, 503):
            with self.subTest(status=status):
                result = self.client.get(f"/api/v1/report/http-error/{status}")
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json(), fail(status, "测试错误"))
                self.assertEqual(result.headers["X-Test-Header"], "kept")

    def test_business_exception_keeps_business_data(self):
        result = self.client.get("/api/v1/report/business-error")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), fail(503, "依赖未就绪", {"retry": False}))

    def test_unexpected_exception_hides_internal_details_in_response(self):
        with patch.object(response.logger, "exception") as log:
            result = self.client.get("/api/v1/report/unexpected")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), fail(500, "服务器内部错误"))
        self.assertNotIn("fake-internal-detail", result.text)
        log.assert_called_once()

    def test_auth_and_agent_keep_http_authentication_convention(self):
        for module in ("auth", "agent"):
            with self.subTest(module=module):
                result = self.client.get(f"/api/v1/{module}/unauthorized")
                self.assertEqual(result.status_code, 401)
                self.assertEqual(result.json(), {"detail": "未登录"})
                self.assertEqual(result.headers["WWW-Authenticate"], "Bearer")

    def test_auth_validation_keeps_framework_status(self):
        result = self.client.post("/api/v1/auth/validate", json={})
        self.assertEqual(result.status_code, 422)

    def test_enterprise_http_failure_has_envelope(self):
        result = self.client.get("/api/v1/enterprise/forbidden")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), fail(403, "无权限"))


if __name__ == "__main__":
    unittest.main()
