"""真实本地MySQL+HTTP验证。只创建和删除本脚本生成的隔离测试库；不连组长数据库。"""
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import json
import re
import socket
import sys
import threading
import time
import uuid

import httpx
import uvicorn
from fastapi import FastAPI
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from check_student_shared_schema import connection_url
from app.api.student_leave import create_router as leave_router
from app.api.student_ticket import create_router as ticket_router
from app.clients.student_ticket_dify import StudentTicketDifyClient
from app.config import StudentTicketSettings
from app.repositories.student_schema import check_student_schema


@contextmanager
def isolated_mysql():
    url=connection_url(True)
    if url.host != "127.0.0.1": raise RuntimeError("仅支持学生本地实例")
    name="student_test_"+uuid.uuid4().hex
    if not re.fullmatch(r"student_test_[0-9a-f]{32}", name): raise RuntimeError("测试库名校验失败")
    admin=create_engine(url.set(database=None),echo=False,connect_args={"connect_timeout":3})
    engine=None
    created=False
    try:
        with admin.begin() as connection:
            connection.exec_driver_sql(f"CREATE DATABASE \x60{name}\x60 CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        created=True
        engine=create_engine(url.set(database=name),echo=False)
        sql=(ROOT/"scripts/sql/all.sql").read_text(encoding="utf-8")
        blocks=re.findall(r"CREATE TABLE[\s\S]*?ENGINE=InnoDB[^;]*;",sql)
        ddls={re.search(r"CREATE TABLE \x60?(\w+)\x60?",b)[1]:b for b in blocks}
        order=["org_department","employee","customer_profile","student_profile","student_staff_binding",
               "student_admin_service","service_ticket","service_ticket_record","business_notification","operation_log"]
        with engine.begin() as connection:
            assert connection.exec_driver_sql("SELECT @@FOREIGN_KEY_CHECKS").scalar()==1
            for table in order: connection.exec_driver_sql(ddls[table])
            # 精确执行CREATE语句，绝不执行all.sql头部的DROP。
            connection.execute(text("INSERT INTO org_department(department_id,department_code,department_name) VALUES(5,'TEST','学生服务测试部门')"))
            connection.execute(text("INSERT INTO student_profile(student_id,student_no,full_name,department_id,status) VALUES(7,'TEST-7','测试学生甲',5,'active'),(8,'TEST-8','测试学生乙',5,'active')"))
        yield engine
    finally:
        if engine is not None: engine.dispose()
        if created:
            # 名字由本脚本生成并匹配固定测试前缀，仅清理本次隔离库。
            with admin.begin() as connection: connection.exec_driver_sql(f"DROP DATABASE \x60{name}\x60")
        admin.dispose()


def main():
    with isolated_mysql() as engine:
        with engine.connect() as connection:
            schema={feature:check_student_schema(connection,feature)["compatible"] for feature in ("leave","ticket")}
        assert all(schema.values())
        sessions=sessionmaker(bind=engine)
        actor=SimpleNamespace(identity_type="student",student_id=7,user_id=907)
        live, requests=[],[]
        def account(): return actor
        def get_db():
            with sessions() as db:
                live.append(db)
                try: yield db
                finally: live.remove(db)
        def upstream(request):
            assert all(not db.in_transaction() for db in live)
            requests.append(json.loads(request.content))
            return httpx.Response(200,json={"workflow_run_id":"mysql-http-mock-001","data":{"status":"succeeded","outputs":{
                "result":{"summary":"学生反馈课程变更，希望明确安排。","suggested_category":"teaching"}}}})
        config=StudentTicketSettings(_env_file=None,STUDENT_DIFY_TICKET_KEY="test-only-workflow-key",
                                    STUDENT_DIFY_TICKET_BASE="http://dify-test.local/v1")
        workflow=StudentTicketDifyClient(config,httpx.MockTransport(upstream))
        app=FastAPI(title="学生业务最小单元验收；测试身份")
        app.include_router(leave_router(account,get_db),prefix="/api/v1")
        app.include_router(ticket_router(account,account,get_db,lambda:workflow),prefix="/api/v1")
        sock=socket.socket();sock.bind(("127.0.0.1",0))
        port=sock.getsockname()[1]
        server=uvicorn.Server(uvicorn.Config(app,log_level="error"))
        thread=threading.Thread(target=server.run,kwargs={"sockets":[sock]},daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if server.started: break
                time.sleep(.05)
            if not server.started: raise RuntimeError("临时HTTP服务未启动")
            with httpx.Client(base_url=f"http://127.0.0.1:{port}/api/v1/student",trust_env=False,timeout=20) as client:
                body={"content":"课程安排变更，希望老师明确后续安排。","ticket_type":"complaint","category_code":"teaching"}
                headers={"Idempotency-Key":"mysql-http-001"}
                first=client.post("/complaint",json=body,headers=headers)
                assert first.status_code==200,first.text
                retry=client.post("/complaint",json=body,headers=headers)
                assert retry.json()==first.json()
                ticket_id=first.json()["data"]["ticket_id"]
                assert client.get("/tickets").json()["data"]["items"][0]["ticket_id"]==ticket_id
                assert client.get(f"/tickets/{ticket_id}").json()["data"]["content"]==body["content"]
                with engine.begin() as connection:
                    connection.execute(text("INSERT INTO service_ticket_record(ticket_id,record_type,service_code,content,visibility,record_key) VALUES(:id,'note','test-only','内部材料','internal','internal-test')"),{"id":ticket_id})
                records=client.get(f"/tickets/{ticket_id}/records").json()["data"]["items"]
                assert len(records)==1 and "内部材料" not in json.dumps(records,ensure_ascii=False)
                actor.student_id=8
                assert client.get(f"/tickets/{ticket_id}").status_code==404
                assert client.get(f"/tickets/{ticket_id}/records").status_code==404
                actor.student_id=7
                # 未配置真实Dify时原文仍落库，回执明确摘要不可用。
                workflow.config=StudentTicketSettings(_env_file=None,STUDENT_DIFY_TICKET_KEY="")
                fallback=client.post("/complaint",json=body,headers={"Idempotency-Key":"mysql-http-fallback"})
                assert fallback.status_code==200 and fallback.json()["data"]["ai_status"]=="unavailable"
                plain_leave=client.post("/leave",headers={"Idempotency-Key":"mysql-leave-001"},json={
                    "leave_content":"因个人安排申请请假", "leave_type":"personal",
                    "leave_start_at":"2026-10-20T09:00:00+08:00", "leave_end_at":"2026-10-20T18:00:00+08:00"})
                assert plain_leave.status_code==200 and plain_leave.json()["data"]["ai_status"]=="not_requested"
            fk_rejected=False
            try:
                with engine.begin() as connection:
                    connection.execute(text("INSERT INTO service_ticket_record(ticket_id,record_type,student_id,visibility,record_key) VALUES(999999,'submitted',7,'student_visible','invalid-fk-test')"))
            except IntegrityError: fk_rejected=True
            assert fk_rejected
            with engine.connect() as connection:
                counts={name:connection.exec_driver_sql(f"SELECT COUNT(*) FROM {name}").scalar() for name in
                        ("service_ticket","service_ticket_record","student_admin_service","operation_log")}
            assert counts=={"service_ticket":2,"service_ticket_record":3,"student_admin_service":1,"operation_log":3}
            assert len(requests)==1
            print(json.dumps({"database":"本地MySQL 8.0隔离测试库；自动清理", "transport":"真实localhost HTTP",
                "schema_compatible":schema,"foreign_key_checks_enabled":True,"invalid_foreign_key_rejected":fk_rejected,
                "owner_scope_and_internal_visibility":"passed","idempotent_replay":"passed",
                "plain_leave_no_model":"passed", "model_unavailable_original_saved":"passed", "persisted_rows":counts,
                "workflow_requests":len(requests),"dify_transport":"httpx.MockTransport test double",
                "real_dify_verified":False,"group_jwt_verified":False},ensure_ascii=False,indent=2))
        finally:
            server.should_exit=True
            thread.join(timeout=5)
            sock.close()
            if thread.is_alive(): raise RuntimeError("HTTP服务未正常退出")


if __name__=="__main__": main()
