"""统一企业 Workflow 的适配、分流、输出契约及原图保留回归。"""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import yaml

from app.clients.enterprise.enterprise_dify import EnterpriseDifyClient
from app.config import settings
from app.core.common.response import BusinessException

ROOT = Path(__file__).resolve().parents[2]
RESULTS = {
    "extract": {"action": "daily.create", "target": {}, "fields": {"submitted_content": "测试日报"}, "missing_fields": [], "needs_clarification": False},
    "query": {"schema_version": "enterprise-query-v1", "sql_template": "SELECT COUNT(*) AS total FROM customers", "params": {}, "referenced_tables": ["customers"], "referenced_columns": []},
    "knowledge": {"answer": "测试签到时间为九点。", "citations": [{"id": 1, "version": 1}], "mode": "qa"},
    "summary": {"summary": "完成测试，下一步完善检查。"},
}
INPUTS = {
    "extract": {"text": "提交日报", "action_catalog": ["daily.create"], "field_schema": {}, "context": {}},
    "query": {"question": "客户数量", "schema_context": {"customers": ["customer_id"]}, "dialect": "mysql", "query_constraints": {"max_rows": 100}, "bound_filters": {}, "schema_version": "enterprise-query-v1"},
    "knowledge": {"question": "签到时间", "mode": "qa", "candidates": [{"id": 1, "version": 1, "content": "签到时间九点"}]},
    "summary": {"content": "完成测试", "report_date": "2026-10-17"},
}


def result_for(scene, mode="qa"):
    result = {"contract_version": "enterprise-v1", **deepcopy(RESULTS[scene])}
    if scene == "knowledge":
        result["mode"] = mode
    return result


class Transport:
    def __init__(self):
        self.calls = []
        self.override = None

    def post_json_sync(self, path, *, api_key, payload):
        self.calls.append((path, api_key, payload))
        scene = payload["inputs"]["scene"]
        inputs = json.loads(payload["inputs"]["payload"])
        return self.override or {"data": {"status": "succeeded", "outputs": {
            "scene": scene, "result": result_for(scene, inputs.get("mode", "qa"))}}}


class UnifiedClientTests(unittest.TestCase):
    def setUp(self):
        config = patch.multiple(settings, ENTERPRISE_DIFY_API_KEY="app-fictional-unified-test-key",
                                ENTERPRISE_DIFY_CONTRACT_VERSION="enterprise-v1")
        config.start()
        self.addCleanup(config.stop)
        self.transport = Transport()
        self.client = EnterpriseDifyClient(self.transport)

    def test_every_scene_uses_one_key_and_preserves_business_result(self):
        for scene, fields in INPUTS.items():
            with self.subTest(scene=scene):
                self.assertEqual(self.client.run(scene, fields, 7), result_for(scene))
                path, key, body = self.transport.calls[-1]
                self.assertEqual((path, key), ("/workflows/run", "app-fictional-unified-test-key"))
                self.assertEqual(set(body["inputs"]), {"scene", "payload"})
                self.assertEqual(json.loads(body["inputs"]["payload"]), {**fields, "contract_version": "enterprise-v1"})
                self.assertEqual(body["user"], "enterprise:7")
        self.assertEqual(self.client.run("knowledge", {**INPUTS["knowledge"], "mode": "rag"}, 7)["mode"], "rag")

    def test_invalid_scene_or_version_does_not_call_model(self):
        for scene, fields in [("delete", {}), ([], {}), ("summary", []), ("summary", {"contract_version": "wrong"})]:
            with self.subTest(scene=scene), self.assertRaises(BusinessException) as caught:
                self.client.run(scene, fields, 7)
            self.assertEqual(caught.exception.code, 400)
        self.assertEqual(self.transport.calls, [])

    def test_missing_key_never_falls_back_to_another_application(self):
        with patch.object(settings, "ENTERPRISE_DIFY_API_KEY", ""), self.assertRaises(BusinessException) as caught:
            self.client.run("summary", INPUTS["summary"], 7)
        self.assertEqual(caught.exception.code, 503)
        self.assertEqual(self.transport.calls, [])

    def test_invalid_output_and_mismatched_scene_are_rejected(self):
        for data in [
            {"status": "failed"},
            {"status": "succeeded", "outputs": {"scene": "query", "result": result_for("summary")}},
            {"status": "succeeded", "outputs": {"scene": "summary", "result": "not json"}},
            {"status": "succeeded", "outputs": {"scene": "summary", "result": {"contract_version": "enterprise-v1", "summary": []}}},
            {"status": "succeeded", "outputs": {"scene": "summary", "result": {"contract_version": "wrong", "summary": "test"}}},
        ]:
            self.transport.override = {"data": data}
            with self.subTest(data=data), self.assertRaises(BusinessException) as caught:
                self.client.run("summary", INPUTS["summary"], 7)
            self.assertEqual(caught.exception.code, 503)

    def test_query_and_knowledge_subcontracts_are_checked(self):
        for scene, change in [("query", {"schema_version": "wrong"}), ("knowledge", {"mode": "rag"})]:
            self.transport.override = {"data": {"status": "succeeded", "outputs": {
                "scene": scene, "result": {**result_for(scene), **change}}}}
            with self.subTest(scene=scene), self.assertRaises(BusinessException):
                self.client.run(scene, INPUTS[scene], 7)

    def test_json_string_result_is_supported(self):
        self.transport.override = {"data": {"status": "succeeded", "outputs": {
            "scene": "summary", "result": json.dumps(result_for("summary"))}}}
        self.assertEqual(self.client.run("summary", INPUTS["summary"], 7), result_for("summary"))

    def test_enterprise_address_is_independent_of_other_modules(self):
        response = {"data": {"status": "succeeded", "outputs": {"scene": "summary", "result": result_for("summary")}}}
        with patch.object(settings, "ENTERPRISE_DIFY_API_BASE", "http://enterprise.test/v1"), \
             patch.object(settings, "DIFY_API_BASE", "http://other-modules.test/v1"), \
             patch("app.clients.enterprise.enterprise_dify.DifyHttpClient") as factory:
            factory.return_value.post_json_sync.return_value = response
            self.assertEqual(EnterpriseDifyClient().run("summary", INPUTS["summary"], 7), result_for("summary"))
            factory.assert_called_once_with("http://enterprise.test/v1", settings.DIFY_API_TIMEOUT_SECONDS)


class UnifiedGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = yaml.safe_load((ROOT / "dify/enterprise/enterprise.yml").read_text(encoding="utf-8"))

    def execute_graph(self, scene, fields):
        graph = self.document["workflow"]["graph"]
        nodes = {n["id"]: n for n in graph["nodes"]}
        values, visited, current = {"start": {"scene": scene, "payload": json.dumps(fields, ensure_ascii=False)}}, [], "start"
        def select(selector):
            value = values[selector[0]]
            for field in selector[1:]: value = value[field]
            return value
        while True:
            self.assertNotIn(current, visited)
            visited.append(current)
            node = nodes[current]["data"]
            handle = "source"
            if node["type"] == "code":
                scope = {}
                exec(node["code"], scope)
                values[current] = scope["main"](**{v["variable"]: select(v["value_selector"]) for v in node["variables"]})
            elif node["type"] == "if-else":
                handle = "false"
                for case in node["cases"]:
                    if all(select(c["variable_selector"]) == c["value"] for c in case["conditions"]):
                        handle = case["case_id"]
                        break
            elif node["type"] == "llm":
                values[current] = {"text": json.dumps(result_for(scene, fields.get("mode", "qa")), ensure_ascii=False)}
            elif node["type"] == "end":
                return {v["variable"]: select(v["value_selector"]) for v in node["outputs"]}, visited
            outgoing = [e for e in graph["edges"] if e["source"] == current and e["sourceHandle"] == handle]
            self.assertEqual(len(outgoing), 1, (current, handle))
            current = outgoing[0]["target"]

    def test_all_five_paths_execute_exactly_one_scene_model(self):
        for scene, mode in [("extract", None), ("query", None), ("summary", None), ("knowledge", "qa"), ("knowledge", "rag")]:
            with self.subTest(scene=scene, mode=mode):
                fields = {**INPUTS[scene], "contract_version": "enterprise-v1"}
                if mode: fields["mode"] = mode
                outputs, visited = self.execute_graph(scene, fields)
                self.assertEqual(outputs, {"scene": scene, "result": result_for(scene, mode or "qa")})
                self.assertEqual(sum("-llm" in name for name in visited), 1)
                self.assertTrue(all(name.startswith(scene + "-") for name in visited if "-llm" in name))

    def test_unknown_scene_missing_fields_and_invalid_mode_fail_before_model(self):
        for scene, fields in [("unsupported", {}), ("summary", {}), ("knowledge", {**INPUTS["knowledge"], "mode": "guess"})]:
            with self.subTest(scene=scene), self.assertRaises(ValueError):
                self.execute_graph(scene, {**fields, "contract_version": "enterprise-v1"})

    def test_graph_ids_edges_and_selector_targets_exist(self):
        graph = self.document["workflow"]["graph"]
        ids = [n["id"] for n in graph["nodes"]]
        self.assertEqual(len(ids), len(set(ids)))
        for edge in graph["edges"]:
            self.assertIn(edge["source"], ids)
            self.assertIn(edge["target"], ids)
        self.assertEqual(sum(n["data"]["type"] == "start" for n in graph["nodes"]), 1)
        self.assertEqual(sum(n["data"]["type"] == "llm" for n in graph["nodes"]), 5)


if __name__ == "__main__":
    unittest.main()
