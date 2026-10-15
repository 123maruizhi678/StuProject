"""智能体输入/输出契约。Context 和所有业务资料必须由可信后端构造。"""

from datetime import date
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import (
    AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, StrictFloat,
    StrictInt, StrictStr, model_validator,
)

Id = Annotated[str, Field(pattern=r"^[1-9][0-9]*$", max_length=20)]
Name = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
Text = Annotated[str, Field(min_length=1, max_length=10000)]
Scalar = StrictStr | StrictInt | StrictFloat | StrictBool | None
Role = Literal["employee", "consultant", "manager", "teacher", "academic", "admin"]
Route = Literal["query", "command", "knowledge", "general", "clarify"]
Task = Literal["chat", "command", "daily_prepare", "daily_summary", "knowledge", "nl2sql"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class ActorContext(Model):
    subject: str = Field(min_length=1, max_length=128)
    role_codes: list[Role] = Field(min_length=1, max_length=6)
    now: AwareDatetime
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"


T = TypeVar("T")


class AgentResult(Model, Generic[T]):
    data: T
    workflow_run_id: str | None = None


class Turn(Model):
    role: Literal["user", "assistant"]
    content: Text


class ChatRequest(Model):
    message: Text
    history: list[Turn] = Field(default_factory=list, max_length=12)
    allowed_routes: list[Route] = Field(default_factory=lambda: ["general", "clarify"], max_length=5)


class ChatDecision(Model):
    route: Route
    reply: Text
    normalized_request: str = Field(default="", max_length=10000)


class ParameterRule(Model):
    description: str = Field(min_length=1, max_length=500)
    value_type: Literal["string", "integer", "number", "boolean", "date", "datetime"] = "string"
    required: bool = False
    choices: list[Scalar] = Field(default_factory=list, max_length=50)
    min_length: int = Field(default=0, ge=0, le=10000)
    max_length: int = Field(default=5000, ge=1, le=10000)
    minimum: float | None = None
    maximum: float | None = None

    @model_validator(mode="after")
    def bounds(self):
        if self.min_length > self.max_length:
            raise ValueError("min_length must not exceed max_length")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum must not exceed maximum")
        return self


class ActionSpec(Model):
    name: Name
    description: str = Field(min_length=1, max_length=1000)
    entity_type: Name | None = None
    requires_target: bool = False
    fields: dict[Name, ParameterRule] = Field(default_factory=dict, max_length=30)

    @model_validator(mode="after")
    def target_kind(self):
        if self.requires_target and not self.entity_type:
            raise ValueError("target action requires entity_type")
        reserved = {"sql", "raw_sql", "table_name", "actor_id", "operator_id", "role_codes", "permissions", "expected_version"}
        if reserved.intersection(self.fields):
            raise ValueError("action fields contain reserved execution/identity fields")
        return self


class Candidate(Model):
    ref: str = Field(min_length=1, max_length=100)
    entity_type: Name
    entity_id: Id
    display_name: str = Field(min_length=1, max_length=300)
    version: int = Field(ge=1)


class CommandRequest(Model):
    command: Text
    actions: list[ActionSpec] = Field(default_factory=list, max_length=50)
    candidates: list[Candidate] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def unique_catalogs(self):
        for values in ([a.name for a in self.actions], [c.ref for c in self.candidates]):
            if len(values) != len(set(values)):
                raise ValueError("action names and candidate refs must be unique")
        return self


class CommandDraft(Model):
    action: Name | None
    target_ref: str | None = Field(default=None, max_length=100)
    parameters: dict[Name, Scalar] = Field(default_factory=dict, max_length=30)
    explanation: Text


class CommandProposal(Model):
    status: Literal["proposed", "needs_clarification", "unsupported"]
    action: Name | None = None
    target: Candidate | None = None
    parameters: dict[str, Scalar] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list)
    message: Text
    requires_confirmation: bool = False


