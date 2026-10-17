"""只将已发布统一 Workflow 配置写入根 .env，不修改数据库或前端。"""
import argparse
import json
import shutil
from pathlib import Path

from dotenv import dotenv_values, set_key, unset_key

ROOT = Path(__file__).resolve().parents[2]
OLD_KEYS = ("ENTERPRISE_EXTRACT_DIFY_API_KEY", "ENTERPRISE_NL2SQL_DIFY_API_KEY",
            "ENTERPRISE_KNOWLEDGE_DIFY_API_KEY", "ENTERPRISE_SUMMARY_DIFY_API_KEY")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deployment", type=Path, default=ROOT / ".runtime/enterprise-unified/deployment.json")
    args = parser.parse_args()
    deployment = json.loads(args.deployment.read_text(encoding="utf-8"))
    values = deployment["config"]
    values.setdefault("ENTERPRISE_DIFY_API_BASE", "http://127.0.0.1/v1")
    key = values.get("ENTERPRISE_DIFY_API_KEY", "")
    if not key.startswith("app-") or "PLACEHOLDER" in key or values.get("ENTERPRISE_DIFY_CONTRACT_VERSION") != "enterprise-v1":
        raise ValueError("无效的统一工作流发布配置")
    env = ROOT / ".env"
    backup = ROOT / ".runtime/enterprise-unified/env.before"
    backup.parent.mkdir(parents=True, exist_ok=True)
    if env.exists() and not backup.exists():
        shutil.copy2(env, backup)
    for name in ("ENTERPRISE_DIFY_API_BASE", "ENTERPRISE_DIFY_API_KEY", "ENTERPRISE_DIFY_CONTRACT_VERSION"):
        set_key(str(env), name, values[name], quote_mode="always")
    current = dotenv_values(env)
    for name in OLD_KEYS:
        if name in current:
            unset_key(str(env), name)
    print(json.dumps({"configured_names": ["ENTERPRISE_DIFY_API_BASE", "ENTERPRISE_DIFY_API_KEY", "ENTERPRISE_DIFY_CONTRACT_VERSION"], "secrets_printed": False}))


if __name__ == "__main__":
    main()
