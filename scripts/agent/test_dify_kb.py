"""检索测试：验证 4 个知识库能命中预期内容。"""

import json
import sys
import urllib.request

BASE = "http://localhost"
TOKEN = sys.argv[1]
KB_DIR = __file__.rsplit("\\", 3)[0] + "\\dify\\agent\\knowledge"

TESTS = [
    ("公司信息", "你们公司有哪些校区"),
    ("公司业务", "提供背景提升服务吗"),
    ("留学政策", "英国毕业后能留几年"),
    ("FAQ", "退费政策是什么"),
]


def call(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        BASE + path,
        method=method,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


mapping = json.loads(open(KB_DIR + "\\dataset_ids.json", encoding="utf-8").read())
for kb_name, query in TESTS:
    dataset_id = mapping[kb_name]["dataset_id"]
    data = call(
        "POST",
        f"/v1/datasets/{dataset_id}/retrieve",
        {"query": query, "retrieval_model": {
            "search_method": "keyword_search",
            "top_k": 3,
            "score_threshold": 0.0,
            "score_threshold_enabled": False,
            "reranking_enable": False,
            "reranking_mode": None,
            "weights": None,
            "reranking_model": {"reranking_model_name": "", "reranking_provider_name": ""},
        }},
    )
    records = data.get("records", [])
    print(f"== {kb_name} | 查询: {query} | 命中 {len(records)} 条")
    for r in records[:2]:
        seg = r.get("segment", {})
        print(f"   score={r.get('score'):.3f} | {seg.get('content', '')[:80].replace(chr(10), ' ')}")
