"""离线展示六项能力的返回契约；固定示例，不代表真实模型推理结果。"""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from enterprise_agents import EnterpriseAgents
from enterprise_agents.contracts import (
    ActorContext, ChatRequest, CommandRequest, ActionSpec, Candidate, ParameterRule,
    DailyPrepareRequest, SummaryRequest, SubmittedReport, KnowledgeRequest,
    KnowledgeChunk, NL2SQLRequest, ViewSpec,
)
from enterprise_agents.runtime import WorkflowOutput


class DemonstrationRuntime:
    async def run(self, task, **kwargs):
        outputs = {
            "chat":{"route":"command","reply":"请先确认","normalized_request":"批准请假"},
            "command":{"action":"approve_leave","target_ref":"leave-1","parameters":{"comment":"同意"},"explanation":"识别批准意图"},
            "daily_prepare":{"proposed_content":"跟进三个客户，尚未签约。","ai_summary":"三个客户跟进中","work_items":["跟进三个客户"]},
            "daily_summary":{"progress":[{"text":"三个客户正在跟进，尚未签约。","source_ids":["910001"]}]},
            "knowledge":{"found":True,"answer":"联系本部门负责人。","source_refs":["guide-v1"]},
            "nl2sql":{"view_name":"v_customer","sql":"SELECT customer_id, full_name FROM v_customer WHERE full_name=:name LIMIT 20","parameters":{"name":"测试客户"}},
        }
        return WorkflowOutput(outputs[task],"offline-demo")


async def main():
    agent=EnterpriseAgents(DemonstrationRuntime())
    context=ActorContext(subject="offline-demo-employee",role_codes=["employee","teacher"],now=datetime(2026,10,15,2,tzinfo=timezone.utc))
    calls = [
        ("chat",agent.chat(ChatRequest(message="同意测试学生请假",allowed_routes=["command"]),context)),
        ("command",agent.command(CommandRequest(command="同意测试学生请假",actions=[ActionSpec(name="approve_leave",description="批准请假",entity_type="leave",requires_target=True,fields={"comment":ParameterRule(description="审批意见")})],candidates=[Candidate(ref="leave-1",entity_type="leave",entity_id="910001",display_name="测试学生",version=1)]),context)),
        ("daily_prepare",agent.prepare_daily(DailyPrepareRequest(report_date="2026-10-15",text="跟进三个客户，还没签约"),context)),
        ("daily_summary",agent.summarize_daily(SummaryRequest(start_date="2026-10-15",end_date="2026-10-15",reports=[SubmittedReport(daily_report_id="910001",employee_id="910002",report_date="2026-10-15",submitted_content="跟进三个客户，尚未签约。",version=1)]),context)),
        ("knowledge",agent.ask_knowledge(KnowledgeRequest(question="新人联系谁",chunks=[KnowledgeChunk(ref="guide-v1",knowledge_id="910001",content_version=1,title="测试入职指南",content="新人联系本部门负责人。")]),context)),
        ("nl2sql",agent.nl2sql(NL2SQLRequest(question="查测试客户",views=[ViewSpec(name="v_customer",description="仅展示授权客户的测试视图",columns={"customer_id":"内部ID","full_name":"姓名"})]),context)),
    ]
    for task, call in calls:
        result=await call
        print(json.dumps({"task":task,**result.model_dump(mode="json")},ensure_ascii=False,indent=2))


if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
