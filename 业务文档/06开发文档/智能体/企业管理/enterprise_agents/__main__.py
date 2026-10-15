"""python -m enterprise_agents TASK --input request.json --context trusted.json"""

import argparse
import asyncio
import json
from pathlib import Path
import sys

from pydantic import ValidationError

from .contracts import ActorContext, ChatRequest, CommandRequest, DailyPrepareRequest, SummaryRequest, KnowledgeRequest, NL2SQLRequest
from .runtime import AgentError
from .service import EnterpriseAgents


CALLS = {
    "chat": (ChatRequest, "chat"), "command": (CommandRequest, "command"),
    "daily_prepare": (DailyPrepareRequest, "prepare_daily"),
    "daily_summary": (SummaryRequest, "summarize_daily"),
    "knowledge": (KnowledgeRequest, "ask_knowledge"), "nl2sql": (NL2SQLRequest, "nl2sql"),
}


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=CALLS)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True, help="trusted backend context; never expose as a public request field")
    args = parser.parse_args()
    request_model, method = CALLS[args.task]
    request = request_model.model_validate_json(args.input.read_text(encoding="utf-8-sig"))
    actor = ActorContext.model_validate_json(args.context.read_text(encoding="utf-8-sig"))
    result = await getattr(EnterpriseAgents(), method)(request, actor)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        asyncio.run(main())
    except AgentError as error:
        print(json.dumps({"error_code": error.code, "message": str(error)}, ensure_ascii=False))
        raise SystemExit(1)
    except (ValidationError, OSError):
        print(json.dumps({"error_code": "AGENT_INPUT_INVALID", "message": "输入文件或上下文不符合约定"}, ensure_ascii=False))
        raise SystemExit(1)
