"""唯一学生助手 Workflow 客户端。所有模型能力共用同一个应用和专用 Key。"""
import json
from datetime import datetime, timezone
import httpx
from pydantic import ValidationError
from app.config import settings as student_settings
from app.core.common.response import BusinessException
from app.schemas.student.student import ChatDecision, TicketSummary

class StudentAssistantDifyClient:
    def __init__(self, config=None, transport=None):
        self.config = config or student_settings
        self.transport = transport

    def run(self, message, actor, *, mode='chat', history=None, context=None, knowledge=None):
        key = self.config.STUDENT_DIFY_KEY.get_secret_value()
        if not key:
            raise BusinessException('学生助手尚未配置唯一 Workflow 的 STUDENT_DIFY_KEY',503)
        payload = {'inputs': {'message':message,'mode':mode,
            'history':json.dumps(history or [],ensure_ascii=False),
            'context':json.dumps(context or {},ensure_ascii=False,default=str),
            'knowledge':json.dumps(knowledge or [],ensure_ascii=False),
            'current_time':datetime.now(timezone.utc).isoformat()},
            'response_mode':'blocking','user':actor.key}
        try:
            from app.core.common.dify import DifyHttpClient
            envelope = DifyHttpClient(self.config.DIFY_API_BASE,
                self.config.DIFY_API_TIMEOUT_SECONDS, transport=self.transport).post_json_sync(
                    '/workflows/run', api_key=key, payload=payload)
            data=envelope['data']
            if data['status']!='succeeded':
                raise ValueError('workflow_failed')
            value=data['outputs']['result']
            decision=ChatDecision.model_validate(json.loads(value) if isinstance(value,str) else value)
            run_id=envelope.get('workflow_run_id') or data.get('id')
            if not isinstance(run_id,str) or not 1<=len(run_id)<=128:
                raise ValueError('missing_run_id')
            decision.mental.workflow_run_id=run_id
            return decision,run_id
        except (httpx.HTTPError,ValueError,TypeError,KeyError,ValidationError):
            raise BusinessException('学生助手模型暂不可用或输出不符合约定',503) from None

    def mental(self,text,actor):
        decision,_=self.run(text,actor,mode='mental')
        return decision.mental

    def ticket(self,text,actor):
        decision,run_id=self.run(text,actor,mode='summary')
        if not decision.summary:
            raise BusinessException('学生助手未返回投诉摘要',503)
        return TicketSummary(summary=decision.summary,workflow_run_id=run_id,category='other')

class TicketWorkflowAdapter:
    def __init__(self, client=None):
        self.client=client or StudentAssistantDifyClient()
    def summarize(self,student_id,payload):
        from app.core.student.student_auth import Principal
        from app.schemas.student.student_ticket import TicketAnalysis
        from app.clients.student.student_ticket_dify import StudentTicketDifyError
        try:
            result=self.client.ticket(payload.content,Principal('student',student_id))
            return TicketAnalysis(summary=result.summary,suggested_category=result.category,
                workflow_run_id=result.workflow_run_id,analysis_version=student_settings.STUDENT_ANALYSIS_VERSION)
        except BusinessException:
            raise StudentTicketDifyError('assistant_summary_unavailable') from None

class LeaveWorkflowAdapter:
    def analyze_leave(self,student_id,payload):
        from app.core.student.student_auth import Principal
        from app.schemas.student.student_leave import LeaveAnalysis
        from app.clients.student.student_leave_dify import StudentLeaveDifyError
        try:
            result=StudentAssistantDifyClient().ticket(payload.leave_content,Principal('student',student_id))
            return LeaveAnalysis(summary=result.summary[:200],review_points=[],workflow_run_id=result.workflow_run_id,
                analysis_version=student_settings.STUDENT_ANALYSIS_VERSION)
        except BusinessException:
            raise StudentLeaveDifyError(503,'学生助手摘要不可用') from None

def get_ticket_workflow():
    return TicketWorkflowAdapter()
def get_leave_workflow():
    return LeaveWorkflowAdapter()
