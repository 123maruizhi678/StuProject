"""Dify 工作流 HTTP 客户端：调用 NL2SQL 工作流并提取配置的 SQL 输出变量。"""
import httpx

from app.config import settings


async def call_nl2sql(question: str, user: str = "stuproject") -> str:
    """调用 Dify NL2SQL 工作流，返回其输出中的 SQL 文本。

    Args:
        question: 自然语言问题
        user: Dify 侧的用户标识（用于会话/审计）
    Returns:
        工作流输出变量（DIFY_SQL_OUTPUT_KEY）中的 SQL 字符串
    Raises:
        ValueError: 输出中缺少配置的 SQL 变量
        httpx.HTTPStatusError: Dify 接口返回非 2xx
    """
    url = f"{settings.DIFY_API_BASE}/workflows/run"
    # Dify 工作流入参：承载自然语言问题的变量名（固定为 question）
    QUESTION_KEY = "question"
    payload = {
        "inputs": {QUESTION_KEY: question},
        "response_mode": "blocking",
        "user": user,
    }
    headers = {
        "Authorization": f"Bearer {settings.DIFY_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()["data"]
        outputs = data.get("outputs") or {}
        sql = outputs.get(settings.DIFY_SQL_OUTPUT_KEY)
        if not sql:
            raise ValueError(
                f"Dify 输出缺少 SQL 变量 '{settings.DIFY_SQL_OUTPUT_KEY}'"
            )
        return sql.strip()
