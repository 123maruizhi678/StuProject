"""学生模块外部适配器。默认只走真实配置；测试通过依赖注入使用模拟适配器。"""

import json
import httpx
from fastapi import Depends
from app.database import get_db
from pydantic import ValidationError
from app.config import settings
from app.core.response import BusinessException
from app.core.student_auth import sign_token, verify_token
from app.schemas.student import MentalAssessment, TicketSummary, ChatDecision

MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def request_json(method, url, token, *, payload=None, params=None):
    if not url or not token:
        raise BusinessException("外部服务尚未配置", 503)
    try:
        with httpx.Client(
            timeout=settings.STUDENT_HTTP_TIMEOUT, follow_redirects=False
        ) as client:
            with client.stream(
                method,
                url,
                headers={"Authorization": "Bearer " + token},
                json=payload,
                params=params,
            ) as response:
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_RESPONSE_BYTES:
                        raise ValueError("response size")
                    chunks.append(chunk)
                result = json.loads(b"".join(chunks))
                if not isinstance(result, dict):
                    raise ValueError("response shape")
                return result
    except (httpx.HTTPError, ValueError, UnicodeError):
        raise BusinessException("外部服务不可用或返回格式不正确", 503) from None


def object_json(value):
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("\x60\x60\x60json") and value.endswith("\x60\x60\x60"):
            value = value[7:-3].strip()
        elif value.startswith("\x60\x60\x60") and value.endswith("\x60\x60\x60"):
            value = value[3:-3].strip()
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object")
    return value


class StudentDifyClient:
    def _workflow(self, key, text, actor):
        result = request_json(
            "POST",
            settings.DIFY_API_BASE.rstrip("/") + "/workflows/run",
            key,
            payload={
                "inputs": {"text": text},
                "response_mode": "blocking",
                "user": actor.key,
            },
        )
        data = result.get("data") or {}
        if data.get("status") != "succeeded":
            raise BusinessException("学生AI工作流未成功完成", 503)
        return object_json((data.get("outputs") or {}).get("result"))

    def mental(self, text, actor):
        try:
            return MentalAssessment.model_validate(
                self._workflow(settings.STUDENT_DIFY_MENTAL_KEY, text, actor)
            )
        except (ValidationError, ValueError, TypeError):
            raise BusinessException(
                "心理评估输出不符合约定，请稍后重试或联系老师", 503
            ) from None

    def ticket(self, text, actor):
        try:
            return TicketSummary.model_validate(
                self._workflow(settings.STUDENT_DIFY_TICKET_KEY, text, actor)
            )
        except (ValidationError, ValueError, TypeError):
            raise BusinessException("投诉摘要输出不符合约定", 503) from None

    def chat(self, body, actor):
        conversation_id = ""
        if body.conversation_token:
            claims = verify_token(body.conversation_token, "student-conversation")
            if claims.get("subject") != actor.key:
                raise BusinessException("会话不属于当前学生", 403)
            conversation_id = claims.get("conversation_id", "")
            if not isinstance(conversation_id, str) or len(conversation_id) > 128:
                raise BusinessException("会话凭证格式错误", 400)
        result = request_json(
            "POST",
            settings.DIFY_API_BASE.rstrip("/") + "/chat-messages",
            settings.STUDENT_DIFY_CHAT_KEY,
            payload={
                "inputs": {},
                "query": body.message,
                "response_mode": "blocking",
                "user": actor.key,
                "conversation_id": conversation_id,
            },
        )
        try:
            decision = ChatDecision.model_validate(object_json(result["answer"]))
            cid = result["conversation_id"]
            if not isinstance(cid, str) or not cid or len(cid) > 128:
                raise ValueError()
            token = sign_token(
                {"subject": actor.key, "conversation_id": cid},
                "student-conversation",
                86400,
            )
            resources = (result.get("metadata") or {}).get("retriever_resources") or []
            sources = [
                {
                    "document_name": r.get("document_name"),
                    "segment_id": r.get("segment_id"),
                }
                for r in resources[:20]
                if isinstance(r, dict)
                and isinstance(r.get("document_name"), str)
                and isinstance(r.get("segment_id"), str)
            ]
            return decision, token, sources
        except (ValidationError, ValueError, TypeError, KeyError):
            raise BusinessException("学生对话输出不符合约定", 503) from None


# 明确返回字段，避免把审计、心理预警、内部备注或生成的SQL交给学生。
QUERY_FIELDS = {
    "leave": {
        "student_id",
        "leave_request_id",
        "request_no",
        "leave_type",
        "start_at",
        "end_at",
        "reason",
        "status",
        "decision_at",
        "decision_comment",
        "row_version",
    },
    "tickets": {
        "student_id",
        "ticket_id",
        "ticket_no",
        "ticket_type",
        "category_code",
        "content",
        "ai_summary",
        "status",
        "solution",
        "resolved_at",
        "closed_at",
        "satisfaction_score",
        "row_version",
    },
    "ticket_records": {
        "student_id",
        "ticket_id",
        "ticket_record_id",
        "record_type",
        "content",
        "visibility",
        "to_status",
        "cycle_no",
        "created_at",
    },
    "academic": {
        "student_id",
        "id",
        "event_type",
        "title",
        "due_at",
        "source_timezone",
        "event_status",
        "event_version",
        "source_updated_at",
        "synced_at",
    },
    "progress": {
        "student_id",
        "id",
        "application_name",
        "external_application_id",
        "stage_code",
        "stage_status",
        "detail",
        "source_updated_at",
        "synced_at",
    },
    "reminders": {
        "student_id",
        "id",
        "academic_event_id",
        "lead_minutes",
        "notify_at",
        "event_version",
        "status",
        "sent_at",
    },
    "notifications": {
        "student_id",
        "notification_id",
        "entity_type",
        "entity_id",
        "event_code",
        "channel",
        "title",
        "content",
        "delivery_status",
        "sent_at",
        "read_at",
        "created_at",
    },
}


