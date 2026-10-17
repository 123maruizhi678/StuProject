"""在 Dify 创建「客户画像研判规则」知识库并导入规则文档。

运行：python scripts/create_knowledge_base.py
依赖：本机 Dify 已启动，账号 sunguotao37@163.com / Asdf9876（或改下方常量）。
"""

import base64
import sys
from pathlib import Path

import httpx

DIFY_BASE = "http://127.0.0.1"
EMAIL = "sunguotao37@163.com"
PASSWORD = "Asdf9876"
DATASET_NAME = "客户画像研判规则"
DOC_PATH = Path(__file__).resolve().parents[1] / "dify" / "customer" / "knowledge" / "客户画像研判规则.md"


def main() -> None:
    c = httpx.Client(base_url=DIFY_BASE, timeout=60)
    r = c.post("/console/api/login", json={
        "email": EMAIL,
        "password": base64.b64encode(PASSWORD.encode()).decode(),
        "remember_me": True,
        "language": "zh-Hans",
    })
    assert r.status_code == 200 and r.json().get("result") == "success", r.text
    h = {"X-CSRF-Token": c.cookies["csrf_token"]}

    # 已存在则复用
    dataset_id = None
    r = c.get("/console/api/datasets", params={"page": 1, "limit": 100}, headers=h)
    for item in r.json().get("data", []):
        if item.get("name") == DATASET_NAME:
            dataset_id = item["id"]
            print(f"知识库已存在：{dataset_id}")
            break

    if dataset_id is None:
        r = c.post("/console/api/datasets", headers=h, json={
            "name": DATASET_NAME,
            "description": "客户画像研判规则语义、字段字典、运算符与评分口径（参考资产）",
            "indexing_technique": "economy",
            "permission": "all_team_members",
            "provider": "vendor",
        })
        print("创建知识库", r.status_code, r.text[:300])
        assert r.status_code in (200, 201), r.text
        dataset_id = r.json()["id"]
        print(f"知识库 ID：{dataset_id}")

    # 上传规则文档
    doc_bytes = DOC_PATH.read_bytes()
    r = c.post("/console/api/files/upload", headers=h,
               data={"source": "datasets"},
               files={"file": (DOC_PATH.name, doc_bytes, "text/markdown")})
    print("上传文件", r.status_code, r.text[:300])
    assert r.status_code in (200, 201), r.text
    file_id = r.json()["id"]

    # 创建文档
    r = c.post(f"/console/api/datasets/{dataset_id}/documents", headers=h, json={
        "name": DOC_PATH.name,
        "indexing_technique": "economy",
        "data_source": {
            "info_list": {
                "data_source_type": "upload_file",
                "file_info_list": {"file_ids": [file_id]},
            }
        },
        "process_rule": {"mode": "automatic"},
        "doc_form": "text_model",
        "doc_language": "Chinese",
    })
    print("创建文档", r.status_code, r.text[:500])
    assert r.status_code in (200, 201), r.text

    print("完成：知识库「客户画像研判规则」已创建并导入规则文档。")


if __name__ == "__main__":
    sys.exit(main())
