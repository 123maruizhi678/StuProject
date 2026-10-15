"""六项企业 AI 功能。这里只形成候选，不签发确认凭证、不执行业务写入。"""

from datetime import date, datetime
from pathlib import Path
import re

from pydantic import ValidationError

from .contracts import (
    ActorContext, AgentResult, ChatRequest, ChatDecision, CommandRequest, CommandDraft,
    CommandProposal, DailyPrepareRequest, DailyDraft, DailyPrepared, SummaryRequest,
    SummaryDraft, DailySummary, ReportSource, KnowledgeRequest, KnowledgeDraft,
    KnowledgeSource, KnowledgeAnswer, NL2SQLRequest, SQLDraft, SQLCandidate,
)
from .runtime import AgentError, DifyWorkflowRuntime, Runtime


PROMPTS = Path(__file__).resolve().parent / "prompts"
NO_KNOWLEDGE = "暂未找到足够的已确认资料，请联系相关负责人核实。"
OUTPUT_MODELS = {
    "chat": ChatDecision, "command": CommandDraft, "daily_prepare": DailyDraft,
    "daily_summary": SummaryDraft, "knowledge": KnowledgeDraft, "nl2sql": SQLDraft,
}


class EnterpriseAgents:
    def __init__(self, runtime: Runtime | None = None):
        self.runtime = runtime if runtime is not None else DifyWorkflowRuntime()

    async def _generate(self, task, request, actor: ActorContext):
        prompt = (PROMPTS / "common.md").read_text(encoding="utf-8") + "\n\n" + (PROMPTS / (task + ".md")).read_text(encoding="utf-8")
        payload = {
            "context": {"now": actor.now.isoformat(), "timezone": actor.timezone, "role_codes": actor.role_codes},
            "request": request.model_dump(mode="json"),
        }
        model = OUTPUT_MODELS[task]
        result = await self.runtime.run(
            task, prompt=prompt, payload=payload, schema=model.model_json_schema(), subject=actor.subject,
        )
        try:
            parsed = model.model_validate(result.data)
        except ValidationError:
            raise AgentError("智能体输出字段、类型或动作不符合约定") from None
        return parsed, result.run_id

    async def chat(self, request: ChatRequest, actor: ActorContext) -> AgentResult[ChatDecision]:
        decision, run_id = await self._generate("chat", request, actor)
        if decision.route in ("query", "command", "knowledge") and not decision.normalized_request:
            decision.normalized_request = request.message
        if decision.route not in request.allowed_routes:
            decision = ChatDecision(route="clarify", reply="当前功能未开放，请使用已授权的业务入口。")
        elif decision.route == "command":
            # 路由阶段没有执行工具，绝不将模型的“已保存/已批准”当作回执。
            decision.reply = "已识别办理意图，请先生成业务预览并核对后确认。"
        elif decision.route == "query":
            decision.reply = "已识别查询意图，请由授权查询服务获取实际结果。"
        elif decision.route == "knowledge":
            decision.reply = "已识别知识问答意图，请在授权资料中检索后回答。"
        return AgentResult(data=decision, workflow_run_id=run_id)

    async def command(self, request: CommandRequest, actor: ActorContext) -> AgentResult[CommandProposal]:
        if not request.actions:
            return AgentResult(data=CommandProposal(status="unsupported", message="当前没有可用的业务动作。"))
        draft, run_id = await self._generate("command", request, actor)
        if draft.action is None:
            return AgentResult(data=CommandProposal(status="unsupported", message="无法匹配已开放动作，请补充需求或使用业务表单。"), workflow_run_id=run_id)
        spec = next((a for a in request.actions if a.name == draft.action), None)
        if spec is None:
            raise AgentError("智能体选择了目录外的动作")
        if set(draft.parameters) - set(spec.fields):
            raise AgentError("智能体返回了动作目录外的参数")
        missing = []
        parameters = {}
        for name, rule in spec.fields.items():
            value = draft.parameters.get(name)
            if value is None or value == "":
                if rule.required:
                    missing.append(name)
                continue
            if not self._parameter_valid(value, rule):
                raise AgentError("智能体返回的业务参数类型或范围不符合动作目录")
            parameters[name] = value
        target = None
        candidates = [c for c in request.candidates if c.entity_type == spec.entity_type]
        if spec.requires_target:
            # 后端需先根据用户输入缩小候选；同一目标仍有多条时强制澄清。
            if len(candidates) != 1:
                missing.append("target")
            elif draft.target_ref != candidates[0].ref:
                raise AgentError("智能体目标与后端候选不一致")
            else:
                target = candidates[0]
        elif draft.target_ref is not None:
            raise AgentError("新增类动作不应带有已有对象引用")
        ready = not missing
        proposal = CommandProposal(
            status="proposed" if ready else "needs_clarification", action=spec.name,
            target=target, parameters=parameters, missing_fields=missing,
            candidates=candidates if "target" in missing else [],
            message="请核对候选内容；后端校验并生成确认凭证后才可办理。" if ready else "请补充必填信息或明确唯一目标，再重新解析。",
            requires_confirmation=ready,
        )
        return AgentResult(data=proposal, workflow_run_id=run_id)

    @staticmethod
    def _parameter_valid(value, rule):
        kind = rule.value_type
        valid = {
            "string": isinstance(value, str), "integer": type(value) is int,
            "number": type(value) in (int, float), "boolean": type(value) is bool,
            "date": isinstance(value, str), "datetime": isinstance(value, str),
        }[kind]
        if not valid:
            return False
        if rule.choices and not any(type(value) is type(choice) and value == choice for choice in rule.choices):
            return False
        if isinstance(value, str):
            if not rule.min_length <= len(value) <= rule.max_length:
                return False
            try:
                if kind == "date":
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                        return False
                    date.fromisoformat(value)
                elif kind == "datetime":
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    if parsed.tzinfo is None or parsed.utcoffset() is None:
                        return False
            except ValueError:
                return False
        if kind in ("number", "integer"):
            if rule.minimum is not None and value < rule.minimum:
                return False
            if rule.maximum is not None and value > rule.maximum:
                return False
        return True

    async def prepare_daily(self, request: DailyPrepareRequest, actor: ActorContext) -> AgentResult[DailyPrepared]:
        draft, run_id = await self._generate("daily_prepare", request, actor)
        return AgentResult(data=DailyPrepared(**draft.model_dump(), report_date=request.report_date), workflow_run_id=run_id)

    async def summarize_daily(self, request: SummaryRequest, actor: ActorContext) -> AgentResult[DailySummary]:
        if not request.reports:
            return AgentResult(data=DailySummary(report_count=0, sources=[]))
        draft, run_id = await self._generate("daily_summary", request, actor)
        reports = {r.daily_report_id: r for r in request.reports}
        cited = set()
        for group in (draft.progress, draft.outputs, draft.risks, draft.next_plans):
            for point in group:
                if not set(point.source_ids) <= reports.keys():
                    raise AgentError("日报汇总引用了输入范围外的日报")
                cited.update(point.source_ids)
        sources = [ReportSource(daily_report_id=r.daily_report_id, employee_id=r.employee_id, version=r.version)
                   for r in request.reports if r.daily_report_id in cited]
        return AgentResult(data=DailySummary(**draft.model_dump(), report_count=len(reports), sources=sources), workflow_run_id=run_id)

    async def ask_knowledge(self, request: KnowledgeRequest, actor: ActorContext) -> AgentResult[KnowledgeAnswer]:
        if not request.chunks:
            return AgentResult(data=KnowledgeAnswer(found=False, answer=NO_KNOWLEDGE))
        draft, run_id = await self._generate("knowledge", request, actor)
        chunks = {c.ref: c for c in request.chunks}
        if not set(draft.source_refs) <= chunks.keys():
            raise AgentError("知识回答引用了输入范围外的来源")
        if not draft.found:
            return AgentResult(data=KnowledgeAnswer(found=False, answer=NO_KNOWLEDGE), workflow_run_id=run_id)
        if not draft.source_refs:
            raise AgentError("知识回答缺少来源")
        sources = [KnowledgeSource(**chunks[ref].model_dump(exclude={"content"})) for ref in dict.fromkeys(draft.source_refs)]
        return AgentResult(data=KnowledgeAnswer(found=True, answer=draft.answer, sources=sources), workflow_run_id=run_id)

    async def nl2sql(self, request: NL2SQLRequest, actor: ActorContext) -> AgentResult[SQLCandidate]:
        draft, run_id = await self._generate("nl2sql", request, actor)
        if draft.status == "needs_clarification":
            if draft.sql is not None or draft.view_name is not None or draft.parameters or not draft.clarification:
                raise AgentError("查询澄清输出不符合约定")
            return AgentResult(data=SQLCandidate(**draft.model_dump()), workflow_run_id=run_id)
        if draft.view_name not in {v.name for v in request.views}:
            raise AgentError("SQL 候选声明了目录外的视图")
        if draft.sql is None or not re.match(r"^SELECT\b", draft.sql, flags=re.IGNORECASE):
            raise AgentError("NL2SQL 只能生成 SELECT 候选")
        # 此处只有候选格式检查，不是 SQL 安全解析器。SQL 的实际表、字段、
        # 多语句/副作用、行权限、资源限制必须由后端 AST 校验器检查。
        # 本包没有数据库连接/执行路径，绝不能直接传给原 nl2sql_query 执行。
        return AgentResult(data=SQLCandidate(**draft.model_dump()), workflow_run_id=run_id)
