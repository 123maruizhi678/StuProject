"""从四份已导出 DSL 合并生成一个企业 Workflow，保留原提示词和模型。"""
import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.enterprise.workflow_merge import SCENES, merge_workflows

LEGACY_FILES = {"extract": "enterprise_extract.yml", "query": "enterprise_nl2sql_readonly.yml",
                "knowledge": "enterprise_knowledge.yml", "summary": "enterprise_daily_summary.yml"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=ROOT / "dify/enterprise/legacy")
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    documents = {}
    for scene in SCENES:
        source = args.source_dir / f"{scene}.published.yml"
        if not source.exists():
            source = args.source_dir / LEGACY_FILES[scene]
        documents[scene] = yaml.safe_load(source.read_text(encoding="utf-8-sig"))
    content = yaml.safe_dump(merge_workflows(documents, args.provider, args.model), allow_unicode=True, sort_keys=False)
    if args.json:
        print(json.dumps({"enterprise.yml": content}, ensure_ascii=False))
    else:
        target = ROOT / "dify/enterprise/enterprise.yml"
        target.write_text(content, encoding="utf-8")
        print("Generated dify/enterprise/enterprise.yml")


if __name__ == "__main__":
    main()
