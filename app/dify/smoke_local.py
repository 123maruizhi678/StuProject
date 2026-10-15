"""通过真实 education_agent 和真实认证验证七项接口；仅写入 EIT 虚构学生的新测试成绩。"""
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import BASE_DIR
from app.database import SessionLocal, engine
from app.main import app
from app.models.enterprise_student import Employee, StudentProfile
from app.services.enterprise_nl2sql import execute_query

PREFIX = "/api/v1/enterprise"


def run():
    if engine.url.database != "education_agent" or engine.url.host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("只允许本机 education_agent 联调库")
    with SessionLocal() as db:
        student = db.scalar(select(StudentProfile).where(StudentProfile.student_id == 910001, StudentProfile.student_no == "EIT-S001"))
        actor = db.get(Employee, 910005)
        if student is None or actor is None:
            raise RuntimeError("需要现有 EIT-S001 / EIT-E005 虚构测试对象")
    config = dotenv_values(BASE_DIR / ".env")
    marker = "EIT-SMOKE-" + uuid.uuid4().hex[:12]
    results = []
    def checked(label, response):
        body = response.json()
        if response.status_code != 200 or body.get("code") != 0:
            raise RuntimeError(f"{label} failed: HTTP {response.status_code}, code={body.get('code')}, message={body.get('message')}")
        results.append({"check": label, "passed": True})
        return body["data"]
    with TestClient(app) as client:
        login = checked("real-login", client.post("/api/v1/auth/login", json={
            "username": config["ENTERPRISE_TEST_USERNAME"], "password": config["ENTERPRISE_TEST_PASSWORD"]}))
        auth = {"Authorization": "Bearer " + login["access_token"]}
        checked("STU-01", client.get(PREFIX + "/students?student_no=EIT-S001", headers=auth))
        checked("STU-02", client.get(PREFIX + "/students/910001", headers=auth))
        create = {"student_id":910001,"course_code":"EIT-ENGLISH","term_code":"EIT-2026-AUTUMN",
            "assessment_code":marker,"attempt_no":1,"score_value":"81.25","max_score":"100.00"}
        data = checked("SCO-01", client.post(PREFIX + "/scores", json=create, headers={**auth,"Idempotency-Key":marker+"-create"}))
        score_id = data["score_id"]
        replay = checked("create-idempotent-retry", client.post(PREFIX + "/scores", json=create, headers={**auth,"Idempotency-Key":marker+"-create"}))
        assert replay == data
        checked("SCO-02", client.get(PREFIX + f"/scores?student_id=910001&assessment_code={marker}", headers=auth))
        checked("SCO-03", client.get(PREFIX + f"/scores/{score_id}", headers=auth))
        corrected = checked("SCO-04", client.patch(PREFIX + f"/scores/{score_id}", json={
            "score_value":"88.50","expected_version":1,"change_reason":"虚构联调成绩更正"}, headers={**auth,"Idempotency-Key":marker+"-correct"}))
        assert corrected["version"] == 2
        voided = checked("SCO-05", client.post(PREFIX + f"/scores/{score_id}/void", json={
            "expected_version":2,"change_reason":"联调完成，作废测试成绩，保留审计"}, headers={**auth,"Idempotency-Key":marker+"-void"}))
        assert voided["status"] == "void" and voided["version"] == 3
        detail = checked("three-audit-snapshots", client.get(PREFIX + f"/scores/{score_id}", headers=auth))
        assert len(detail["history"]) == 3
        # 此 SQL 来自本机 Dify 草稿页面的真实模型试运行，验证其后端执行段。
        with SessionLocal() as db:
            actor = db.get(Employee, 910005)
            result = execute_query(db, actor, "SELECT student_no, full_name FROM authorized_students WHERE student_no = 'EIT-S001' LIMIT 200")
            assert result["row_count"] == 1 and result["rows"][0]["student_no"] == "EIT-S001"
            results.append({"check":"real-Dify-generated-SQL-to-real-authorized-MySQL", "passed":True})
        workflow_result = client.post(PREFIX + "/student-scores/nl-query", json={"question":"查询学号 EIT-S001 的学生姓名"}, headers=auth).json()
        results.append({"check":"dedicated-Dify-API", "code":workflow_result["code"], "passed":workflow_result["code"] == 0})
    report = {"tested_at":datetime.now(timezone.utc).isoformat(),"database":"education_agent",
        "test_score_id":score_id,"test_assessment_code":marker,"final_test_score_status":"void",
        "checks":results, "note":"仅 dedicated-Dify-API 项成功才代表完整模型API链路通过；仅使用本应用专用Key。"}
    Path(__file__).with_name("local_smoke_results.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))


if __name__ == "__main__":
    run()
