"""学生请假 Dify Workflow 适配器：保留请假输入、结果校验和错误语义。"""
import json

import httpx
from pydantic import ValidationError

from app.config import settings, student_leave_dify_settings
from app.core.dify import DifyHttpClient
from app.schemas.student_leave import DifyLeaveContent, LeaveAnalysis


class StudentLeaveDifyError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


class StudentLeaveDifyClient:
    def __init__(self, config=None, transport=None, http=None):
        self.config = config or student_leave_dify_settings
        self.http = http or DifyHttpClient(
            api_base=settings.DIFY_API_BASE,
            timeout=self.config.STUDENT_DIFY_LEAVE_TIMEOUT,
            transport=transport,
        )

    @property
    def transport(self):
        """兼容依赖注入测试：访问底层 HTTPX transport。"""
        return self.http.transport

    @transport.setter
    def transport(self, value):
        self.http.transport = value
    def analyze_leave(self, student_id, payload):
        key = self.config.STUDENT_DIFY_LEAVE_KEY.get_secret_value()
        if not key:
            raise StudentLeaveDifyError(503, "请假Dify工作流尚未配置，申请未提交")
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
            envelope = self.http.post_json_sync(
                "/workflows/run", api_key=key, payload=request_body
            )
        except httpx.TimeoutException:
            raise StudentLeaveDifyError(503, "请假AI分析超时，申请未提交，请稍后重试") from None
        except httpx.HTTPStatusError:
            raise StudentLeaveDifyError(502, "请假Dify工作流返回异常，申请未提交") from None
        except ValueError:
            raise StudentLeaveDifyError(502, "请假Dify响应格式无效，申请未提交") from None
        except httpx.RequestError:
            raise StudentLeaveDifyError(503, "请假Dify工作流暂不可用，申请未提交") from None
        try:
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
            raise StudentLeaveDifyError(502, "请假AI结果不符合约定，申请未提交") from None


def get_leave_workflow():
    return StudentLeaveDifyClient()