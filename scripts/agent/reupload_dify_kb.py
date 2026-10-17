"""用自定义分段规则（按空行分段、单段 <=300 tokens）重新上传 4 个知识库文档。

先删除旧文档，再以 custom 分段规则重新上传，保证 FAQ「一问一段」粒度。
依赖：本地 Dify（http://localhost）+ 知识库 API 密钥。

用法：python scripts/agent/reupload_dify_kb.py <知识库API密钥>
映射来源：dify/agent/knowledge/dataset_ids.json（build_dify_kb.py 生成）。
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
MAPPING = KB_DIR / "dataset_ids.json"

PROCESS_RULE = {
    "mode": "custom",
    "rules": {
        "pre_processing_rules": [
            {"id": "remove_extra_spaces", "enabled": True},
            {"id": "remove_urls_emails", "enabled": False},
        ],
        "segmentation": {
            "separator": "\n\n",
            "max_tokens": 300,
        },
    },
}

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
        body = resp.read().decode()
        return json.loads(body) if body else {}


def list_documents(dataset_id):
    data = api("GET", f"/v1/datasets/{dataset_id}/documents?limit=100")
    return data.get("data", [])


def delete_document(dataset_id, document_id):
    api("DELETE", f"/v1/datasets/{dataset_id}/documents/{document_id}")


def upload_text(dataset_id, file_path):
    content = file_path.read_text(encoding="utf-8")
    data = api(
        "POST",
        f"/v1/datasets/{dataset_id}/document/create-by-text",
        {
            "name": file_path.stem,
            "text": content,
            "indexing_technique": "economy",
            "process_rule": PROCESS_RULE,
        },
    )
    return data.get("document", {}).get("id") or data.get("id")


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
    if not MAPPING.exists():
        print(f"缺少映射文件 {MAPPING}，请先运行 build_dify_kb.py")
        sys.exit(1)
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))

    for name, info in mapping.items():
        dataset_id = info["dataset_id"]
        file_name = KB_FILES.get(name)
        file_path = KB_DIR / file_name if file_name else None
        if not file_path or not file_path.exists():
            print(f"[跳过] {name}: 源文件不存在")
            continue

        docs = list_documents(dataset_id)
        for doc in docs:
            delete_document(dataset_id, doc["id"])
            print(f"[删除] {name} 旧文档 {doc['id']}")

        document_id = upload_text(dataset_id, file_path)
        ok = wait_indexed(dataset_id, document_id)
        info["document_id"] = document_id
        info["status"] = "completed" if ok else "timeout"
        print(f"[重传] {name} -> document_id={document_id} 索引={'完成' if ok else '超时'}")

    MAPPING.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n映射已更新 {MAPPING}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()[:500]}")
        sys.exit(1)
