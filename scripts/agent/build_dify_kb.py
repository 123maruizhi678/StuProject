"""一键搭建客服 Agent 的 4 个 Dify 知识库（公司信息/公司业务/留学政策/FAQ）。

流程：创建知识库 -> 上传 dify/agent/knowledge/*.md -> 轮询索引状态 -> 输出 dataset_id 映射。
依赖：本地 Dify（http://localhost）+ 知识库 API 密钥。

用法：python scripts/agent/build_dify_kb.py <知识库API密钥>
输出：dataset_id / document_id 映射写入 dify/agent/knowledge/dataset_ids.json。
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
OUT_JSON = KB_DIR / "dataset_ids.json"

# 复用现有「校区手册」知识库同款检索配置（economy 索引，无需 embedding 模型）
RETRIEVAL_MODEL = {
    "search_method": "semantic_search",
    "top_k": 3,
    "weights": None,
    "reranking_mode": None,
    "reranking_model": {"reranking_model_name": "", "reranking_model_provider": ""},
    "score_threshold": 0.5,
}

# 知识库名 -> 源文件
KB_FILES = {
    "公司信息": "公司信息.md",
    "公司业务": "公司业务.md",
    "留学政策": "留学政策.md",
    "FAQ": "FAQ.md",
}


def api(method, path, payload=None):
    req = urllib.request.Request(
        BASE + path,
        method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def create_dataset(name):
    data = api(
        "POST",
        "/v1/datasets",
        {
            "name": name,
            "permission": "only_me",
            "indexing_technique": "economy",
            "retrieval_model": RETRIEVAL_MODEL,
        },
    )
    return data["id"]


def upload_document(dataset_id, file_path):
    boundary = "----StuProjectKB"
    body = bytearray()
    file_name = file_path.name
    content = file_path.read_bytes()

    def field(name, value):
        return (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n"
            f"{value}\r\n"
        ).encode()

    body += field("indexing_technique", "economy")
    body += field("process_rule", json.dumps({"mode": "automatic"}))
    body += (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{file_name}\"\r\n"
        f"Content-Type: text/markdown\r\n\r\n"
    ).encode()
    body += content
    body += f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{BASE}/v1/datasets/{dataset_id}/document/create-by-file",
        method="POST",
        data=bytes(body),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def wait_indexed(dataset_id, document_id, timeout=300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = api("GET", f"/v1/datasets/{dataset_id}/documents/{document_id}")
        status = (data.get("display_status") or "").lower()
        if status == "available":
            return True
        if status == "error":
            raise RuntimeError(f"文档索引失败: {data}")
        time.sleep(3)
    return False


def main():
    if not TOKEN:
        print("缺少知识库 API 密钥参数")
        sys.exit(1)

    result = {}
    for name, file_name in KB_FILES.items():
        file_path = KB_DIR / file_name
        if not file_path.exists():
            print(f"[跳过] {name}: 源文件不存在 {file_path}")
            continue
        dataset_id = create_dataset(name)
        print(f"[创建] {name} -> dataset_id={dataset_id}")
        doc = upload_document(dataset_id, file_path)
        document_id = doc.get("document", {}).get("id") or doc.get("id")
        ok = wait_indexed(dataset_id, document_id)
        result[name] = {
            "dataset_id": dataset_id,
            "document_id": document_id,
            "status": "completed" if ok else "timeout",
        }
        print(f"[上传] {name} -> document_id={document_id} 索引={'完成' if ok else '超时'}")

    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n映射已写入 {OUT_JSON}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()[:500]}")
        sys.exit(1)
