"""一键搭建客服 Agent 的 4 个 Dify 知识库（公司信息/公司业务/留学政策/FAQ）。

流程：创建知识库 -> 上传 dify/agent/knowledge/*.md -> 轮询索引状态 -> 输出 dataset_id 映射。
依赖：本地 Dify（http://localhost）+ 知识库 API 密钥。
"""

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://localhost"
TOKEN = sys.argv[1]
KB_DIR = Path(__file__).resolve().parent.parent.parent / "dify" / "agent" / "knowledge"

# 复用现有「校区手册」知识库同款检索配置（economy 索引，无需 embedding 模型）
RETRIEVAL_MODEL = {
    "search_method": "semantic_search",
    "top_k": 3,
    "weights": None,
    "reranking_mode": None,
    "reranking_model": {"reranking_model_name": "", "reranking_provider_name": ""},
    "score_threshold": 0.5,
    "reranking_enable": False,
    "score_threshold_enabled": False,
}

# 知识库名 -> (源文档, 描述)
KBS = {
    "公司信息": ("公司信息.md", "留学机构公司信息：品牌背景、发展历程、成功案例、校区分布、联系方式"),
    "公司业务": ("公司业务.md", "留学机构业务板块：留学申请、背景提升、语言培训、服务流程"),
    "留学政策": ("留学政策.md", "主流留学国家/地区签证要求、申请门槛、移民就业政策（通用框架，需定期更新）"),
    "FAQ": ("FAQ.md", "高频问答对：申请流程、费用、退费政策、录取入学、服务保障"),
}


def call(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        BASE + path,
        method=method,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def create_dataset(name: str, description: str) -> str:
    data = call(
        "POST",
        "/v1/datasets",
        {
            "name": name,
            "description": description,
            "indexing_technique": "economy",
            "permission": "only_me",
            "retrieval_model": RETRIEVAL_MODEL,
        },
    )
    return data["id"]


def upload_document(dataset_id: str, doc_name: str, text: str) -> str:
    data = call(
        "POST",
        f"/v1/datasets/{dataset_id}/document/create-by-text",
        {
            "name": doc_name,
            "text": text,
            "indexing_technique": "economy",
            "doc_language": "Chinese",
            "process_rule": {"mode": "automatic"},
        },
    )
    return data["document"]["id"]


def wait_indexed(dataset_id: str, doc_id: str, timeout: int = 180) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = call("GET", f"/v1/datasets/{dataset_id}/documents?page=1&limit=20")
        for doc in data.get("data", []):
            if doc["id"] == doc_id:
                status = doc.get("indexing_status") or doc.get("indexing_status_v2") or doc.get("status")
                if status == "completed":
                    return status
                if status in ("error", "archived"):
                    raise RuntimeError(f"文档索引失败: {doc.get('error')}")
        time.sleep(2)
    return "timeout"


def main() -> None:
    result = {}
    for kb_name, (doc_name, desc) in KBS.items():
        text = (KB_DIR / doc_name).read_text(encoding="utf-8")
        dataset_id = create_dataset(kb_name, desc)
        print(f"[创建知识库] {kb_name} -> {dataset_id}")
        doc_id = upload_document(dataset_id, doc_name, text)
        print(f"[上传文档] {doc_name} -> {doc_id}")
        status = wait_indexed(dataset_id, doc_id)
        print(f"[索引状态] {kb_name}: {status}")
        result[kb_name] = {"dataset_id": dataset_id, "document_id": doc_id, "status": status}

    out = KB_DIR / "dataset_ids.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成。映射已写入 {out}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
