"""检索测试：验证 4 个知识库能命中预期内容。

用法：python scripts/agent/test_dify_kb.py <知识库API密钥>
映射来源：dify/agent/knowledge/dataset_ids.json。
"""
import json
import sys
import urllib.request
from pathlib import Path

BASE = "http://localhost"
TOKEN = sys.argv[1]
KB_DIR = Path(__file__).resolve().parent.parent.parent / "dify" / "agent" / "knowledge"
MAPPING = KB_DIR / "dataset_ids.json"

TESTS = [
    ("公司信息", "你们公司有哪些校区"),
    ("公司业务", "提供背景提升服务吗"),
    ("留学政策", "英国毕业后能留几年"),
    ("FAQ", "退费政策是什么"),
]


def retrieve(dataset_id, query):
    req = urllib.request.Request(
        f"{BASE}/v1/datasets/{dataset_id}/retrieve",
        method="POST",
        data=json.dumps({"query": query, "retrieval_model": {"search_method": "semantic_search", "top_k": 3}}).encode(),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def main():
    if not MAPPING.exists():
        print(f"缺少映射文件 {MAPPING}，请先运行 build_dify_kb.py")
        sys.exit(1)
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))

    passed = 0
    for name, query in TESTS:
        info = mapping.get(name)
        if not info:
            print(f"[跳过] {name}: 映射中没有该知识库")
            continue
        records = retrieve(info["dataset_id"], query).get("records", [])
        if records:
            top = records[0]
            score = top.get("score", 0)
            snippet = (top.get("segment", {}).get("content") or "")[:40].replace("\n", " ")
            print(f"[命中] {name} 《{query}》 score={score:.2f} {snippet}...")
            passed += 1
        else:
            print(f"[未命中] {name} 《{query}》")
    print(f"\n通过 {passed}/{len(TESTS)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 - 联调脚本顶层兜底
        print(f"失败: {e}")
        sys.exit(1)
