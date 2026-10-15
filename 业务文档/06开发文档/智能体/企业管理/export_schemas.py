"""生成供 Dify LLM 节点使用的六份输出 JSON Schema。"""

import json
from pathlib import Path

from enterprise_agents.service import OUTPUT_MODELS


def main():
    target = Path(__file__).resolve().parent / "schemas"
    target.mkdir(exist_ok=True)
    for name, model in OUTPUT_MODELS.items():
        (target / (name + ".schema.json")).write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
    print("Exported 6 JSON schemas")


if __name__ == "__main__":
    main()
