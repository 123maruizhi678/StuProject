"""调用已发布的学生请假Dify Workflow；不执行数据库写入。"""
import json

import httpx
from pydantic import ValidationError

from app.config import student_leave_dify_settings
from app.schemas.student_leave import DifyLeaveContent, LeaveAnalysis


class StudentLeaveDifyError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


class StudentLeaveDifyClient:
    def __init__(self, config=None, transport=None):
        self.config = config or student_leave_dify_settings
        self.transport = transport

    def analyze_leave(self, student_id, payload):
        key = self.config.STUDENT_DIFY_LEAVE_KEY.get_secret_value()
        if not key:
            raise StudentLeaveDifyError(503, "请假Dify工作流尚未配置")
        request_body = {
            "inputs": {
                "leave_content": payload.leave_content,
                "leave_type": payload.leave_type,
                "leave_start_at": payload.leave_start_at.isoformat(),
                "leave_end_at": payload.leave_end_at.isoformat(),
            },
            "response_mode": "blocking",
            "user": f"student-{student_id}",
        }
        try:
            with httpx.Client(
                timeout=httpx.Timeout(self.config.STUDENT_DIFY_LEAVE_TIMEOUT, connect=5),
                transport=self.transport, trust_env=False, follow_redirects=False,
            ) as client:
                response = client.post(
                    str(self.config.STUDENT_DIFY_LEAVE_BASE).rstrip("/") + "/workflows/run",
                    json=request_body, headers={"Authorization": f"Bearer {key}"},
                )
                response.raise_for_status()
        except httpx.TimeoutException:
            raise StudentLeaveDifyError(503, "请假AI分析超时") from None
        except httpx.HTTPStatusError:
            raise StudentLeaveDifyError(502, "请假Dify工作流返回异常") from None
        except httpx.RequestError:
            raise StudentLeaveDifyError(503, "请假Dify工作流暂不可用") from None
        try:
            envelope = response.json()
            data = envelope["data"]
            if data["status"] != "succeeded":
                raise ValueError("workflow not succeeded")
            result = data["outputs"]["result"]
            content = DifyLeaveContent.model_validate(
                json.loads(result) if isinstance(result, str) else result
            )
            run_id = envelope.get("workflow_run_id") or data.get("id")
            return LeaveAnalysis(
                **content.model_dump(), workflow_run_id=run_id,
                analysis_version=self.config.STUDENT_DIFY_LEAVE_VERSION,
            )
        except (ValueError, TypeError, KeyError, ValidationError):
            raise StudentLeaveDifyError(502, "请假AI结果不符合约定") from None


def get_leave_workflow():
    return StudentLeaveDifyClient()
