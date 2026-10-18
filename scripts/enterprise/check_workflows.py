"""使用非个人样例实测统一应用的五条路径，校验全部命中同一发布版本。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.clients.enterprise.enterprise_dify import EnterpriseDifyClient
from app.config import settings
from app.core.common.dify import DifyHttpClient
from app.core.enterprise.enterprise_sql_guard import validate_query


class RecordingTransport(DifyHttpClient):
    def post_json_sync(self, *args, **kwargs):
        self.response = super().post_json_sync(*args, **kwargs)
        return self.response


def main():
    transport = RecordingTransport(settings.ENTERPRISE_DIFY_API_BASE or settings.DIFY_API_BASE, settings.DIFY_API_TIMEOUT_SECONDS)
    client = EnterpriseDifyClient(transport)
    cases = {
        "extract": {"text": "提交今天的日报，完成本地测试。", "action_catalog": ["daily.create"],
            "field_schema": {"daily.create": {"report_date": "YYYY-MM-DD", "submitted_content": "string"}},
            "context": {"today": "2026-10-17"}, "contract_version": "enterprise-v1"},
        "query": {"question": "有多少客户？", "schema_context": {"customers": ["customer_id", "status"]},
            "dialect": "mysql", "query_constraints": {"max_rows": 100}, "bound_filters": {},
            "schema_version": "enterprise-query-v1", "contract_version": "enterprise-v1"},
        "knowledge.qa": {"question": "测试制度规定的签到时间？", "mode": "qa",
            "candidates": [{"id": 1, "version": 1, "title": "仅测试制度", "content": "测试制度：签到时间为上午九点。"}],
            "contract_version": "enterprise-v1"},
        "knowledge.rag": {"question": "测试文档规定的签到时间？", "mode": "rag",
            "candidates": [{"id": 1, "version": 1, "title": "仅测试文档", "content": "测试文档：签到时间为上午九点。"}],
            "contract_version": "enterprise-v1"},
        "summary": {"content": "仅联调样例：完成本地接口检查，下一步完善测试。", "report_date": "2026-10-17",
            "contract_version": "enterprise-v1"},
    }
    folder = ROOT / ".runtime/enterprise-unified"
    deployment_path = folder / "deployment.json"
    deployment = json.loads(deployment_path.read_text(encoding="utf-8")) if deployment_path.exists() else None
    expected_workflow = deployment["app"]["workflow_id"] if deployment else None
    results = []
    for name, inputs in cases.items():
        scene = name.split(".")[0]
        try:
            result = client.run(scene, inputs, 0)
            data = transport.response["data"]
            if expected_workflow:
                assert data["workflow_id"] == expected_workflow, "调用到了不同发布版本"
            if scene == "extract":
                assert result["action"] == "daily.create", "提取场景路由错误"
            elif scene == "query":
                validate_query(result["sql_template"], result["params"], {}, inputs["schema_context"])
            elif scene == "knowledge":
                assert result["answer"] and result["citations"], "知识结果缺少来源"
                assert all(c == {"id": 1, "version": 1} for c in result["citations"]), "来源不在授权候选中"
            else:
                assert result["summary"].strip(), "摘要为空"
            record = {"scene": name, "passed": True, "workflow_id": data["workflow_id"],
                      "run_id": transport.response.get("workflow_run_id", data.get("id")), "output_keys": sorted(result)}
        except Exception as exc:
            record = {"scene": name, "passed": False, "error_type": type(exc).__name__, "message": str(exc)}
        results.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "verification.json").write_text(json.dumps({"results": results, "expected_workflow_id": expected_workflow}, ensure_ascii=False, indent=2), encoding="utf-8")
    if not all(item["passed"] for item in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
