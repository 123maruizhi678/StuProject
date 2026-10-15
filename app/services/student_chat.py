"""Dify只提出业务动作；学生确认签名预览后，后端调用固定业务函数。"""

from app.services.student_service import digest
from pydantic import ValidationError
from app.config import settings
from app.core.response import BusinessException
from app.core.student_auth import sign_token, verify_token
from app.schemas.student import LeaveInput, TicketInput, ReminderInput

WRITE_ACTIONS = {
    "leave.submit": LeaveInput,
    "ticket.submit": TicketInput,
    "reminder.set": ReminderInput,
}
READ_ACTIONS = {
    "academic.query": "academic",
    "progress.query": "progress",
    "leave.query": "leave",
    "ticket.query": "tickets",
    "reminders.query": "reminders",
    "notifications.query": "notifications",
}


class StudentChatService:
    def __init__(self, service, dify, query):
        self.service, self.dify, self.query = service, dify, query

    def chat(self, actor, key, body):
        self.service.student(actor)
        decision, conversation, sources = self.dify.chat(body, actor)
        allowed = {
            "leave": {"none", "leave.submit", "leave.query"},
            "mental": {"none"},
            "feedback": {"none", "ticket.submit", "ticket.query"},
            "academic": {"none", "academic.query", "reminder.set", "reminders.query"},
            "progress": {"none", "progress.query"},
            "life": {"none"},
            "upgrade": {"none"},
        }
        if decision.action not in allowed[decision.intent]:
            raise BusinessException("AI动作与学生业务场景不一致", 503)
        if decision.intent in ("life", "upgrade") and not sources:
            decision.answer = "暂未检索到已确认的资料，请联系服务老师核实。"
        # 即使消息被分到生活/学业，也保存情绪评估，避免只监测mental分支。
        self.service.record_mental(actor, "chat:" + key, body.message, decision.mental)
        result = {
            "intent": decision.intent,
            "answer": decision.answer,
            "conversation_token": conversation,
            "sources": sources,
            "pending_action": None,
        }
        if decision.action in WRITE_ACTIONS:
            try:
                params = WRITE_ACTIONS[decision.action].model_validate(
                    decision.parameters
                )
            except ValidationError:
                raise BusinessException(
                    "AI提出的办理参数不完整，请补充或使用表单", 400
                ) from None
            claims = {
                "subject": actor.key,
                "action": decision.action,
                "parameters": params.model_dump(mode="json"),
                "jti": digest([actor.key, key])[:32],
            }
            token = sign_token(
                claims, "student-action", settings.STUDENT_ACTION_TTL_SECONDS
            )
            result["pending_action"] = {
                "action": decision.action,
                "parameters": claims["parameters"],
                "action_token": token,
            }
        elif decision.action in READ_ACTIONS:
            if decision.parameters:
                raise BusinessException("AI查询参数不符合场景约定", 400)
            self.service.student(actor)
            result["data"] = self.query.query(actor, READ_ACTIONS[decision.action])
        return result

    def confirm(self, actor, token):
        claims = verify_token(token, "student-action")
        if claims.get("subject") != actor.key:
            raise BusinessException("操作凭证不属于当前学生", 403)
        action = claims.get("action")
        if (
            action not in WRITE_ACTIONS
            or not isinstance(claims.get("jti"), str)
            or len(claims["jti"]) != 32
        ):
            raise BusinessException("不支持的业务动作", 400)
        try:
            params = WRITE_ACTIONS[action].model_validate(claims["parameters"])
        except (ValidationError, KeyError):
            raise BusinessException("操作参数无效", 400) from None
        # 以签名预览的jti去重；更换HTTP请求键也不能重复办理同一预览。
        key = "confirm:" + claims["jti"]
        if action == "leave.submit":
            return self.service.submit_leave(actor, key, params)
        if action == "reminder.set":
            return self.service.set_reminder(actor, key, params)
        summary = None
        try:
            summary = self.dify.ticket(params.complaint_content, actor)
        except BusinessException:
            pass  # 摘要不可用仍保留学生提交，不制造摘要。
        return self.service.submit_ticket(actor, key, params, summary)
