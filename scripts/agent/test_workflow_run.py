"""联调测试：调用 Dify 客服Agent 工作流 /workflows/run，验证 7 场景输出。

用法: python scripts/test_workflow_run.py <app-api-key>
"""

import json
import sys
import urllib.error
import urllib.request

BASE = "http://localhost/v1"
KEY = sys.argv[1]

# 覆盖 7 个意图分支的典型问法
QUERIES = [
    ("公司信息", "你们公司成立多久了？有哪些校区？"),
    ("公司业务", "你们提供哪些服务？"),
    ("留学政策", "英国留学毕业后能留下工作吗？"),
    ("FAQ", "申请需要提前多久准备？"),
    ("课程推荐", "我想去英国读研，有课程推荐吗？"),
    ("活动报名", "最近有什么讲座可以报名？"),
    ("闲聊", "你好呀"),
]


def run(query: str) -> dict:
    req = urllib.request.Request(
        f"{BASE}/workflows/run",
        method="POST",
        data=json.dumps(
            {
                "inputs": {"query": query},
                "response_mode": "blocking",
                "user": "visitor-test",
            }
        ).encode("utf-8"),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode("utf-8", "ignore")[:500]}


for expect, query in QUERIES:
    data = run(query)
    if "http_error" in data:
        print(f"[{expect}] HTTP {data['http_error']}: {data['body'][:200]}")
        continue
    status = (data.get("data") or {}).get("status")
    outputs = (data.get("data") or {}).get("outputs") or {}
    intent = outputs.get("intent")
    reply = (outputs.get("reply") or "")[:60].replace("\n", " ")
    error = (data.get("data") or {}).get("error")
    ok = "OK " if intent == expect else "MISMATCH"
    print(f"[{ok}] 期望={expect} 实际={intent} status={status} | {reply}")
    if error:
        print(f"       error: {str(error)[:200]}")
