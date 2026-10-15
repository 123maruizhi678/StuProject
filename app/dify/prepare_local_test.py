"""补齐本机联调结构；不删表、不重置密码、不覆盖既有业务数据。"""
import re
import secrets

from dotenv import dotenv_values, set_key
from sqlalchemy import inspect, text

from app.config import BASE_DIR
from app.database import engine
from app.services.auth_service import hash_password, verify_password


def prepare():
    if engine.url.database != "education_agent" or engine.url.host not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("本脚本只允许用户指定的本机 education_agent 测试库")
    inspector = inspect(engine)
    changes = []
    with engine.begin() as connection:
        if "crm_student_id" not in {c["name"] for c in inspector.get_columns("student_profile")}:
            connection.exec_driver_sql("ALTER TABLE student_profile ADD COLUMN crm_student_id VARCHAR(128) COLLATE utf8mb4_bin NULL, ADD UNIQUE KEY uq_student_crm (crm_student_id)")
            changes.append("added nullable student_profile.crm_student_id and unique index")
        if not inspector.has_table("user_account"):
            source = (BASE_DIR / "scripts/sql/all.sql").read_text(encoding="utf-8")
            ddl = re.search(r"CREATE TABLE `user_account`\s*\([\s\S]*?\) ENGINE=InnoDB[^;]*;", source)
            if ddl is None:
                raise RuntimeError("未找到项目 user_account 建表定义")
            connection.exec_driver_sql(ddl.group(0))
            changes.append("created user_account from project DDL")
        employee = connection.execute(text("SELECT employee_id FROM employee WHERE employee_id=910005 AND employee_no='EIT-E005' AND status='active' AND JSON_CONTAINS(role_codes, '\"academic\"')")).first()
        if not employee:
            raise RuntimeError("需要现有 EIT-E005 虚构教务员工；未自动创建真实员工")
        env_path = BASE_DIR / ".env"
        config = dotenv_values(env_path)
        password = config.get("ENTERPRISE_TEST_PASSWORD") or secrets.token_urlsafe(24)
        account = connection.execute(text("SELECT username,password_hash FROM user_account WHERE employee_id=910005 OR username='eit-academic'" )).mappings().first()
        if account:
            if account["username"] != "eit-academic" or not verify_password(password, account["password_hash"]):
                raise RuntimeError("员工已有其他账号或测试密码不匹配，未覆盖账号")
        else:
            connection.execute(text("INSERT INTO user_account (username,password_hash,identity_type,employee_id) VALUES (:username,:password_hash,'employee',910005)"),
                {"username": "eit-academic", "password_hash": hash_password(password)})
            changes.append("created synthetic eit-academic login linked to EIT-E005")
        # 凭据仅写本机 .env，不写 DSL、报告或日志。
        if not config.get("AUTH_SECRET_KEY"):
            set_key(str(env_path), "AUTH_SECRET_KEY", secrets.token_urlsafe(48))
        set_key(str(env_path), "ENTERPRISE_TEST_USERNAME", "eit-academic")
        if not config.get("ENTERPRISE_TEST_PASSWORD"):
            set_key(str(env_path), "ENTERPRISE_TEST_PASSWORD", password)
    print({"database": engine.url.database, "changes": changes, "test_credentials": "project .env ENTERPRISE_TEST_USERNAME / ENTERPRISE_TEST_PASSWORD"})


if __name__ == "__main__":
    prepare()
