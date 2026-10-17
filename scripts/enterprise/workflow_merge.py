"""Merge exported enterprise graphs, preserving each LLM prompt and model."""
from copy import deepcopy

SCENES = ("extract", "query", "knowledge", "summary")
LABELS = {"extract": "动作提取", "query": "只读查询", "knowledge": "知识问答", "summary": "日报摘要"}
FIELDS = {
    "extract": {"text": "str", "action_catalog": "list", "field_schema": "dict", "context": "dict"},
    "query": {"question": "str", "schema_context": "dict", "dialect": "str", "query_constraints": "dict", "bound_filters": "dict", "schema_version": "str"},
    "knowledge": {"question": "str", "mode": "str", "candidates": "list"},
    "summary": {"content": "str", "report_date": "str"},
}
OUTPUT_KEYS = sorted({"contract_version", *(key for fields in FIELDS.values() for key in fields)})


def node(identifier, kind, title, data, x, y=400):
    return {"id": identifier, "type": "custom", "position": {"x": x, "y": y},
            "positionAbsolute": {"x": x, "y": y}, "width": 260, "height": 100,
            "sourcePosition": "right", "targetPosition": "left",
            "data": {"type": kind, "title": title, "selected": False, **data}}


def edge(source, target, handle="source"):
    return {"id": f"{source['id']}-{handle}-{target['id']}", "source": source["id"],
            "target": target["id"], "sourceHandle": handle, "targetHandle": "target", "type": "custom",
            "data": {"sourceType": source["data"]["type"], "targetType": target["data"]["type"],
                     "isInIteration": False, "isInLoop": False}, "zIndex": 0}


def unpack_code():
    return '''import json

def main(scene: str, payload: str) -> dict:
    fields = ''' + repr(FIELDS) + '''
    types = {"str": str, "list": list, "dict": dict}
    if scene not in fields:
        raise ValueError("Unsupported enterprise scene")
    value = json.loads(payload)
    if not isinstance(value, dict) or value.get("contract_version") != "enterprise-v1":
        raise ValueError("Invalid enterprise input contract")
    for key, kind in fields[scene].items():
        if not isinstance(value.get(key), types[kind]):
            raise ValueError("Invalid input type: " + key)
    if scene == "knowledge" and value["mode"] not in ("qa", "rag"):
        raise ValueError("Invalid knowledge mode")
    if scene == "query" and (value["dialect"] != "mysql" or value["schema_version"] != "enterprise-query-v1"):
        raise ValueError("Invalid enterprise query contract")
    result = {key: "" for key in ''' + repr(OUTPUT_KEYS) + '''}
    for key in fields[scene].keys() | {"contract_version"}:
        item = value[key]
        result[key] = json.dumps(item, ensure_ascii=False) if isinstance(item, (dict, list)) else item
    return result
'''


def rewire(data, identifiers):
    if isinstance(data, list):
        return [rewire(item, identifiers) for item in data]
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key in {"value_selector", "variable_selector"} and isinstance(value, list) and value:
                result[key] = [identifiers.get(value[0], value[0]), *value[1:]]
            else:
                result[key] = rewire(value, identifiers)
        return result
    if isinstance(data, str):
        for old, new in identifiers.items():
            data = data.replace("{{#" + old + ".", "{{#" + new + ".")
    return data


def merge_workflows(documents, provider=None, model=None):
    start = node("start", "start", "统一企业入口", {"variables": [
        {"variable": "scene", "label": "业务场景", "type": "select", "required": True, "max_length": 48, "options": list(SCENES)},
        {"variable": "payload", "label": "后端授权输入（JSON）", "type": "paragraph", "required": True, "max_length": 262144, "options": []}]}, 40)
    unpack = node("unpack", "code", "输入契约校验与解包", {"code_language": "python3", "code": unpack_code(),
        "variables": [{"variable": key, "value_selector": ["start", key]} for key in ("scene", "payload")],
        "outputs": {key: {"type": "string", "children": None} for key in OUTPUT_KEYS}}, 370)
    route = node("scene-route", "if-else", "按业务场景分流", {"cases": [
        {"case_id": scene, "logical_operator": "and", "conditions": [
            {"variable_selector": ["start", "scene"], "comparison_operator": "is", "value": scene}]} for scene in SCENES]}, 700)
    nodes, edges, dependencies = [start, unpack, route], [edge(start, unpack), edge(unpack, route)], []
    for index, scene in enumerate(SCENES):
        workflow = documents[scene]["workflow"]
        if workflow.get("environment_variables") or workflow.get("conversation_variables"):
            raise ValueError("Application-scoped variables require explicit merge handling")
        for dependency in documents[scene].get("dependencies", []):
            if dependency not in dependencies:
                dependencies.append(deepcopy(dependency))
        graph = workflow["graph"]
        starts = [n for n in graph["nodes"] if n["data"]["type"] == "start"]
        if len(starts) != 1:
            raise ValueError("Each source graph must have exactly one start")
        old_start = starts[0]["id"]
        identifiers = {n["id"]: scene + "-" + n["id"] for n in graph["nodes"]}
        identifiers[old_start] = "unpack"
        copied = {}
        for original in graph["nodes"]:
            if original["id"] == old_start:
                continue
            item = deepcopy(original)
            item["id"] = identifiers[original["id"]]
            item["data"] = rewire(item["data"], identifiers)
            item["data"]["title"] = LABELS[scene] + " · " + item["data"]["title"]
            item["data"]["selected"] = False
            item["position"] = {"x": original["position"]["x"] + 760, "y": original["position"]["y"] + index * 560}
            item["positionAbsolute"] = deepcopy(item["position"])
            if item["data"]["type"] == "llm":
                if provider: item["data"]["model"]["provider"] = provider
                if model: item["data"]["model"]["name"] = model
            if item["data"]["type"] == "end":
                for output in item["data"]["outputs"]:
                    if output["variable"] == "query_result": output["variable"] = "result"
                item["data"]["outputs"].append({"variable": "scene", "value_selector": ["start", "scene"], "value_type": "string"})
            copied[original["id"]] = item
            nodes.append(item)
        for original in graph["edges"]:
            if original["source"] == old_start:
                edges.append(edge(route, copied[original["target"]], scene))
            else:
                item = deepcopy(original)
                item.update(id=scene + "-" + original["id"], source=identifiers[original["source"]], target=identifiers[original["target"]])
                edges.append(item)
    reject = node("reject-scene", "code", "拒绝未知场景", {"code_language": "python3",
        "code": 'def main() -> dict:\n    raise ValueError("Unsupported enterprise scene")\n',
        "variables": [], "outputs": {"result": {"type": "object", "children": None}}}, 1050, 2500)
    invalid_end = node("end-invalid", "end", "无效请求不会返回业务结果", {"outputs": [
        {"variable": "result", "value_selector": [reject["id"], "result"], "value_type": "object"}]}, 1380, 2500)
    nodes.extend([reject, invalid_end])
    edges.extend([edge(route, reject, "false"), edge(reject, invalid_end)])
    return {"kind": "app", "version": "0.5.0", "dependencies": dependencies,
        "app": {"name": "StuProject-企业-统一工作流", "description": "enterprise-v1：scene 分流动作提取、只读查询、知识 QA/RAG、日报摘要；仅接收后端授权输入。",
                "mode": "workflow", "icon": "🏢", "icon_background": "#E0E7FF", "use_icon_as_answer_icon": False},
        "workflow": {"environment_variables": [], "conversation_variables": [],
            "features": deepcopy(documents["extract"]["workflow"]["features"]),
            "graph": {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 0.4}}}}
