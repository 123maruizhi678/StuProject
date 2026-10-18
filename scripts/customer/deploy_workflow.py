"""仅通过后端 API 更新客户抽取 Workflow；保留已有模型，备份后发布。"""
import argparse
import copy
import json
import os
import re
from datetime import datetime
from pathlib import Path

import yaml

from dify_console import DifyConsole

ROOT = Path(__file__).resolve().parents[2]


def set_env(path, updates):
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    for name, value in updates.items():
        pattern = re.compile(r"^" + re.escape(name) + r"=.*$", re.MULTILINE)
        line = name + "=" + value
        text = pattern.sub(lambda _: line, text) if pattern.search(text) else text.rstrip() + "\n" + line + "\n"
    path.write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1")
    parser.add_argument("--local-container", default=None, help="需有用户明确授权的本机管理员会话签发")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--configure-env", type=Path)
    args = parser.parse_args()
    console = DifyConsole(args.base, args.local_container)
    document = yaml.safe_load((ROOT / "dify/customer/customer-extract.yml").read_text(encoding="utf-8"))
    apps = [a for a in console.apps() if a["name"] == document["app"]["name"] and a["mode"] == "workflow"]
    if len(apps) > 1:
        raise RuntimeError("Multiple customer extraction apps; refusing ambiguous update")
    backup_dir = ROOT / "dify/customer/backups"
    backup_dir.mkdir(exist_ok=True)
    if apps:
        app_id = apps[0]["id"]
        old = console.request("GET", f"apps/{app_id}/workflows/draft")
        published = console.request("GET", f"apps/{app_id}/workflows/publish")
        # Backups contain only this app's graph/features, not tokens or provider credentials.
        backup = {"app_id": app_id, "draft": {k: old.get(k) for k in ("graph", "features")},
                  "published": {k: published.get(k) for k in ("graph", "features")} if published else None}
        backup_path = backup_dir / (datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")
        backup_path.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")
        llms = [n["data"]["model"] for n in old["graph"]["nodes"] if n["data"]["type"] == "llm"]
        if len(llms) != 1:
            raise RuntimeError("Expected one existing LLM binding")
        for node in document["workflow"]["graph"]["nodes"]:
            if node["data"]["type"] == "llm":
                model = copy.deepcopy(llms[0])
                model["completion_params"]["temperature"] = 0
                node["data"]["model"] = model
        payload = {"graph": document["workflow"]["graph"], "features": old["features"], "hash": old["hash"]}
        console.request("POST", f"apps/{app_id}/workflows/draft", json=payload)
    else:
        imported = console.request("POST", "apps/imports", json={"mode": "yaml-content", "yaml_content": yaml.safe_dump(document, allow_unicode=True)})
        if imported.get("status") not in ("completed", "completed-with-warnings"):
            raise RuntimeError("Dify import did not complete")
        app_id = imported["app_id"]
    if args.publish:
        console.request("POST", f"apps/{app_id}/workflows/publish", json={"marked_name": "customer-extract-v1", "marked_comment": "固定13字段；输入与输出严格校验；规则裁决由后端执行"})
    if args.configure_env:
        if not args.publish:
            raise RuntimeError("Only configure backend against a published workflow")
        keys = console.request("GET", f"apps/{app_id}/api-keys")["data"]
        key = keys[0]["token"] if keys else console.request("POST", f"apps/{app_id}/api-keys")["token"]
        set_env(args.configure_env, {"CUSTOMER_EXTRACT_DIFY_APP_ID": app_id,
                                    "CUSTOMER_EXTRACT_DIFY_API_BASE": args.base.rstrip("/") + "/v1",
                                    "CUSTOMER_EXTRACT_DIFY_API_KEY": key,
                                    "CUSTOMER_EXTRACT_DIFY_TIMEOUT_SECONDS": "60"})
    print(json.dumps({"app_id": app_id, "published": args.publish, "backend_configured": bool(args.configure_env),
                      "url": args.base + "/app/" + app_id + "/workflow"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
