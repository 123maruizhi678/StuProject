"""NL2SQL Dify Workflow 适配器：负责业务输入映射和 SQL 输出校验。"""

from app.config import settings
from app.core.dify import DifyHttpClient


class NL2SQLDifyClient:
    """将自然语言查询请求转换为 NL2SQL Workflow 契约。"""

    def __init__(self, http: DifyHttpClient | None = None) -> None:
        self.http = http or DifyHttpClient(
            settings.DIFY_API_BASE,
            timeout=settings.DIFY_API_TIMEOUT_SECONDS,
        )

    async def generate_sql(self, question: str, user: str = "stuproject") -> str:
        api_key = settings.DIFY_NL2SQL_API_KEY or settings.DIFY_API_KEY
        if not api_key:
            raise RuntimeError("未配置 NL2SQL Dify 应用 API Key")

        response = await self.http.post_json(
            "/workflows/run",
            api_key=api_key,
            payload={
                "inputs": {"question": question},
                "response_mode": "blocking",
                "user": user,
            },
        )
        data = response.get("data")
        if not isinstance(data, dict) or data.get("status") != "succeeded":
            raise ValueError("NL2SQL Dify Workflow 未成功完成")
        outputs = data.get("outputs")
        output_key = settings.DIFY_NL2SQL_OUTPUT_KEY or settings.DIFY_SQL_OUTPUT_KEY
        sql = outputs.get(output_key) if isinstance(outputs, dict) else None
        if not isinstance(sql, str) or not sql.strip():
            raise ValueError(f"NL2SQL Workflow 输出缺少有效字段 '{output_key}'")
        return sql.strip()