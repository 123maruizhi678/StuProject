"""抽取信任边界及故障回退：使用真实 HTTP 传输类和可控响应。"""
import json
from pathlib import Path

import httpx
import pytest
import yaml
from pydantic import SecretStr, ValidationError

from app.clients.customer.extract_dify import ExtractDifyClient
from app.config import settings
from app.core.common.dify import DifyHttpClient
from app.schemas.customer.extraction import CustomerExtractFields, FIELD_SCHEMA
from app.services.customer.extractor import ExtractorService


def result(fields, version="v1", status="succeeded"):
    return {"data": {"status": status, "outputs": {"fields": fields, "contract_version": version}}}


def client_for(monkeypatch, body=None, status=200, timeout=False):
    monkeypatch.setattr(settings, "CUSTOMER_EXTRACT_DIFY_API_KEY", SecretStr("app-test"))
    calls = []
    def respond(request):
        calls.append(request)
        if timeout:
            raise httpx.ReadTimeout("test", request=request)
        return httpx.Response(status, json=body)
    http = DifyHttpClient("http://dify.invalid/v1", transport=httpx.MockTransport(respond))
    return ExtractDifyClient(http), calls


def test_request_contract_and_deterministic_precedence(monkeypatch):
    client, calls = client_for(monkeypatch, result({"full_name": "张三", "age": 99, "phone": "13900139000"}))
    fields = ExtractorService(client).extract("张三，35岁，电话+86 138-0013-8000，邮箱test@example.com")
    assert fields == {"full_name": "张三", "age": 35, "phone": "13800138000", "contact_email": "test@example.com"}
    request = calls[0]
    assert request.url.path == "/v1/workflows/run"
    assert request.headers["Authorization"] == "Bearer app-test"
    payload = json.loads(request.content)
    assert payload["response_mode"] == "blocking"
    assert json.loads(payload["inputs"]["field_schema"]) == FIELD_SCHEMA
    assert payload["inputs"]["contract_version"] == "v1"


@pytest.mark.parametrize("body", [
    result({"age": True}), result({"age": "35"}), result({"age": 121}),
    result({"work_years": -1}), result({"work_years": 2.5}),
    result({"matched": True}), result({"customer_id": 1}), result({"city": ["北京"]}),
    result({"phone": "123"}), result({"gender": "未知"}), result({"contact_email": "bad"}),
    result([]), result("not-json"), result({"age": 30}, version="v2"),
    result({"age": 30}, status="failed"), {"data": {"status": "running"}},
    {"data": {"status": "succeeded", "outputs": {"fields": {"age": 30}}}},
    {"data": []}, {"data": {"status": "succeeded", "outputs": []}},
])
def test_invalid_model_output_falls_back(monkeypatch, body):
    client, calls = client_for(monkeypatch, body)
    assert ExtractorService(client).extract("年龄30，13800138000") == {"age": 30, "phone": "13800138000"}
    assert len(calls) == 1


@pytest.mark.parametrize("status,timeout", [(401, False), (429, False), (500, False), (200, True)])
def test_transport_failure_does_not_retry(monkeypatch, status, timeout):
    client, calls = client_for(monkeypatch, {}, status=status, timeout=timeout)
    assert ExtractorService(client).extract("年龄30") == {"age": 30}
    assert len(calls) == 1


def test_no_key_does_not_call_model(monkeypatch):
    client, calls = client_for(monkeypatch, {})
    monkeypatch.setattr(settings, "CUSTOMER_EXTRACT_DIFY_API_KEY", SecretStr(""))
    assert ExtractorService(client).extract("年龄40") == {"age": 40}
    assert not calls


def test_json_string_and_null_fields(monkeypatch):
    client, _ = client_for(monkeypatch, result('{"full_name":"张三","age":null}'))
    assert client.extract_fields("姓名张三") == {"full_name": "张三"}


def test_contract_and_size_rejected_before_http(monkeypatch):
    client, calls = client_for(monkeypatch, {})
    for args in [("text", {"role": "admin"}, "v1"), ("text", FIELD_SCHEMA, "v2"), ("中" * 35000, FIELD_SCHEMA, "v1")]:
        with pytest.raises(ValueError):
            client.extract_fields(*args)
    assert not calls


def test_excel_values_and_whitelist():
    out = ExtractorService().coerce({"age": True, "work_years": "5", "city": ["北京"], "full_name": " 张三 ", "matched": True})
    assert out == {"work_years": 5, "full_name": "张三"}


def test_multiple_customers_are_not_merged(monkeypatch):
    client, _ = client_for(monkeypatch, result({"full_name": "张甲"}))
    assert ExtractorService(client).extract("客户一：张甲，年龄30；客户二：李乙，年龄40") == {}


def test_dify_parser_matches_backend_validation():
    document = yaml.safe_load((Path(__file__).resolve().parents[2] / "dify/customer/customer-extract.yml").read_text(encoding="utf-8"))
    data = next(n["data"] for n in document["workflow"]["graph"]["nodes"] if n["id"] == "code")
    namespace = {}
    exec(data["code"], namespace)
    assert namespace["main"]('```json\n{"age":30}\n```') == {"fields": {"age": 30}, "contract_version": "v1"}
    assert namespace["main"]('<think>reasoning</think>{"city":"北京"}')["fields"] == {"city": "北京"}
    for fields in [{"age": True}, {"matched": True}, {"phone": "123"}, {"age": "30"}, {"work_years": 81}]:
        with pytest.raises(ValueError):
            namespace["main"](json.dumps(fields))
        with pytest.raises(ValidationError):
            CustomerExtractFields.model_validate(fields)
    with pytest.raises(ValueError):
        namespace["main"]("invalid JSON")


def test_input_node_rejects_changed_schema():
    document = yaml.safe_load((Path(__file__).resolve().parents[2] / "dify/customer/customer-extract.yml").read_text(encoding="utf-8"))
    data = next(n["data"] for n in document["workflow"]["graph"]["nodes"] if n["id"] == "validate")
    namespace = {}
    exec(data["code"], namespace)
    assert namespace["main"]("客户资料", json.dumps(FIELD_SCHEMA), "v1")["text"] == "客户资料"
    with pytest.raises(ValueError):
        namespace["main"]("客户资料", '{"role":"admin"}', "v1")
