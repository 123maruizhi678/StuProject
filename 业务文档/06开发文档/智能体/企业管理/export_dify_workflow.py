"""导出一个服务六项任务的 Dify Workflow DSL；不联网、不创建远程应用。"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from enterprise_agents.contracts import (
    ActorContext, ActionSpec, Candidate, ChatRequest, CommandRequest,
    DailyPrepareRequest, KnowledgeChunk, KnowledgeRequest, NL2SQLRequest,
    ParameterRule, SubmittedReport, SummaryRequest, ViewSpec,
)
from enterprise_agents.service import OUTPUT_MODELS, PROMPTS


ROOT = Path(__file__).resolve().parent
START, LLM, END = "1780000000001", "1780000000002", "1780000000003"


def node(node_id, kind, title, x, **data):
    position = {"x": x, "y": 240}
    return {
        "id": node_id, "type": "custom", "width": 244, "height": 120,
        "position": position, "positionAbsolute": dict(position),
        "sourcePosition": "right", "targetPosition": "left", "selected": False,
        "data": {"type": kind, "title": title, "desc": "", "selected": False, **data},
    }


def build_workflow(provider="", model="", plugin_id=None):
    variables = []
    for name, title, length in (
        ("task", "任务类型", 64), ("system_prompt", "可信后端提供的任务提示词", 65536),
        ("payload_json", "后端授权范围内的JSON资料", 200000),
        ("schema_json", "任务输出JSON Schema", 65536),
    ):
        variables.append({"variable": name, "label": title, "type": "paragraph" if name != "task" else "select",
                          "required": True, "max_length": length,
                          "options": list(OUTPUT_MODELS) if name == "task" else []})
    guard = (PROMPTS / "common.md").read_text(encoding="utf-8")
    system = (
        guard + "\n\n本轮任务：{{#" + START + ".task#}}\n"
        + "后端任务指令：\n{{#" + START + ".system_prompt#}}\n"
        + "输出必须符合下列JSON Schema，只返回JSON对象：\n{{#" + START + ".schema_json#}}"
    )
    nodes = [
        node(START, "start", "六任务统一输入", 80, variables=variables),
        node(LLM, "llm", "企业助手统一AI处理", 410,
             context={"enabled": False, "variable_selector": []},
             model={"provider": provider, "name": model, "mode": "chat", "completion_params": {"temperature": 0}},
             prompt_template=[{"id": "system-instruction", "role": "system", "text": system},
                              {"id": "trusted-payload", "role": "user", "text": "{{#" + START + ".payload_json#}}"}],
             variables=[], vision={"enabled": False}),
        node(END, "end", "统一result输出", 740,
             outputs=[{"variable": "result", "value_selector": [LLM, "text"], "value_type": "string"}]),
    ]
    edges = []
    for source, target, source_type, target_type in ((START, LLM, "start", "llm"), (LLM, END, "llm", "end")):
        edges.append({"id": f"{source}-source-{target}-target", "type": "custom",
                      "source": source, "target": target, "sourceHandle": "source", "targetHandle": "target",
                      "data": {"sourceType": source_type, "targetType": target_type, "isInIteration": False, "isInLoop": False}, "zIndex": 0})
    dependencies = []
    if plugin_id:
        dependencies.append({"type": "marketplace", "current_identifier": None,
                             "value": {"marketplace_plugin_unique_identifier": plugin_id}})
    return {
        "kind": "app", "version": "0.3.0", "dependencies": dependencies,
        "app": {"name": "企业智能助手-六任务统一Workflow", "mode": "workflow", "icon": "🤖",
                "icon_background": "#E0EAFF", "use_icon_as_answer_icon": False,
                "description": "一个Workflow处理对话路由、指令解析、日报整理/汇总、知识问答和NL2SQL候选；业务执行由后端完成。"},
        "workflow": {"conversation_variables": [], "environment_variables": [],
                     "features": {"file_upload": {"enabled": False}, "opening_statement": "",
                                  "retriever_resource": {"enabled": False}, "sensitive_word_avoidance": {"enabled": False},
                                  "speech_to_text": {"enabled": False}, "suggested_questions": [],
                                  "suggested_questions_after_answer": {"enabled": False}, "text_to_speech": {"enabled": False}},
                     "graph": {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 0.8}}},
    }


def test_inputs():
    context = ActorContext(subject="synthetic-dify-smoke-test", role_codes=["employee", "teacher"],
                           now=datetime(2026, 10, 15, 2, tzinfo=timezone.utc))
    requests = {
        "chat": ChatRequest(message="同意测试学生的请假", allowed_routes=["command", "clarify"]),
        "command": CommandRequest(command="同意测试学生的请假，意见为按时返校",
                                  actions=[ActionSpec(name="approve_leave", description="批准已分派的待审批请假", entity_type="leave", requires_target=True,
                                                      fields={"comment": ParameterRule(description="审批意见")})],
                                  candidates=[Candidate(ref="leave-test-1", entity_type="leave", entity_id="910001", display_name="虚构学生的请假", version=1)]),
        "daily_prepare": DailyPrepareRequest(report_date="2026-10-15", text="今天跟进三个客户，还没有签约，明天核对材料。"),
        "daily_summary": SummaryRequest(start_date="2026-10-15", end_date="2026-10-15",
                                        reports=[SubmittedReport(daily_report_id="910001", employee_id="910002", report_date="2026-10-15",
                                                                 submitted_content="跟进三个客户，尚未签约。", version=1)]),
        "knowledge": KnowledgeRequest(question="新人应联系谁？", chunks=[KnowledgeChunk(ref="guide-test-v1", knowledge_id="910001", content_version=1,
                                                                                     title="虚构入职指南", content="新人先联系本部门负责人了解工作安排。")]),
        "nl2sql": NL2SQLRequest(question="查询姓名为测试客户的客户ID和姓名", views=[ViewSpec(name="v_authorized_customer", description="虚构的已授权客户视图",
                                                                                       columns={"customer_id": "内部主键", "full_name": "客户姓名"})]),
    }
    examples = {}
    for task, request in requests.items():
        prompt = (PROMPTS / "common.md").read_text(encoding="utf-8") + "\n\n" + (PROMPTS / (task + ".md")).read_text(encoding="utf-8")
        payload = {"context": {"now": context.now.isoformat(), "timezone": context.timezone, "role_codes": context.role_codes},
                   "request": request.model_dump(mode="json")}
        examples[task] = {"task": task, "system_prompt": prompt,
                          "payload_json": json.dumps(payload, ensure_ascii=False),
                          "schema_json": json.dumps(OUTPUT_MODELS[task].model_json_schema(), ensure_ascii=False)}
    return examples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="", help="对方Dify中实际已配置的provider标识；未知时留空")
    parser.add_argument("--model", default="", help="对方Dify中实际已配置的模型名；未知时留空")
    parser.add_argument("--plugin-id", help="可选：对方模型插件的真实完整标识，不猜测版本")
    args = parser.parse_args()
    if bool(args.provider) != bool(args.model):
        parser.error("provider和model须同时提供或同时留空")
    target = ROOT / "dify"
    target.mkdir(exist_ok=True)
    # JSON is a YAML subset and can be read by Dify's YAML DSL parser.
    # Keep a .yml extension for the DSL import dialog. No extra dependency needed.
    (target / "企业智能助手_单应用_待选模型.yml").write_text(
        json.dumps(build_workflow(args.provider, args.model, args.plugin_id), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (target / "六任务试运行输入.json").write_text(json.dumps(test_inputs(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"workflow_count": 1, "llm_node_count": 1, "task_count": 6,
                      "model_configured": bool(args.provider and args.model), "remote_deployment_performed": False}))


if __name__ == "__main__":
    main()
