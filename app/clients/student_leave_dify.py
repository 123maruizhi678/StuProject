"""学生请假 Dify Workflow 客户端。

契约见 dify/student_leave/README.md「后端调用契约」：
    POST {STUDENT_DIFY_LEAVE_BASE}/workflows/run
    inputs: leave_content / leave_type / leave_start_at / leave_end_at（字符串）
    user: 后端生成的 student-<业务学生ID>；正式请求的登录 Token 不转发给 Dify
    仅接受 data.status=succeeded；outputs.result 须符合 DifyLeaveContent
    workflow_run_id 取顶层值或 data.id；analysis_version 由本模块附加

错误映射（与接口层约定一致）：
    502 模型输出错误或工作流失败 / 输出不符合约定
    503 未配置专用 Key、超时或网络不可用
以上情况均不产生申请、通知或操作记录（由 service 层保证未提交）。
"""
import json

import httpx
from pydantic import ValidationError

from app.config import StudentLeaveDifySettings, student_leave_dify_settings
from app.schemas.student_leave import DifyLeaveContent, LeaveAnalysis, LeaveInput


class StudentLeaveDifyError(Exception):
    """请假工作流调用失败；status 为接口层使用的 HTTP 语义状态码。"""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(message)


class StudentLeaveDifyClient:
    """调用请假 Workflow，把请假理由整理为摘要与审批关注点。"""

    def __init__(
        self,
        settings: StudentLeaveDifySettings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        # settings / transport 可注入，便于测试替身，不影响生产路径
        self._settings = settings or student_leave_dify_settings
        self._transport = transport

    def analyze_leave(self, student_id: int, payload: LeaveInput) -> LeaveAnalysis:
        """调用工作流并严格校验输出，返回带版本信息的分析结果。"""
        secret = self._settings.STUDENT_DIFY_LEAVE_KEY.get_secret_value()
        if not secret:
            raise StudentLeaveDifyError(503, "请假工作流未配置专用 API Key")

        request_payload = {
            "inputs": {
                "leave_content": payload.leave_content,
                "leave_type": payload.leave_type,
                "leave_start_at": payload.leave_start_at.isoformat(),
                "leave_end_at": payload.leave_end_at.isoformat(),
            },
            "response_mode": "blocking",
            "user": f"student-{student_id}",
        }
        headers = {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}
        url = f"{self._settings.STUDENT_DIFY_LEAVE_BASE.rstrip('/')}/workflows/run"

        try:
            with httpx.Client(
                timeout=self._settings.STUDENT_DIFY_LEAVE_TIMEOUT,
                transport=self._transport,
                trust_env=False,
                follow_redirects=False,
            ) as client:
                response = client.post(url, json=request_payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as error:
            raise StudentLeaveDifyError(503, "请假工作流调用超时") from error
        except httpx.HTTPError as error:
            raise StudentLeaveDifyError(503, "请假工作流暂不可用") from error
        except ValueError as error:  # 响应非 JSON
            raise StudentLeaveDifyError(502, "请假工作流返回了无法解析的内容") from error

        run = data.get("data") or {}
        if run.get("status") != "succeeded":
            raise StudentLeaveDifyError(502, "请假工作流执行失败")

        outputs = run.get("outputs") or {}
        result = outputs.get("result")
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError as error:
                raise StudentLeaveDifyError(502, "请假工作流输出不是合法 JSON") from error
        try:
            content = DifyLeaveContent.model_validate(result)
        except ValidationError as error:
            raise StudentLeaveDifyError(502, "请假工作流输出不符合约定结构") from error

        run_id = data.get("workflow_run_id") or run.get("id") or ""
        if not run_id:
            raise StudentLeaveDifyError(502, "请假工作流未返回运行 ID")

        return LeaveAnalysis(
            **content.model_dump(),
            workflow_run_id=run_id,
            analysis_version=self._settings.STUDENT_DIFY_LEAVE_VERSION,
        )


def get_leave_workflow() -> StudentLeaveDifyClient:
    """FastAPI 依赖：提供请假工作流客户端（测试可覆盖此依赖注入替身）。"""
    return StudentLeaveDifyClient()
