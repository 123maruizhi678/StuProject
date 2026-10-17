"""用自定义分段规则（按空行分段、单段 <=300 tokens）重新上传 4 个知识库文档。

先删除旧文档，再以 custom 分段规则重新上传，保证 FAQ「一问一段」粒度。
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = "http://localhost"
TOKEN = sys.argv[1]
KB_DIR = Path(__file__).resolve().parent.parent.parent / "dify" / "agent" / "knowledge"

PROCESS_RULE = {
    "mode": "custom",
    "rules": {
        "pre_processing_rules": [
            {"id": "remove_extra_spaces", "enabled": True},
            {"id": "remove_urls_emails", "enabled": False},
        ],
        "segmentation": {"separator": "\n\n", "max_tokens": 300, "chunk_overlap": 0},
    },
}

DOC_NAMES = {
    "公司信息": "公司信息.md",
    "公司业务": "公司业务.md",
    "留学政策": "留学政策.md",
    "FAQ": "FAQ.md",
}


def call(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        BASE + path,
        method=method,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def wait_indexed(dataset_id: str, doc_id: str, timeout: int = 180) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = call("GET", f"/v1/datasets/{dataset_id}/documents?page=1&limit=20")
        for doc in data.get("data", []):
            if doc["id"] == doc_id:
                status = doc.get("indexing_status")
                if status == "completed":
                    return status
                if status in ("error", "archived"):
                    raise RuntimeError(f"索引失败: {doc.get('error')}")
        time.sleep(2)
    return "timeout"


def clean_text(text: str) -> str:
    """剔除文档头部的使用说明注释（> 开头的行），避免分词噪声占用关键词槽位。"""
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(">")]
    return "\n".join(lines).strip()


def main() -> None:
    mapping = json.loads((KB_DIR / "dataset_ids.json").read_text(encoding="utf-8"))
    for kb_name, doc_name in DOC_NAMES.items():
        dataset_id = mapping[kb_name]["dataset_id"]
        old_doc_id = mapping[kb_name]["document_id"]
        call("DELETE", f"/v1/datasets/{dataset_id}/documents/{old_doc_id}")
        print(f"[删除旧文档] {kb_name}")
        text = clean_text((KB_DIR / doc_name).read_text(encoding="utf-8"))
        data = call(
            "POST",
            f"/v1/datasets/{dataset_id}/document/create-by-text",
            {
                "name": doc_name,
                "text": text,
                "indexing_technique": "economy",
                "doc_language": "Chinese",
                "process_rule": PROCESS_RULE,
            },
        )
        doc_id = data["document"]["id"]
        status = wait_indexed(dataset_id, doc_id)
        mapping[kb_name]["document_id"] = doc_id
        mapping[kb_name]["status"] = status
        print(f"[重新上传] {kb_name} -> {doc_id} ({status})")

    (KB_DIR / "dataset_ids.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("完成，dataset_ids.json 已更新")


if __name__ == "__main__":
    main()
