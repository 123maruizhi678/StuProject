"""重建 Workflow 提示词及输出契约；保留已配置的模型，不发布应用。"""
from pathlib import Path
import sys
import yaml
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def output_schema():
    """复用后端契约，展开引用以便 Dify 编辑器和模型供应商读取。"""
    from app.schemas.student.student import ChatDecision, LeaveInput, TicketInput, ReminderInput
    schema = ChatDecision.model_json_schema()
    definitions = schema.pop('$defs', {})
    # 运行 ID 由客户端从 Dify 响应写入，禁止模型自行生成。
    definitions['MentalAssessment']['properties'].pop('workflow_run_id')

    def expand(value):
        if isinstance(value, list):
            return [expand(item) for item in value]
        if not isinstance(value, dict):
            return value
        if '$ref' in value:
            return expand(definitions[value['$ref'].rsplit('/', 1)[-1]])
        return {key: expand(item) for key, item in value.items() if key not in ('title', 'default')}

    result = expand(schema)
    # 原生严格结构化输出要求每个对象禁止额外字段、所有属性均列入 required。
    # 参数采用业务白名单的联合对象，不能用任意 dict，也不能给查询塞入空值参数。
    def parameters(model, names):
        properties = model.model_json_schema()['properties']
        return {'type': 'object', 'properties': {name: expand(properties[name]) for name in names},
                'required': list(names), 'additionalProperties': False}

    result['properties']['parameters'] = {'anyOf': [
        {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False},
        parameters(LeaveInput, ('leave_content', 'leave_type', 'leave_start_at', 'leave_end_at')),
        parameters(TicketInput, ('content', 'ticket_type', 'category_code')),
        parameters(ReminderInput, ('academic_event_id', 'lead_minutes')),
    ]}
    result['required'] = list(result['properties'])
    mental = result['properties']['mental']
    mental['required'] = list(mental['properties'])
    # 模型必须返回 JSON 数值；后端仍兼容旧流程的 Decimal 字符串。
    mental['properties']['emotion_score'] = {'type': 'number', 'minimum': 0, 'maximum': 100}
    result['properties']['mental']['description'] = (
        '每种意图和模式都必须评估当前文本并填写；不得返回空对象或虚构健康结论。'
        '高风险必须提供非空 trigger_reason。')
    return result


def export():
    path=ROOT/'dify/student/student_assistant.yml'
    data=yaml.safe_load(path.read_text(encoding='utf-8'))
    nodes={n['data']['type']:n for n in data['workflow']['graph']['nodes']}
    nodes['llm']['data']['prompt_template'][0]['text']=(ROOT/'dify/student/assistant_prompt.md').read_text(encoding='utf-8')
    nodes['llm']['data']['structured_output_enabled'] = True
    nodes['llm']['data']['structured_output'] = {'schema': output_schema()}
    # 512 tokens 在回复较长时可能截断完整 JSON。
    nodes['llm']['data']['model']['completion_params']['max_tokens'] = 2048
    path.write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False),encoding='utf-8')
if __name__=='__main__':export()
