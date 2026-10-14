"""NL2SQL 通用工具：自然语言 → Dify 工作流 → SQL → 本地 MySQL 执行。

对外提供 nl2sql_query()，任意函数/路由均可调用。返回统一格式：
    {"code": 0, "message": "success", "data": {"sql": ..., "rows": [...]}}
"""
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text

from app.core.dify import call_nl2sql
from app.core.response import ResultCode, fail, success
from app.database import engine


async def nl2sql_query(question: str, read_only: bool = True) -> dict:
    """通用入口：自然语言问题转为 SQL 并在本地库执行，返回统一信封。

    Args:
        question: 自然语言问题
        read_only: 为 True 时仅允许 SELECT，防止破坏性语句
    """
    # 1. 调用 Dify 取得 SQL
    try:
        sql = await call_nl2sql(question)
    except Exception as e:
        return fail(ResultCode.SERVER_ERROR, f"Dify 调用失败: {e}")

    # 2. 安全校验：只读模式下仅允许 SELECT
    if read_only and not sql.strip().lower().startswith("select"):
        return fail(
            ResultCode.PARAM_ERROR,
            "仅允许查询类(SELECT)语句",
            data={"sql": sql},
        )

    # 3. 在本地 MySQL 同步执行（放到线程池，避免阻塞事件循环）
    def _execute():
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            return [dict(row) for row in result.mappings().all()]

    try:
        rows = await run_in_threadpool(_execute)
    except Exception as e:
        return fail(ResultCode.SERVER_ERROR, f"SQL 执行失败: {e}", data={"sql": sql})

    return success(data={"sql": sql, "rows": rows})
