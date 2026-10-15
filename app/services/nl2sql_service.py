"""NL2SQL 业务服务：经专用 Dify 适配器生成 SQL，再按策略执行查询。"""

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text

from app.clients.nl2sql_dify import NL2SQLDifyClient
from app.core.response import ResultCode, fail, success
from app.database import engine


async def nl2sql_query(question: str, read_only: bool = True) -> dict:
    """自然语言转 SQL 并执行，返回统一信封中的 SQL 和结果行。"""
    try:
        sql = await NL2SQLDifyClient().generate_sql(question)
    except Exception as e:
        return fail(ResultCode.SERVER_ERROR, f"Dify 调用失败: {e}")

    # 此处是 NL2SQL 业务策略，不属于通用 HTTP 客户端。
    if read_only and not sql.strip().lower().startswith("select"):
        return fail(
            ResultCode.PARAM_ERROR,
            "仅允许查询类(SELECT)语句",
            data={"sql": sql},
        )

    def _execute():
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            return [dict(row) for row in result.mappings().all()]

    try:
        rows = await run_in_threadpool(_execute)
    except Exception as e:
        return fail(ResultCode.SERVER_ERROR, f"SQL 执行失败: {e}", data={"sql": sql})

    return success(data={"sql": sql, "rows": rows})