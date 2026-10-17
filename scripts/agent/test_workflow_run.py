"""联调测试：调用 Dify 客服Agent 工作流 /workflows/run，验证 7 场景输出。

用法：python scripts/agent/test_workflow_run.py
配置来源：根目录 .env 的 DIFY_API_BASE / DIFY_AGENT_API_KEY。
"""
import json

import httpx


def load_env(path=".env"):
    cfg = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        cfg[k.strip()] = v.strip()
    return cfg


ENV = load_env()
BASE = ENV.get("DIFY_API_BASE", "http://127.0.0.1/v1").rstrip("/")
KEY = ENV.get("DIFY_AGENT_API_KEY", "")

# 7 大意图场景的典型问法 -> 期望 intent
CASES = [
    ("company_info", "你们是什么公司？有哪些校区？"),
    ("business_query", "你们提供哪些服务？"),
    ("policy_query", "德国签证需要什么材料？"),
    ("course_recommend", "我想提升雅思，有课程推荐吗？"),
    ("event_query", "最近有什么讲座？"),
    ("faq", "退费政策是什么？"),
    ("chat", "你好呀"),
]


def run(query):
    resp = httpx.post(
        f"{BASE}/workflows/run",
        json={"inputs": {"query": query}, "response_mode": "blocking", "user": "test-workflow-run"},
        headers={"Authorization": f"Bearer {KEY}"},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json().get("data", {})
    outputs = data.get("outputs") or {}
    return data.get("status"), outputs.get("intent"), outputs.get("reply") or ""


def main():
    if not KEY:
        print("未配置 DIFY_AGENT_API_KEY（.env）")
        raise SystemExit(1)

    passed = 0
    for expect, query in CASES:
        try:
            status, intent, reply = run(query)
        except Exception as e:  # noqa: BLE001 - 联调脚本逐例容错
            print(f"[失败] 《{query}》 {e}")
            continue
        mark = "OK " if intent == expect else "偏差"
        if intent == expect:
            passed += 1
        print(f"[{mark}] 《{query}》 intent={intent}（期望 {expect}） reply={reply[:40]}...")
    print(f"\n通过 {passed}/{len(CASES)}")


if __name__ == "__main__":
    main()
