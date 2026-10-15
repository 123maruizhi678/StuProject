"""NL2SQL 业务服务：通过通用 Dify Workflow 客户端生成并执行查询。"""

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text

from app.core.dify import run_workflow
from app.core.response import ResultCode, fail, success
from app.database import engine


async def nl2sql_query(question: str, read_only: bool = True) -> dict:
    """自然语言转 SQL 并执行，返回统一信封中的 SQL 和结果行。"""
    # 1. 选择 nl2sql 场景配置，运行对应 Dify Workflow 并提取 sql 输出。
    try:
        sql = await run_workflow("nl2sql", {"question": question})
    except Exception as e:
        return fail(ResultCode.SERVER_ERROR, f"Dify 调用失败: {e}")

    # 2. 现有只读保护为 SELECT 前缀检查；这不是完整 SQL 安全解析。
    if read_only and not sql.strip().lower().startswith("select"):
        return fail(
            ResultCode.PARAM_ERROR,
            "仅允许查询类(SELECT)语句",
            data={"sql": sql},
        )

    # 3. 在线程池同步访问数据库，避免阻塞异步事件循环。
    def _execute():
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            return [dict(row) for row in result.mappings().all()]

    try:
        rows = await run_in_threadpool(_execute)
    except Exception as e:
        return fail(ResultCode.SERVER_ERROR, f"SQL 执行失败: {e}", data={"sql": sql})

    return success(data={"sql": sql, "rows": rows})