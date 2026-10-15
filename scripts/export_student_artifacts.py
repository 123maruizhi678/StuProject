"""从当前学生路由和模型导出交接材料；不连接数据库。"""

import contextlib
import io
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy.dialects.mysql import dialect
from app.main import app
from app.models.student import STUDENT_TABLES
from app.models.student_shared import student_leave_request
from scripts.init_student_tables import dry_run

ROOT = Path(__file__).resolve().parents[1]
api_dir = ROOT / "业务文档/04接口设计"
sql_dir = ROOT / "scripts/sql/学生智能助手"
api_dir.mkdir(parents=True, exist_ok=True)


def main():
    schema = app.openapi()
    schema["info"][
        "description"
    ] = "学生助手后端与企业协作接口。HTTP200统一信封，以业务code判断结果。"
    student_schema = {
        **schema,
        "paths": {
            p: v
            for p, v in schema["paths"].items()
            if p.startswith(("/api/v1/student", "/api/v1/internal/student"))
        },
    }
    enterprise_schema = {
        **student_schema,
        "paths": {
            p: v
            for p, v in student_schema["paths"].items()
            if p.startswith("/api/v1/internal/student")
        },
    }
    for name, data in (
        ("学生助手_OpenAPI.json", student_schema),
        ("学生助手_企业侧_OpenAPI.json", enterprise_schema),
    ):
        (api_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        dry_run()
    (sql_dir / "学生智能助手_建表草案.sql").write_text(
        "-- V3 2026-10-15：五张学生专属表 + 公共请假表。已有库请用初始化脚本预检，禁止重复执行DROP或重建。\n"
        + "\n".join(line.rstrip() for line in buffer.getvalue().splitlines())
        + "\n",
        encoding="utf-8",
    )
    header = """# 学生智能助手建表方案 V3

2026-10-15。学生模块五张专属表，加上一张与企业共用的请假表，共六张业务表；学生/员工身份、归属、工单、通知和操作记录继续复用公共表。

- 私有表时间沿用组长现有DATETIME(6)，共享请假等企业表沿用DATETIME(3)，全部按UTC存储。
- mental_warning使用组长现有version字段；API统一返回row_version并接收expected_version。
- student_academic_reminder沿用原有字段，不增加row_version；用微秒updated_at标识设置代次，任务状态更新保留该时间，使取消后重新开启的旧消息失效。
- 公共请假student_leave_request直接复用企业DDL。学生提交/撤回，企业老师调用同一学生业务服务审批，两端使用同一leave_request_id。apply_id是API别名。
- student_profile.crm_student_id是CRM身份；external_student_id是教务身份，不能混用。组长实库已提供该列，仓库旧企业DDL未提供；集成到其他库时请由公共表维护者补迁移。本地专用开发实例自动补该列。
- 主键有符号BIGINT。主表先存在；组合外键保证预警/画像、提醒/节点属于同一学生。

初始化：python scripts/init_student_tables.py --check，然后--apply。只创建缺失的五张专属表与公共请假表；不删除数据、不自动修改已有结构。默认启动Web不建表。已有约束不一致会停止，需单独迁移。

## 字段字典

"""
    lines = [header]
    mysql = dialect()
    for table in (*STUDENT_TABLES, student_leave_request):
        lines += [
            f"### {table.name}\n",
            "| 字段 | MySQL类型 | 可空 | 主键 | 说明 |",
            "|---|---|---|---|---|",
        ]
        for col in table.columns:
            lines.append(
                f"| {col.name} | {col.type.compile(dialect=mysql)} | {'是' if col.nullable else '否'} | {'是' if col.primary_key else ''} | {(col.comment or '').replace('|','/')} |"
            )
        lines.append("")
    lines += [
        "## 与组长实际结构对照",
        "",
        "对照依据为用户提供的MySQL8.0.44诊断输出，未继续连接组长数据库。已对齐五张学生表字段、DATETIME(6)、预警version和提醒无版本列；输出中缺少student_leave_request，现已纳入学生交付，在本地创建。完整外键、CHECK及索引未出现在该输出中，不能据此声称组长约束已全部核验。",
        "",
        "既有V1独立身份/请假/工单/通知/操作表草案不再执行。公共表权威DDL仍是企业智能助手_建表.sql；本工具未修改企业SQL。",
    ]
    (sql_dir / "学生智能助手_建表方案.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    methods = {"get", "post", "delete", "patch", "put"}
    entries = []
    bodies = {
        "teacher_leave_decision": {
            "expected_version": 1,
            "decision": "approved",
            "comment": "同意请假",
        },
        "ack_warning": {"expected_version": 1, "note": "已接手，准备联系学生"},
        "follow_warning": {"expected_version": 2, "note": "已联系并记录跟进情况"},
        "close_warning": {"expected_version": 3, "note": "人工跟进已完成"},
        "sync_academic": {"student_id": 1, "source_system": "education", "records": []},
        "sync_progress": {"student_id": 1, "source_system": "crm", "records": []},
        "pull_source": {"student_id": 1},
    }
    for path, operations in enterprise_schema["paths"].items():
        for method, op in operations.items():
            if method not in methods:
                continue
            url = path
            import re

            url = re.sub(r"{(\w+)}", lambda m: "{{" + m[1] + "}}", url)
            url = "{{base_url}}" + url
            token = "service_token" if "/sync/" in path else "employee_token"
            headers = [{"key": "Content-Type", "value": "application/json"}]
            if method != "get":
                headers.append(
                    {"key": "Idempotency-Key", "value": "{{idempotency_key}}"}
                )
            request = {
                "method": method.upper(),
                "header": headers,
                "auth": {
                    "type": "bearer",
                    "bearer": [
                        {"key": "token", "value": "{{" + token + "}}", "type": "string"}
                    ],
                },
                "url": url,
            }
            name = op["operationId"].split("_api_v1")[0]
            if name in bodies:
                request["body"] = {
                    "mode": "raw",
                    "raw": json.dumps(bodies[name], ensure_ascii=False, indent=2),
                    "options": {"raw": {"language": "json"}},
                }
            entries.append({"name": method.upper() + " " + path, "request": request})
    collection = {
        "info": {
            "name": "学生助手-企业协作接口",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "description": "重试同一次写入时复用原Idempotency-Key；首次独立动作使用新键。实例ID仅占位，请按真实记录修改。",
        },
        "variable": [
            {"key": k, "value": v}
            for k, v in {
                "base_url": "http://127.0.0.1:8010",
                "employee_token": "",
                "service_token": "",
                "idempotency_key": "replace-with-a-new-uuid",
                "apply_id": "1",
                "warning_id": "1",
                "notification_id": "1",
                "kind": "academic",
            }.items()
        ],
        "item": entries,
    }
    (api_dir / "学生助手_企业侧_Postman.json").write_text(
        json.dumps(collection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with zipfile.ZipFile(
        api_dir / "学生助手_企业侧交接.zip", "w", zipfile.ZIP_DEFLATED
    ) as archive:
        for name in (
            "学生助手_数据表与接口简要说明.md",
            "学生助手_企业侧对接.md",
            "学生助手_企业侧_OpenAPI.json",
            "学生助手_企业侧_Postman.json",
        ):
            archive.write(api_dir / name, arcname=name)
    print(
        json.dumps(
            {
                "student_operations": sum(
                    sum(m in methods for m in ops)
                    for ops in student_schema["paths"].values()
                ),
                "enterprise_operations": len(entries),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