class DailyPrepareRequest(Model):
    report_date: date
    text: Text


class DailyDraft(Model):
    proposed_content: Text
    ai_summary: str = Field(min_length=1, max_length=3000)
    work_items: list[Text] = Field(default_factory=list, max_length=50)
    outputs: list[Text] = Field(default_factory=list, max_length=50)
    risks: list[Text] = Field(default_factory=list, max_length=50)
    next_plans: list[Text] = Field(default_factory=list, max_length=50)


class DailyPrepared(DailyDraft):
    report_date: date
    requires_confirmation: Literal[True] = True


class SubmittedReport(Model):
    daily_report_id: Id
    employee_id: Id
    report_date: date
    submitted_content: Text
    version: int = Field(ge=1)
    status: Literal["submitted"] = "submitted"


class SummaryRequest(Model):
    start_date: date
    end_date: date
    reports: list[SubmittedReport] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def report_window(self):
        if self.start_date > self.end_date:
            raise ValueError("invalid report date range")
        ids = [r.daily_report_id for r in self.reports]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate report IDs")
        if any(not self.start_date <= r.report_date <= self.end_date for r in self.reports):
            raise ValueError("report falls outside requested date range")
        return self


class SummaryPoint(Model):
    text: Text
    source_ids: list[Id] = Field(min_length=1, max_length=200)


class SummaryDraft(Model):
    progress: list[SummaryPoint] = Field(default_factory=list, max_length=50)
    outputs: list[SummaryPoint] = Field(default_factory=list, max_length=50)
    risks: list[SummaryPoint] = Field(default_factory=list, max_length=50)
    next_plans: list[SummaryPoint] = Field(default_factory=list, max_length=50)


class ReportSource(Model):
    daily_report_id: Id
    employee_id: Id
    version: int


class DailySummary(SummaryDraft):
    report_count: int
    sources: list[ReportSource]


class KnowledgeChunk(Model):
    ref: str = Field(min_length=1, max_length=100)
    knowledge_id: Id
    content_version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=300)
    content: Text
    source_reference: str = Field(default="", max_length=512)


class KnowledgeRequest(Model):
    question: Text
    chunks: list[KnowledgeChunk] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def unique_chunks(self):
        refs = [c.ref for c in self.chunks]
        if len(refs) != len(set(refs)):
            raise ValueError("duplicate knowledge refs")
        versions: dict[str, int] = {}
        for chunk in self.chunks:
            if chunk.knowledge_id in versions and versions[chunk.knowledge_id] != chunk.content_version:
                raise ValueError("mixed versions of the same knowledge entry")
            versions[chunk.knowledge_id] = chunk.content_version
        return self


class KnowledgeDraft(Model):
    found: bool
    answer: Text
    source_refs: list[str] = Field(default_factory=list, max_length=30)


class KnowledgeSource(Model):
    ref: str
    knowledge_id: Id
    content_version: int
    title: str
    source_reference: str


class KnowledgeAnswer(Model):
    found: bool
    answer: Text
    sources: list[KnowledgeSource] = Field(default_factory=list)


class ViewSpec(Model):
    name: Name
    description: str = Field(min_length=1, max_length=2000)
    columns: dict[Name, str] = Field(min_length=1, max_length=100)


class NL2SQLRequest(Model):
    question: Text
    views: list[ViewSpec] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique_views(self):
        names = [v.name for v in self.views]
        if len(names) != len(set(names)):
            raise ValueError("duplicate view names")
        return self


class SQLDraft(Model):
    status: Literal["candidate", "needs_clarification"] = "candidate"
    view_name: Name | None = None
    sql: str | None = Field(default=None, min_length=1, max_length=20000)
    parameters: dict[Name, Scalar] = Field(default_factory=dict, max_length=50)
    clarification: str = Field(default="", max_length=1000)


class SQLCandidate(SQLDraft):
    requires_backend_validation: Literal[True] = True
