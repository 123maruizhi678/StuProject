"""真实 HTTP → 专用 Dify Workflow → 授权 MySQL 查询联调；不写入业务记录。"""
from datetime import datetime, timezone
import json
from pathlib import Path

from dotenv import dotenv_values
import httpx


def run(base_url="http://127.0.0.1:8000"):
    root = Path(__file__).resolve().parents[2]
    config = dotenv_values(root / ".env")
    results = []
    with httpx.Client(base_url=base_url, timeout=90) as client:
        login = client.post("/api/v1/auth/login", json={
            "username": config["ENTERPRISE_TEST_USERNAME"],
            "password": config["ENTERPRISE_TEST_PASSWORD"],
        }).json()
        assert login["code"] == 0, "真实账号登录失败"
        headers = {"Authorization": "Bearer " + login["data"]["access_token"]}
        prefix = "/api/v1/enterprise"

        def fixed(path):
            result = client.get(prefix + path, headers=headers).json()
            assert result["code"] == 0, "固定接口读取失败"
            return result["data"]

        def query(name, question, expected_code=0):
            response = client.post(prefix + "/student-scores/nl-query", json={"question": question}, headers=headers)
            result = response.json()
            passed = response.status_code == 200 and result["code"] == expected_code
            record = {"case": name, "question": question, "http_status": response.status_code,
                      "code": result.get("code"), "passed": passed}
            if result.get("data") and isinstance(result["data"], dict):
                record["row_count"] = result["data"].get("row_count")
            results.append(record)
            assert passed, f"{name}: code={result.get('code')}, message={result.get('message')}"
            assert "sql" not in (result.get("data") or {}), "响应不应暴露SQL"
            return result.get("data")

        students = fixed("/students?student_no=EIT-S001")
        assert students["total"] == 1
        selected = query("student-query", "查询学号 EIT-S001 的学生，只返回 student_no 和 full_name")
        assert selected["row_count"] == 1 and selected["rows"][0]["student_no"] == "EIT-S001"
        assert selected["rows"][0]["full_name"] == students["items"][0]["full_name"]

        scores = fixed("/scores?student_id=910001&course_code=EIT-ENGLISH&status=valid")
        selected = query("score-query", "查询学号 EIT-S001、课程 EIT-ENGLISH 的有效成绩，只返回 score_id、student_no、score_value、max_score")
        assert selected["row_count"] == scores["total"]
        actual = {row["score_id"]: row for row in selected["rows"]}
        from decimal import Decimal
        for row in scores["items"]:
            assert Decimal(str(actual[row["score_id"]]["score_value"])) == Decimal(row["score_value"])

        scores_all = fixed("/scores?course_code=EIT-ENGLISH&status=valid")
        aggregate = query("authorized-count", "统计当前授权范围内课程 EIT-ENGLISH 的有效成绩条数，返回总条数")
        assert aggregate["row_count"] == 1
        assert int(next(iter(aggregate["rows"][0].values()))) == scores_all["total"]

        query("write-refused", "把学号 EIT-S001 的英语成绩改成100分，直接更新数据库", expected_code=400)
        unchanged = fixed("/scores?student_id=910001&course_code=EIT-ENGLISH&status=valid")
        assert unchanged == scores, "只读请求不得更改成绩"
        results.append({"case": "grade-values-and-versions-unchanged", "passed": True})

    report = {"tested_at": datetime.now(timezone.utc).isoformat(), "api_base": base_url,
        "dify_base": config.get("STUDENT_SCORE_DIFY_BASE"), "database": "education_agent",
        "dify_app_id": "516a21f8-2658-4475-b297-83fc523b4ee4", "workflow_published": True,
        "real_model_http_chain": True, "business_writes": False, "checks": results}
    Path(__file__).with_name("nl2sql_e2e_results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    run()
