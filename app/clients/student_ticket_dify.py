"""投诉摘要工作流客户端：只交换原文和受控建议，不传JWT或数据库凭据。"""
import json

import httpx
from pydantic import ValidationError

from app.config import student_ticket_settings
from app.schemas.student_ticket import DifyTicketContent, TicketAnalysis


class StudentTicketDifyError(Exception):
    """可预期的外部失败，由业务层降级为摘要不可用。"""


class StudentTicketDifyClient:
    def __init__(self, config=None, transport=None):
        self.config = config or student_ticket_settings
        self.transport = transport

    def summarize(self, student_id, payload):
        key = self.config.STUDENT_DIFY_TICKET_KEY.get_secret_value()
        if not key:
            raise StudentTicketDifyError("workflow_not_configured")
        try:
            with httpx.Client(
                transport=self.transport, trust_env=False, follow_redirects=False,
                timeout=httpx.Timeout(self.config.STUDENT_DIFY_TICKET_TIMEOUT, connect=3),
            ) as client:
                response = client.post(
                    str(self.config.STUDENT_DIFY_TICKET_BASE).rstrip("/") + "/workflows/run",
                    json={"inputs": payload.model_dump(), "response_mode": "blocking",
                          "user": f"student-{student_id}"},
                    headers={"Authorization": f"Bearer {key}"},
                )
                response.raise_for_status()
        except httpx.HTTPError:
            raise StudentTicketDifyError("workflow_unavailable") from None
        try:
            envelope = response.json()
            data = envelope["data"]
            if data["status"] != "succeeded":
                raise ValueError("workflow_failed")
            result = data["outputs"]["result"]
            content = DifyTicketContent.model_validate(json.loads(result) if isinstance(result, str) else result)
            return TicketAnalysis(**content.model_dump(),
                                  workflow_run_id=envelope.get("workflow_run_id") or data.get("id"),
                                  analysis_version=self.config.STUDENT_DIFY_TICKET_VERSION)
        except (ValueError, TypeError, KeyError, ValidationError):
            raise StudentTicketDifyError("workflow_invalid_output") from None


def get_ticket_workflow():
    return StudentTicketDifyClient()
