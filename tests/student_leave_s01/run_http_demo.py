"""S01本机HTTP演示：仅测试夹具身份，非登录入口或生产服务。"""
from pathlib import Path
import importlib.util
import json
import socket
import sys
import tempfile
import threading
import time

import httpx
import uvicorn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    spec = importlib.util.spec_from_file_location("s01_test", Path(__file__).with_name("test_submit_leave.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="student_s01_") as directory:
        fixture = module.unit.__wrapped__(Path(directory))
        unit = next(fixture)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(unit.app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(.05)
            if not server.started:
                raise RuntimeError("S01临时服务未启动")
            url = f"http://127.0.0.1:{port}/api/v1/student/leave"
            headers = {"Idempotency-Key": "s01-live-http-001"}
            with httpx.Client(timeout=5, trust_env=False) as client:
                first = client.post(url, json=module.body(), headers=headers)
                retry = client.post(url, json=module.body(), headers=headers)
                forged = client.post(url, json=module.body() | {"student_id": 8},
                                     headers={"Idempotency-Key": "s01-forged"})
            counts = {table.name: module.count(unit, table) for table in (
                module.t.student_admin_service, module.t.business_notification, module.t.operation_log
            )}
            assert first.status_code == 200 and first.json() == retry.json()
            assert forged.status_code == 422 and list(counts.values()) == [1, 1, 1]
            print(json.dumps({
                "feature": "S01 学生提交请假", "transport": "uvicorn + localhost HTTP",
                "identity": "test fixture only; group JWT not tested",
                "database": "temporary isolated SQLite", "http_status": first.status_code,
                "response": first.json(), "replay_same_receipt": True,
                "forged_student_field_status": forged.status_code, "persisted_rows": counts,
                "notification_delivery": "queued, not sent",
            }, ensure_ascii=False, indent=2))
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            sock.close()
            try:
                next(fixture)
            except StopIteration:
                pass
            if thread.is_alive():
                raise RuntimeError("临时服务未正常结束")


if __name__ == "__main__":
    main()
