"""使用真实故障输出验证 DSL 与后端契约，而不依赖模型替身补齐字段。"""
from pathlib import Path
from types import SimpleNamespace
import json

import httpx
import pytest
import yaml
from pydantic import SecretStr
from app.clients.student.student_assistant_dify import StudentAssistantDifyClient
from app.core.common.response import BusinessException
from scripts.student.export_student_workflow import output_schema

ROOT = Path(__file__).resolve().parents[2]


def test_workflow_enforces_backend_mental_fields():
    workflow = yaml.safe_load((ROOT / 'dify/student/student_assistant.yml').read_text(encoding='utf-8'))
    node = next(n['data'] for n in workflow['workflow']['graph']['nodes'] if n['data']['type'] == 'llm')
    assert node['structured_output_enabled'] is True
    assert node['structured_output']['schema'] == output_schema()
    mental = node['structured_output']['schema']['properties']['mental']
    assert {'emotion_tag', 'emotion_score', 'risk_level'} <= set(mental['required'])
    assert 'workflow_run_id' not in mental['properties']
    assert node['prompt_template'][0]['text'] == (ROOT / 'dify/student/assistant_prompt.md').read_text(encoding='utf-8')


def test_output_schema_supports_strict_provider_and_business_parameter_variants():
    schema = output_schema()
    def check(value):
        if isinstance(value, dict):
            if value.get('type') == 'object':
                assert value['additionalProperties'] is False
                assert set(value['required']) == set(value['properties'])
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
    check(schema)
    variants = schema['properties']['parameters']['anyOf']
    assert [set(v['properties']) for v in variants] == [
        set(), {'leave_content', 'leave_type', 'leave_start_at', 'leave_end_at'},
        {'content', 'ticket_type', 'category_code'}, {'academic_event_id', 'lead_minutes'}]
    assert schema['properties']['mental']['properties']['emotion_score'] == {
        'type': 'number', 'minimum': 0, 'maximum': 100}


@pytest.mark.parametrize('mode', ['chat', 'summary', 'mental'])
@pytest.mark.parametrize('mental,valid', [
    ({}, False),
    ({'emotion_tag': '紧张', 'emotion_score': 70}, False),
    ({'emotion_tag': '紧张', 'emotion_score': 70, 'risk_level': 'high'}, False),
    ({'emotion_tag': '紧张', 'emotion_score': 70, 'risk_level': 'medium', 'trigger_reason': ''}, True),
])
def test_client_never_fabricates_missing_mental_assessment(mode, mental, valid):
    decision = {'intent': 'feedback', 'answer': '课程时间冲突', 'mental': mental,
                'action': 'none', 'parameters': {}, 'summary': '两门课程时间冲突'}
    calls = []
    def upstream(request):
        calls.append(request)
        return httpx.Response(200, json={'workflow_run_id': 'run-contract', 'data': {
            'status': 'succeeded', 'outputs': {'result': json.dumps(decision)}}})
    config = SimpleNamespace(STUDENT_DIFY_KEY=SecretStr('test-key'),
                             DIFY_API_BASE='http://dify.test/v1', DIFY_API_TIMEOUT_SECONDS=10)
    client = StudentAssistantDifyClient(config, httpx.MockTransport(upstream))
    if valid:
        result, run_id = client.run('课程时间冲突', SimpleNamespace(key='student:test'), mode=mode)
        assert result.mental.risk_level == 'medium'
        assert result.mental.workflow_run_id == run_id == 'run-contract'
    else:
        with pytest.raises(BusinessException) as error:
            client.run('课程时间冲突', SimpleNamespace(key='student:test'), mode=mode)
        assert error.value.code == 503
    assert len(calls) == 1  # 校验失败也不自动重复调用模型。
