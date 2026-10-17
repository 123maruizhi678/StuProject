"""客服六接口冒烟 / 回归脚本（含本地库盘点与落库验证）。

用法：
    python scripts/agent/smoke_agent_api.py [MySQL密码] [库名]

- host / port / user 从 .env 读取；密码取命令行参数，缺省回退 .env 的 DB_PASSWORD；
- 库名缺省为 .env 的 DB_NAME；
- 报名接口会写入一条测试数据（customer_phone=19900000099）；
  重复执行时报名被防重拦截（code=400）属预期行为；
- DIFY_CLIENT=real 时 chat 走真实 Dify；Dify 不可用时自动兜底话术（属预期行为）。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

TABLES = ["course_project", "lecture_event", "faq", "chat_session", "event_signup", "chat_message"]


def load_env(path=".env"):
    cfg = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        cfg[k.strip()] = v.strip()
    return cfg


ENV = load_env()
PASSWORD = sys.argv[1] if len(sys.argv) > 1 else ENV.get("DB_PASSWORD", "")
DB_NAME = sys.argv[2] if len(sys.argv) > 2 else ENV.get("DB_NAME", "education_agent")

# 密码经环境变量注入（pydantic-settings 中环境变量优先于 .env），不改动 .env 文件
if PASSWORD:
    os.environ["DB_PASSWORD"] = PASSWORD
os.environ["DB_NAME"] = DB_NAME

import pymysql
from fastapi.testclient import TestClient

from app.main import app


def db_connect():
    return pymysql.connect(
        host=ENV.get("DB_HOST", "127.0.0.1"),
        port=int(ENV.get("DB_PORT", "3306")),
        user=ENV.get("DB_USER", "root"),
        password=PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
    )


def counts():
    conn = db_connect()
    cur = conn.cursor()
    result = {}
    for t in ("chat_session", "chat_message", "event_signup"):
        cur.execute(f"SELECT COUNT(*) FROM `{t}`")
        result[t] = cur.fetchone()[0]
    conn.close()
    return result


# ---------- 1. 盘点本地库 ----------
print(f"===== 1. 数据库盘点: {ENV.get('DB_HOST', '127.0.0.1')}:{ENV.get('DB_PORT', '3306')}/{DB_NAME} =====")
before = counts()
conn = db_connect()
cur = conn.cursor()
cur.execute(
    "SELECT table_name FROM information_schema.tables WHERE table_schema=%s ORDER BY table_name",
    (DB_NAME,),
)
print(f"库内共 {len(cur.fetchall())} 张表；冒烟前 chat_session={before['chat_session']}、"
      f"chat_message={before['chat_message']}、event_signup={before['event_signup']}")
cur.execute("SELECT id, event_name, status, quota, signed_count FROM lecture_event ORDER BY id")
print("活动状态：")
for row in cur.fetchall():
    print(f"  id={row[0]} {row[1]} 状态={row[2]} 名额={row[3]} 已报={row[4]}")
conn.close()

# ---------- 2. 跑六个接口 ----------
print("\n===== 2. 客服六接口冒烟（TestClient） =====")
client = TestClient(app)


def show(name, resp, keys=None):
    body = resp.json()
    code = body.get("code")
    msg = body.get("message", "")
    data = body.get("data")
    summary = ""
    if isinstance(data, dict):
        picks = keys or [k for k in ("session_id", "intent", "reply", "signup_id") if k in data]
        summary = " ".join(f"{k}={str(data[k])[:50]}" for k in picks)
    elif isinstance(data, list):
        summary = f"{len(data)} 条"
    flag = "OK " if code == 0 else "FAIL"
    print(f"[{resp.status_code}] {flag} {name}: code={code} {summary}")
    if code != 0:
        print(f"         message: {msg}")


r = client.post("/api/v1/agent/chat", json={"message": "最近有什么留学讲座？"})
show("POST /agent/chat", r)

r = client.get("/api/v1/agent/events")
show("GET  /agent/events", r)
events = r.json().get("data") or []

# 报名只选「报名中」的活动
open_events = [e for e in events if e["status"] == "报名中"]
event_id = open_events[0]["event_id"] if open_events else None
if not open_events:
    print("（无“报名中”活动，跳过详情与报名）")

if event_id:
    r = client.get(f"/api/v1/agent/events/{event_id}")
    show(f"GET  /agent/events/{event_id}", r)

r = client.get("/api/v1/agent/courses")
show("GET  /agent/courses", r)

r = client.get("/api/v1/agent/faq", params={"question": "费用"})
show("GET  /agent/faq", r)

if event_id:
    r = client.post(
        "/api/v1/agent/events/signup",
        json={
            "event_id": event_id,
            "customer_name": "冒烟测试",
            "customer_phone": "19900000099",
            "customer_info": {"source": "smoke-test"},
        },
    )
    show(f"POST /agent/events/signup (event_id={event_id})", r, keys=["signup_id", "signup_time"])

# ---------- 3. 落库验证 ----------
after = counts()
print("\n===== 3. 落库验证 =====")
print(f"chat_session: {before['chat_session']} -> {after['chat_session']}（chat 应 +1）")
print(f"chat_message: {before['chat_message']} -> {after['chat_message']}（chat 应 +2：user+assistant）")
print(f"event_signup: {before['event_signup']} -> {after['event_signup']}（报名成功应 +1）")

conn = db_connect()
cur = conn.cursor()
cur.execute(
    "SELECT session_id, role, intent, LEFT(content, 24) FROM chat_message ORDER BY id DESC LIMIT 2"
)
print("最新两条消息（倒序）：")
for row in cur.fetchall():
    print(f"  session={row[0][:12]}... role={row[1]} intent={row[2]} content={row[3]}")
conn.close()

print("\n注意：报名接口写入了测试数据（customer_phone=19900000099），可在 event_signup 中清理。")
