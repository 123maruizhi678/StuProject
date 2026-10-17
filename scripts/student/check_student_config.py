"""只读检查学生功能配置是否齐备；不连接数据库、调用模型或输出配置值。"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check_config(config):
    """返回缺失字段名称与原因，不返回密钥、连接信息或学生名单。"""
    issues = []

    def require(condition, field, reason):
        if not condition:
            issues.append({"field": field, "reason": reason})

    require(len(config.AUTH_SECRET_KEY.encode()) >= 32,
            "AUTH_SECRET_KEY", "公共登录需要至少32字节签名密钥")
    require(len(config.STUDENT_ACTION_SECRET.encode()) >= 32,
            "STUDENT_ACTION_SECRET", "会话和操作确认需要至少32字节独立签名密钥")
    require(bool(config.STUDENT_DIFY_KEY.get_secret_value().strip()),
            "STUDENT_DIFY_KEY", "完整助手能力需要唯一学生 Workflow 的应用密钥")
    require(bool(config.DIFY_API_BASE.strip()), "DIFY_API_BASE", "需要公共 Dify API 地址")
    require(config.ACCESS_CONTROL_FILE.is_file(), "ACCESS_CONTROL_FILE", "权限策略文件不存在")
    require(config.STUDENT_KNOWLEDGE_FILE.is_file(), "STUDENT_KNOWLEDGE_FILE", "知识配置文件不存在")
    if config.STUDENT_QUERY_BACKEND == "local":
        require(config.STUDENT_COURSES_FILE.is_file(), "STUDENT_COURSES_FILE", "课程与本人选课文件不存在")
    else:
        require(bool(config.STUDENT_NL2SQL_URL.strip()), "STUDENT_NL2SQL_URL", "group查询需要受控服务地址")
        require(bool(config.STUDENT_NL2SQL_TOKEN.strip()), "STUDENT_NL2SQL_TOKEN", "group查询需要服务凭据")
    if config.STUDENT_SYNC_ENABLED:
        require(len(config.STUDENT_SYNC_TOKEN.get_secret_value()) >= 32,
                "STUDENT_SYNC_TOKEN", "同步需要至少32字符独立服务凭据")
        require(bool(config.STUDENT_SYNC_ALLOWED_SOURCES), "STUDENT_SYNC_ALLOWED_SOURCES", "同步需要显式来源授权")
        require(bool(config.STUDENT_SYNC_ALLOWED_STUDENT_IDS), "STUDENT_SYNC_ALLOWED_STUDENT_IDS", "同步需要显式学生范围")
    return {"ready": not issues, "query_backend": config.STUDENT_QUERY_BACKEND,
            "external_sync_enabled": config.STUDENT_SYNC_ENABLED, "issues": issues}


def main():
    from pydantic import ValidationError
    try:
        from app.config import settings
        result = check_config(settings)
    except ValidationError as exc:
        # Pydantic 原始错误可能包含输入值，禁止直接打印。
        result = {"ready": False, "issues": [
            {"field": ".".join(map(str, error["loc"])), "reason": error["type"]}
            for error in exc.errors()
        ]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