class StudentQueryClient:
    def _request(self, payload):
        return request_json(
            "POST",
            settings.STUDENT_NL2SQL_URL,
            settings.STUDENT_NL2SQL_TOKEN,
            payload=payload,
        )

    def query(self, actor, scenario, *, entity_id=None, limit=20, offset=0):
        if scenario not in QUERY_FIELDS or actor.actor_type != "student":
            raise BusinessException("查询场景不允许", 403)
        payload = {
            "contract_version": "student-v1",
            "scenario": scenario,
            "subject": {"type": "student", "id": actor.actor_id},
            "filters": {"entity_id": entity_id},
            "limit": limit,
            "offset": offset,
        }
        result = self._request(payload)
        try:
            if result.get("code") != 0:
                raise ValueError()
            data = result["data"]
            rows = data["rows"]
            if (
                data.get("contract_version") != "student-v1"
                or data.get("subject_id") != actor.actor_id
                or data.get("scenario") != scenario
                or not isinstance(rows, list)
                or len(rows) > limit
            ):
                raise ValueError()
            from datetime import datetime, timezone

            clean = []
            id_field = {
                "leave": "leave_request_id",
                "tickets": "ticket_id",
                "ticket_records": "ticket_id",
                "notifications": "notification_id",
            }.get(scenario, "id")
            for row in rows:
                if not isinstance(row, dict) or row.get("student_id") != actor.actor_id:
                    raise ValueError()
                if entity_id is not None and row.get(id_field) != entity_id:
                    raise ValueError()
                if (
                    scenario == "ticket_records"
                    and row.get("visibility") != "student_visible"
                ):
                    raise ValueError()
                if scenario == "notifications" and (
                    row.get("delivery_status") != "sent"
                    or row.get("channel") != "in_app"
                ):
                    raise ValueError()
                item = {k: v for k, v in row.items() if k in QUERY_FIELDS[scenario]}
                if scenario in ("academic", "progress"):
                    synced = row.get("synced_at")
                    try:
                        when = (
                            datetime.fromisoformat(synced.replace("Z", "+00:00"))
                            if synced
                            else None
                        )
                        if when and when.tzinfo is None:
                            raise ValueError()
                        item["stale"] = not when or (
                            datetime.now(timezone.utc) - when
                        ).total_seconds() > 2 * max(
                            1, settings.STUDENT_SYNC_INTERVAL_SECONDS
                        )
                    except (AttributeError, TypeError):
                        raise ValueError()
                clean.append(item)
            total = data.get("total")
            if type(total) is not int or total < len(clean):
                raise ValueError()
            if entity_id is not None and not clean and scenario != "ticket_records":
                raise BusinessException("记录不存在", 404)
            return {"items": clean, "total": total, "limit": limit, "offset": offset}
        except (ValueError, KeyError, TypeError):
            raise BusinessException(
                "查询服务返回的数据范围或格式不符合约定", 503
            ) from None

    def warning(self, actor, warning_id, student_id):
        if actor.actor_type != "employee":
            raise BusinessException("需要老师身份", 403)
        response = self._request(
            {
                "contract_version": "student-v1",
                "scenario": "mental_warning",
                "subject": {"type": "employee", "id": actor.actor_id},
                "filters": {"warning_id": warning_id, "student_id": student_id},
                "limit": 1,
                "offset": 0,
            }
        )
        try:
            data = response["data"]
            rows = data["rows"]
            if (
                response.get("code") != 0
                or data.get("contract_version") != "student-v1"
                or data.get("subject_id") != actor.actor_id
                or data.get("scenario") != "mental_warning"
                or not isinstance(rows, list)
                or len(rows) > 1
            ):
                raise ValueError()
            if not rows:
                raise BusinessException("记录不存在", 404)
            row = rows[0]
            if (
                not isinstance(row, dict)
                or row.get("id") != warning_id
                or row.get("student_id") != student_id
            ):
                raise ValueError()
            allowed = {
                "id",
                "student_id",
                "trigger_reason",
                "risk_level",
                "follower_status",
                "follower_id",
                "acknowledged_at",
                "closed_at",
                "handling_result",
                "version",
                "row_version",
                "created_at",
            }
            result = {k: v for k, v in row.items() if k in allowed}
            if "version" in result:
                result["row_version"] = result.pop("version")
            return result
        except (KeyError, TypeError, ValueError):
            raise BusinessException("预警查询返回范围或格式不符合约定", 503) from None


class StudentSourceClient:
    def fetch(self, kind, student):
        identity_field = (
            "external_student_id" if kind == "academic" else "crm_student_id"
        )
        identity = student[identity_field]
        if not identity:
            raise BusinessException("学生外部身份尚未绑定", 409)
        url = (
            settings.STUDENT_EDUCATION_URL
            if kind == "academic"
            else settings.STUDENT_CRM_URL
        )
        token = (
            settings.STUDENT_EDUCATION_TOKEN
            if kind == "academic"
            else settings.STUDENT_CRM_TOKEN
        )
        data = request_json("GET", url, token, params={identity_field: identity})
        if data.get(identity_field) != identity:
            raise BusinessException("外部身份映射不匹配", 503)
        return data


def get_dify():
    return StudentDifyClient()


def get_query_client(db=Depends(get_db)):
    if settings.STUDENT_QUERY_BACKEND == "local":
        from app.services.student_local_query import LocalStudentQueryClient

        return LocalStudentQueryClient(db)
    return StudentQueryClient()


def get_source_client():
    return StudentSourceClient()
