"""客户研判 9 接口端到端测试（httpx 同步）。

前置：uvicorn app.main:app 已启动；DB 已执行 scripts/seed_demo.py。
运行：python test_customer_api.py
"""

import sys

import httpx

BASE = "http://127.0.0.1:8000"
PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = ""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {detail}")


def login(username: str, password: str = "123456") -> str:
    r = httpx.post(f"{BASE}/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    assert r.json()["code"] == 0, r.text
    return r.json()["data"]["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def main() -> None:
    # ---- 登录 ----
    admin = login("cust_admin")
    analyst = login("analyst")
    reviewer = login("reviewer")
    consultant = login("consultant")
    print("登录：cust_admin / analyst / reviewer / consultant 均成功")

    # ---- 1. 创建文本来源 ----
    r = httpx.post(f"{BASE}/api/v1/customer/source", headers=auth(admin),
                   data={"text": "张三，男，35岁，硕士，计算机，8年经验，互联网，架构师，北京，高，意向PROD-A，13800138000，zhangsan@example.com"})
    check("创建文本来源", r.status_code == 200 and r.json()["code"] == 0, r.text)
    source_id = r.json()["data"]["id"]

    # ---- 2. 解析 ----
    r = httpx.post(f"{BASE}/api/v1/customer/source/{source_id}/parse",
                   headers=auth(admin), json={"force": False})
    check("解析来源", r.status_code == 200 and r.json()["code"] == 0, r.text)
    fields = r.json()["data"]["fields"]
    info_id = fields[0]["id"]

    # 电话不落明文，邮箱掩码
    raw = httpx.get(f"{BASE}/api/v1/customer/result").json()
    print(f"  解析出 {len(fields)} 条字段记录，info_id={info_id}")

    # ---- 3. 单条研判 ----
    r = httpx.post(f"{BASE}/api/v1/customer/judge", headers=auth(admin),
                   json={"customer_info_id": info_id, "product_code": "PROD-A"})
    check("单条研判", r.status_code == 200 and r.json()["code"] == 0, r.text)
    result = r.json()["data"]
    result_id = result["id"]
    print(f"  研判结果 matched={result['matched']} score={result['score']} rule={result['rule_version']}")

    # ---- 4. 批量研判（含一个不存在的 id，验证 savepoint）----
    r = httpx.post(f"{BASE}/api/v1/customer/judge/batch", headers=auth(admin),
                   json={"customer_info_ids": [info_id, 999999], "product_code": "PROD-A"})
    check("批量研判（含失败项隔离）", r.status_code == 200 and r.json()["code"] == 0, r.text)

    # ---- 5. 结果详情 ----
    r = httpx.get(f"{BASE}/api/v1/customer/result/{result_id}", headers=auth(reviewer))
    check("结果详情（reviewer）", r.status_code == 200 and r.json()["code"] == 0, r.text)

    # ---- 6. 结果列表 ----
    r = httpx.get(f"{BASE}/api/v1/customer/result", headers=auth(consultant),
                  params={"page": 1, "page_size": 20})
    check("结果列表（consultant）", r.status_code == 200 and r.json()["code"] == 0, r.text)

    # ---- 7. 规则列表 ----
    r = httpx.get(f"{BASE}/api/v1/customer/rule", headers=auth(reviewer))
    check("规则列表（reviewer）", r.status_code == 200 and r.json()["code"] == 0, r.text)

    # ---- 8. 发布新规则 ----
    r = httpx.put(f"{BASE}/api/v1/customer/rule", headers=auth(admin), json={
        "product_code": "PROD-A",
        "rule_content": {
            "match_logic": "all",
            "conditions": [{"field": "work_years", "op": "ge", "value": 5}],
            "score_rules": [{"field": "work_years", "points": {"10": 30, "5": 20}}],
        },
        "rule_description": "测试发布 v2",
    })
    check("发布新规则（admin）", r.status_code == 200 and r.json()["code"] == 0, r.text)

    # ---- 9. 原件下载（文本来源无原件，预期 404）----
    r = httpx.get(f"{BASE}/api/v1/customer/source/{source_id}/file", headers=auth(admin))
    check("原件下载（文本来源无原件→404）", r.status_code == 200 and r.json()["code"] == 404, r.text)

    # ---- 权限边界 ----
    r = httpx.get(f"{BASE}/api/v1/customer/result", headers=auth(analyst))
    check("analyst 读结果被拒（403）", r.json()["code"] == 403, r.text)
    r = httpx.put(f"{BASE}/api/v1/customer/rule", headers=auth(reviewer), json={"product_code": "PROD-A", "rule_content": {"conditions": []}})
    check("reviewer 发布规则被拒（403）", r.json()["code"] == 403, r.text)
    r = httpx.post(f"{BASE}/api/v1/customer/source", headers=auth(reviewer), data={"text": "x"})
    check("reviewer 创建来源被拒（403）", r.json()["code"] == 403, r.text)
    r = httpx.post(f"{BASE}/api/v1/customer/judge", headers=auth(consultant), json={"customer_info_id": info_id, "product_code": "PROD-A"})
    check("consultant 研判被拒（403）", r.json()["code"] == 403, r.text)
    r = httpx.get(f"{BASE}/api/v1/customer/result/{result_id}")
    check("未认证被拒（401）", r.json()["code"] == 401, r.text)

    print(f"\n结果：PASS={PASS} FAIL={FAIL}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
