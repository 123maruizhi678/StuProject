"""学生模块外部适配器。默认只走真实配置；测试通过依赖注入使用模拟适配器。"""

import json
import httpx
from fastapi import Depends
from app.database import get_db
from pydantic import ValidationError
from app.config import settings
from app.core.common.response import BusinessException
from app.core.student.student_auth import sign_token, verify_token
from app.schemas.student.student import MentalAssessment, TicketSummary, ChatDecision

MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def request_json(method, url, token, *, payload=None, params=None):
    if not url or not token:
        raise BusinessException("外部服务尚未配置", 503)
    try:
        with httpx.Client(
            timeout=settings.STUDENT_HTTP_TIMEOUT, follow_redirects=False, trust_env=False
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


# 明确返回字段，避免把审计、心理预警、内部备注或生成的SQL交给学生。
QUERY_FIELDS = {
    "courses": {"student_id","course_code","course_name","term_code","status"},
    "scores": {"student_id","score_id","course_code","term_code","assessment_code","attempt_no","score_value","max_score","status","row_version","updated_at"},
    "leave": {"apply_id","student_id","apply_type","apply_content","leave_type","approval_status","leave_start_at","leave_end_at","reviewer_id","reviewed_at","approval_comment","row_version","created_at","updated_at"},
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
        "employee_id", "handling_department_id", "reopen_count", "first_response_at", "response_due_at", "resolution_due_at",
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
        "source_system",
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
        "updated_at",
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

    def query(self, actor, scenario, *, entity_id=None, limit=20, offset=0, approval_status=None):
        if scenario not in QUERY_FIELDS or actor.actor_type != "student":
            raise BusinessException("查询场景不允许", 403)
        payload = {
            "contract_version": "student-v1",
            "scenario": scenario,
            "subject": {"type": "student", "id": actor.actor_id},
            "filters": {"entity_id": entity_id, "approval_status":approval_status},
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
                "leave": "apply_id",
                "scores": "score_id",
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
                if scenario in ("academic", "progress") and row.get("source_system") != "local":
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
            result["warning_id"]=result.pop("id")
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
    from app.clients.student.student_assistant_dify import StudentAssistantDifyClient
    return StudentAssistantDifyClient()


def get_query_client(db=Depends(get_db)):
    if settings.STUDENT_QUERY_BACKEND == "local":
        from app.services.student.student_local_query import LocalStudentQueryClient

        return LocalStudentQueryClient(db)
    return StudentQueryClient()


def get_source_client():
    return StudentSourceClient()
