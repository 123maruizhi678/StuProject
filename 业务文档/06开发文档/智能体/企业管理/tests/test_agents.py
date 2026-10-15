"""离线验证边界与 Dify 契约，不调用真实模型/数据库，不评估模型准确率。"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest

import httpx
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from enterprise_agents import AgentError, DifyConfig, DifyWorkflowRuntime, EnterpriseAgents
from enterprise_agents.contracts import (
    ActorContext, ActionSpec, Candidate, ChatRequest, CommandRequest, DailyPrepareRequest,
    KnowledgeChunk, KnowledgeRequest, NL2SQLRequest, ParameterRule, SubmittedReport,
    SummaryRequest, ViewSpec,
)
from enterprise_agents.runtime import WorkflowOutput, object_json


class FakeRuntime:
    def __init__(self, output):
        self.output = output
        self.calls = []

    async def run(self, task, **kwargs):
        self.calls.append((task, kwargs))
        return WorkflowOutput(self.output, "offline-run")


def actor():
    return ActorContext(subject="employee:910004", role_codes=["employee", "teacher"], now=datetime(2026, 10, 15, 2, tzinfo=timezone.utc))


def candidate(ref="leave-1", entity_id="910001"):
    return Candidate(ref=ref, entity_type="leave", entity_id=entity_id, display_name="测试张同学", version=3)


def command_request(candidates=None, fields=None):
    spec = ActionSpec(name="approve_leave", description="批准请假", entity_type="leave", requires_target=True,
        fields=fields if fields is not None else {"comment": ParameterRule(description="审批意见")})
    return CommandRequest(command="同意测试张同学的请假", actions=[spec], candidates=candidates if candidates is not None else [candidate()])


def report():
    return SubmittedReport(daily_report_id="910001", employee_id="910002", report_date="2026-10-15", submitted_content="跟进三个客户，尚未签约。", version=2)


def chunk():
    return KnowledgeChunk(ref="k1-v2-p1", knowledge_id="910001", content_version=2, title="测试指南", content="联系部门负责人了解工作流程。", source_reference="内部门户/测试指南")


class AgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_routes_without_claiming_write_success(self):
        runtime = FakeRuntime({"route": "command", "reply": "已批准并通知学生", "normalized_request": "同意请假"})
        result = await EnterpriseAgents(runtime).chat(ChatRequest(message="同意请假", allowed_routes=["command"]), actor())
        self.assertNotIn("已批准", result.data.reply)
        self.assertIn("预览", result.data.reply)
        self.assertEqual(result.workflow_run_id, "offline-run")

    async def test_unavailable_route_cannot_grant_capability(self):
        runtime = FakeRuntime({"route":"query", "reply":"可查询所有员工", "normalized_request":"所有员工"})
        result = await EnterpriseAgents(runtime).chat(ChatRequest(message="查员工", allowed_routes=["general"]), actor())
        self.assertEqual(result.data.route, "clarify")

    async def test_missing_normalized_request_preserves_original_message(self):
        runtime = FakeRuntime({"route":"query", "reply":"请查询"})
        result = await EnterpriseAgents(runtime).chat(ChatRequest(message="查本周客户",allowed_routes=["query"]),actor())
        self.assertEqual(result.data.normalized_request,"查本周客户")

    async def test_command_binds_server_target_and_version(self):
        runtime = FakeRuntime({"action":"approve_leave", "target_ref":"leave-1", "parameters":{"comment":"同意"}, "explanation":"识别审批意图"})
        result = await EnterpriseAgents(runtime).command(command_request(), actor())
        self.assertEqual(result.data.status, "proposed")
        self.assertEqual(result.data.target.entity_id, "910001")
        self.assertEqual(result.data.target.version, 3)
        self.assertTrue(result.data.requires_confirmation)
        self.assertNotIn("confirmation_token", result.data.model_dump())

    async def test_same_name_candidates_force_clarification_even_if_model_selects_one(self):
        runtime = FakeRuntime({"action":"approve_leave", "target_ref":"leave-1", "parameters":{}, "explanation":"选择第一个"})
        request = command_request([candidate(), candidate("leave-2", "910002")])
        result = await EnterpriseAgents(runtime).command(request, actor())
        self.assertEqual(result.data.status, "needs_clarification")
        self.assertIsNone(result.data.target)
        self.assertFalse(result.data.requires_confirmation)
        self.assertEqual(len(result.data.candidates), 2)

    async def test_no_candidate_is_not_invented(self):
        runtime = FakeRuntime({"action":"approve_leave", "target_ref":None, "parameters":{}, "explanation":"需要目标"})
        result = await EnterpriseAgents(runtime).command(command_request([]), actor())
        self.assertIn("target", result.data.missing_fields)

    async def test_unknown_action_rejected(self):
        runtime = FakeRuntime({"action":"delete_database", "target_ref":None, "parameters":{}, "explanation":"执行删除"})
        with self.assertRaises(AgentError):
            await EnterpriseAgents(runtime).command(command_request(), actor())

    async def test_unknown_parameters_rejected(self):
        runtime = FakeRuntime({"action":"approve_leave", "target_ref":"leave-1", "parameters":{"sql":"UPDATE employee SET role_codes='admin'"}, "explanation":"绕过流程"})
        with self.assertRaises(AgentError):
            await EnterpriseAgents(runtime).command(command_request(), actor())

    async def test_wrong_target_rejected(self):
        runtime = FakeRuntime({"action":"approve_leave", "target_ref":"outside", "parameters":{}, "explanation":"其他目标"})
        with self.assertRaises(AgentError):
            await EnterpriseAgents(runtime).command(command_request(), actor())

    async def test_missing_required_field_asks_instead_of_fabricating(self):
        runtime = FakeRuntime({"action":"approve_leave", "target_ref":"leave-1", "parameters":{}, "explanation":"未提供理由"})
        request = command_request(fields={"reason":ParameterRule(description="理由", required=True)})
        result = await EnterpriseAgents(runtime).command(request, actor())
        self.assertEqual(result.data.missing_fields, ["reason"])
        self.assertEqual(result.data.status, "needs_clarification")

    async def test_boolean_does_not_pass_numeric_parameter(self):
        runtime = FakeRuntime({"action":"approve_leave", "target_ref":"leave-1", "parameters":{"amount":True}, "explanation":"参数"})
        request = command_request(fields={"amount":ParameterRule(description="测试数值", value_type="integer")})
        with self.assertRaises(AgentError):
            await EnterpriseAgents(runtime).command(request, actor())

    async def test_naive_datetime_parameter_rejected(self):
        runtime = FakeRuntime({"action":"approve_leave", "target_ref":"leave-1", "parameters":{"start_at":"2026-10-15T09:00:00"}, "explanation":"参数"})
        request = command_request(fields={"start_at":ParameterRule(description="开始时间", value_type="datetime")})
        with self.assertRaises(AgentError):
            await EnterpriseAgents(runtime).command(request, actor())

    async def test_no_actions_does_not_call_model(self):
        runtime = FakeRuntime({})
        result = await EnterpriseAgents(runtime).command(CommandRequest(command="审批"), actor())
        self.assertEqual(result.data.status, "unsupported")
        self.assertFalse(runtime.calls)

    async def test_daily_date_comes_from_caller_and_result_is_preview(self):
        runtime = FakeRuntime({"proposed_content":"跟进三个客户，尚未签约。", "ai_summary":"客户跟进中", "work_items":["跟进三个客户"]})
        result = await EnterpriseAgents(runtime).prepare_daily(DailyPrepareRequest(report_date="2026-10-15", text="跟进三个客户，尚未签约"), actor())
        self.assertEqual(str(result.data.report_date), "2026-10-15")
        self.assertTrue(result.data.requires_confirmation)

    async def test_summary_cites_real_reports(self):
        runtime = FakeRuntime({"progress":[{"text":"三个客户正在跟进", "source_ids":["910001"]}]})
        result = await EnterpriseAgents(runtime).summarize_daily(SummaryRequest(start_date="2026-10-15", end_date="2026-10-15", reports=[report()]), actor())
        self.assertEqual(result.data.report_count, 1)
        self.assertEqual(result.data.sources[0].version, 2)

    async def test_summary_invented_citation_rejected(self):
        runtime = FakeRuntime({"risks":[{"text":"不存在的风险", "source_ids":["999999"]}]})
        with self.assertRaises(AgentError):
            await EnterpriseAgents(runtime).summarize_daily(SummaryRequest(start_date="2026-10-15", end_date="2026-10-15", reports=[report()]), actor())

    async def test_empty_summary_does_not_call_model(self):
        runtime = FakeRuntime({})
        result = await EnterpriseAgents(runtime).summarize_daily(SummaryRequest(start_date="2026-10-15", end_date="2026-10-15"), actor())
        self.assertEqual(result.data.report_count, 0)
        self.assertFalse(runtime.calls)

    async def test_knowledge_metadata_comes_from_source(self):
        runtime = FakeRuntime({"found":True,"answer":"联系部门负责人。","source_refs":["k1-v2-p1"]})
        result = await EnterpriseAgents(runtime).ask_knowledge(KnowledgeRequest(question="怎么开始工作", chunks=[chunk()]), actor())
        self.assertEqual(result.data.sources[0].content_version, 2)
        self.assertEqual(result.data.sources[0].title, "测试指南")

    async def test_knowledge_unknown_source_rejected(self):
        runtime = FakeRuntime({"found":True,"answer":"捏造答案","source_refs":["unknown"]})
        with self.assertRaises(AgentError):
            await EnterpriseAgents(runtime).ask_knowledge(KnowledgeRequest(question="问题", chunks=[chunk()]), actor())

    async def test_knowledge_missing_citation_rejected(self):
        runtime = FakeRuntime({"found":True,"answer":"没有来源","source_refs":[]})
        with self.assertRaises(AgentError):
            await EnterpriseAgents(runtime).ask_knowledge(KnowledgeRequest(question="问题", chunks=[chunk()]), actor())

    async def test_no_sources_does_not_call_model(self):
        runtime = FakeRuntime({})
        result = await EnterpriseAgents(runtime).ask_knowledge(KnowledgeRequest(question="报销标准"), actor())
        self.assertFalse(result.data.found)
        self.assertFalse(runtime.calls)

    async def test_nl2sql_only_returns_candidate(self):
        runtime = FakeRuntime({"view_name":"v_customer", "sql":"SELECT customer_id FROM v_customer WHERE full_name=:name LIMIT 20", "parameters":{"name":"测试客户"}})
        request = NL2SQLRequest(question="查测试客户",views=[ViewSpec(name="v_customer",description="后端受控客户视图",columns={"customer_id":"内部主键", "full_name":"姓名"})])
        result = await EnterpriseAgents(runtime).nl2sql(request, actor())
        self.assertTrue(result.data.requires_backend_validation)
        self.assertNotIn("rows", result.data.model_dump())

    async def test_nl2sql_refuses_declared_unauthorized_view(self):
        runtime = FakeRuntime({"view_name":"employee", "sql":"SELECT employee_id FROM employee"})
        request = NL2SQLRequest(question="查员工",views=[ViewSpec(name="v_customer",description="客户",columns={"customer_id":"ID"})])
        with self.assertRaises(AgentError):
            await EnterpriseAgents(runtime).nl2sql(request, actor())

    async def test_nl2sql_write_output_rejected(self):
        runtime = FakeRuntime({"view_name":"v_customer", "sql":"DELETE FROM v_customer"})
        request = NL2SQLRequest(question="删除",views=[ViewSpec(name="v_customer",description="客户",columns={"customer_id":"ID"})])
        with self.assertRaises(AgentError):
            await EnterpriseAgents(runtime).nl2sql(request, actor())

    async def test_nl2sql_can_ask_for_clarification(self):
        runtime = FakeRuntime({"status":"needs_clarification","clarification":"请明确时间范围"})
        request = NL2SQLRequest(question="查最近客户",views=[ViewSpec(name="v_customer",description="客户",columns={"customer_id":"ID"})])
        result = await EnterpriseAgents(runtime).nl2sql(request, actor())
        self.assertIsNone(result.data.sql)

    async def test_extra_output_fields_are_rejected(self):
        runtime = FakeRuntime({"proposed_content":"内容","ai_summary":"摘要","executed":True})
        with self.assertRaises(AgentError):
            await EnterpriseAgents(runtime).prepare_daily(DailyPrepareRequest(report_date="2026-10-15",text="内容"),actor())


class ContractTests(unittest.TestCase):
    def test_reserved_execution_fields_cannot_enter_catalog(self):
        with self.assertRaises(ValidationError):
            ActionSpec(name="unsafe",description="错误目录",fields={"sql":ParameterRule(description="自由 SQL")})

    def test_duplicate_and_out_of_range_reports_rejected(self):
        for reports in ([report(),report()], [report().model_copy(update={"report_date":datetime(2026,10,14).date()})]):
            with self.assertRaises(ValidationError):
                SummaryRequest(start_date="2026-10-15",end_date="2026-10-15",reports=reports)

    def test_mixed_knowledge_versions_rejected(self):
        other = chunk().model_copy(update={"ref":"other", "content_version":1})
        with self.assertRaises(ValidationError):
            KnowledgeRequest(question="问题",chunks=[chunk(),other])

    def test_parser_rejects_duplicate_keys_and_non_objects(self):
        for value in ('{"a":1,"a":2}', '[]', 'null', 'prefix {"a":1}'):
            with self.assertRaises((ValueError, TypeError)):
                object_json(value)


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_request_contract_and_fenced_json_output(self):
        sent = []
        def handler(request):
            sent.append(json.loads(request.content))
            self.assertEqual(request.url.path, "/v1/workflows/run")
            self.assertEqual(request.headers["authorization"], "Bearer test-key")
            return httpx.Response(200,json={"workflow_run_id":"run-1","data":{"status":"succeeded","outputs":{"result":"```json\n{\"route\":\"general\",\"reply\":\"你好\"}\n```"}}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            runtime = DifyWorkflowRuntime(DifyConfig(api_key="test-key"),client)
            result = await EnterpriseAgents(runtime).chat(ChatRequest(message="你好"),actor())
        self.assertEqual(result.data.reply,"你好")
        self.assertEqual(sent[0]["response_mode"],"blocking")
        self.assertEqual(set(sent[0]["inputs"]),{"task","system_prompt","payload_json","schema_json"})
        self.assertNotIn(actor().subject,sent[0]["user"])

    async def test_missing_key_fails_without_network(self):
        runtime = DifyWorkflowRuntime(DifyConfig())
        with self.assertRaises(AgentError) as error:
            await EnterpriseAgents(runtime).chat(ChatRequest(message="你好"),actor())
        self.assertEqual(error.exception.code,"AGENT_NOT_CONFIGURED")

    async def test_failure_does_not_leak_credentials_or_response_body(self):
        def handler(request):
            return httpx.Response(401,text="sensitive-input-and-test-key")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            runtime=DifyWorkflowRuntime(DifyConfig(api_key="test-key"),client)
            with self.assertRaises(AgentError) as error:
                await EnterpriseAgents(runtime).chat(ChatRequest(message="隐私输入"),actor())
        self.assertNotIn("test-key",str(error.exception))
        self.assertNotIn("sensitive-input",str(error.exception))

    async def test_failed_workflow_not_treated_as_success(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={"data":{"status":"failed","outputs":{"result":{}}}}))) as client:
            with self.assertRaises(AgentError):
                await EnterpriseAgents(DifyWorkflowRuntime(DifyConfig(api_key="test-key"),client)).chat(ChatRequest(message="你好"),actor())

    async def test_response_size_limit(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,text="x"*100))) as client:
            runtime=DifyWorkflowRuntime(DifyConfig(api_key="test-key",max_response_bytes=20),client)
            with self.assertRaises(AgentError) as error:
                await EnterpriseAgents(runtime).chat(ChatRequest(message="你好"),actor())
        self.assertEqual(error.exception.code,"AGENT_OUTPUT_TOO_LARGE")

    async def test_context_size_limit(self):
        runtime=DifyWorkflowRuntime(DifyConfig(api_key="test-key",max_payload_bytes=20))
        with self.assertRaises(AgentError) as error:
            await EnterpriseAgents(runtime).chat(ChatRequest(message="你好"),actor())
        self.assertEqual(error.exception.code,"AGENT_CONTEXT_TOO_LARGE")

    async def test_timeout_is_sanitized(self):
        def handler(request):
            raise httpx.ReadTimeout("sensitive timeout details")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(AgentError) as error:
                await EnterpriseAgents(DifyWorkflowRuntime(DifyConfig(api_key="test-key"),client)).chat(ChatRequest(message="你好"),actor())
        self.assertEqual(error.exception.code,"AGENT_TIMEOUT")


if __name__ == "__main__":
    unittest.main()
