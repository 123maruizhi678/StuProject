"""学生模块专用本地MySQL开发实例。只操作带归属标记的独立数据目录。"""

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time

import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.student_sql_paths import enterprise_sql_path

STATE_DIR = ROOT.parent / ".student-local-mysql"
STATE_FILE = STATE_DIR / "instance.json"


def save(state):
    STATE_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load():
    if not STATE_FILE.exists():
        return None
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    if state.get("owner") != str(ROOT):
        raise RuntimeError("本地实例归属不匹配，停止操作")
    return state


def connect(state, *, empty_password=False):
    return pymysql.connect(
        host="127.0.0.1",
        port=state["port"],
        user="root",
        password="" if empty_password else state["root_password"],
        charset="utf8mb4",
        connect_timeout=2,
        read_timeout=10,
        write_timeout=10,
        autocommit=True,
    )


def alive(state):
    try:
        with connect(state) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT @@datadir")
                actual = Path(cursor.fetchone()[0]).resolve()
                if actual != (STATE_DIR / "data").resolve():
                    raise RuntimeError("连接的数据目录不属于本实例")
        return True
    except pymysql.Error:
        return False


def start(args):
    state = load()
    if state and alive(state):
        print(f"学生本地MySQL已运行：127.0.0.1:{state['port']}")
        return state
    if not state:
        if STATE_DIR.exists() and any(STATE_DIR.iterdir()):
            raise RuntimeError("本地目录已有未知文件，停止初始化")
        binary = (
            args.mysqld
            or shutil.which("mysqld")
            or "C:/tools/mysql/mysql-8.0.27-winx64/bin/mysqld.exe"
        )
        if not Path(binary).is_file():
            raise RuntimeError("未找到MySQL服务程序，请用--mysqld指定路径")
        state = {
            "owner": str(ROOT),
            "binary": str(Path(binary).resolve()),
            "port": args.port,
            "root_password": secrets.token_urlsafe(32),
            "app_password": secrets.token_urlsafe(32),
            "auth_secret": secrets.token_urlsafe(48),
            "secured": False,
        }
        save(state)
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", state["port"]))
        except OSError:
            raise RuntimeError("本地开发端口被其他进程占用，未操作该进程") from None
    data = STATE_DIR / "data"
    binary, basedir = state["binary"], str(Path(state["binary"]).parents[1])
    if not data.exists():
        result = subprocess.run(
            [
                binary,
                "--no-defaults",
                "--initialize-insecure",
                f"--basedir={basedir}",
                f"--datadir={data}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            raise RuntimeError("独立MySQL数据目录初始化失败，请检查安装包与本地日志")
    process = subprocess.Popen(
        [
            binary,
            "--no-defaults",
            f"--basedir={basedir}",
            f"--datadir={data}",
            f"--port={state['port']}",
            "--bind-address=127.0.0.1",
            "--mysqlx=0",
            "--skip-log-bin",
            "--default-time-zone=+00:00",
            "--innodb-buffer-pool-size=64M",
            f"--log-error={STATE_DIR / 'mysql.log'}",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    state["pid"] = process.pid
    save(state)
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("独立MySQL启动失败，请查看本地mysql.log")
        try:
            connection = connect(state, empty_password=not state["secured"])
            break
        except pymysql.Error:
            time.sleep(0.2)
    else:
        raise RuntimeError("独立MySQL未在等待时间内就绪")
    with connection as conn:
        with conn.cursor() as cursor:
            if not state["secured"]:
                cursor.execute(
                    "ALTER USER 'root'@'localhost' IDENTIFIED BY %s",
                    (state["root_password"],),
                )
                state["secured"] = True
                save(state)
            cursor.execute(
                "CREATE DATABASE IF NOT EXISTS education_agent CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            )
            cursor.execute(
                "CREATE USER IF NOT EXISTS 'student_local'@'127.0.0.1' IDENTIFIED BY %s",
                (state["app_password"],),
            )
            cursor.execute(
                "GRANT ALL PRIVILEGES ON education_agent.* TO 'student_local'@'127.0.0.1'"
            )
    print(f"学生本地MySQL已启动：127.0.0.1:{state['port']} / education_agent")
    return state


def bootstrap(state):
    # 这些共享表只是独立开发实例的前置依赖，DDL直接取企业版本；生产库禁止运行本工具。
    required = {
        "org_department",
        "employee",
        "customer_profile",
        "student_profile",
        "student_staff_binding",
        "service_ticket",
        "service_ticket_record",
        "business_notification",
        "operation_log",
    }
    source = enterprise_sql_path().read_text(encoding="utf-8")
    blocks = re.findall(
        r"CREATE TABLE(?: IF NOT EXISTS)?\s+`?(\w+)`?\s*\([\s\S]*?\n\) ENGINE[^;]*;",
        source,
        re.I,
    )
    statements = re.findall(
        r"CREATE TABLE(?: IF NOT EXISTS)?\s+`?\w+`?\s*\([\s\S]*?\n\) ENGINE[^;]*;",
        source,
        re.I,
    )
    with connect(state) as conn:
        with conn.cursor() as cursor:
            cursor.execute("USE education_agent")
            cursor.execute("SHOW TABLES")
            existing = {row[0] for row in cursor.fetchall()}
            for name, statement in zip(blocks, statements):
                if name in required and name not in existing:
                    cursor.execute(statement)
            cursor.execute("SHOW COLUMNS FROM student_profile LIKE 'crm_student_id'")
            if not cursor.fetchone():
                cursor.execute(
                    "ALTER TABLE student_profile ADD COLUMN crm_student_id VARCHAR(128) COLLATE utf8mb4_bin NULL UNIQUE"
                )
            cursor.execute(
                "INSERT IGNORE INTO org_department(department_code,department_name) VALUES ('STUDENT_LOCAL_DEMO','学生本地演示部门')"
            )
            cursor.execute(
                "SELECT department_id FROM org_department WHERE department_code='STUDENT_LOCAL_DEMO'"
            )
            department_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT IGNORE INTO employee(employee_no,full_name,department_id,login_provider,login_subject,role_codes,status,joined_date) VALUES ('STUDENT_LOCAL_TEACHER','本地演示老师',%s,'local_demo','student-local-teacher',JSON_ARRAY('teacher'),'active','2026-01-01')",
                (department_id,),
            )
            cursor.execute(
                "SELECT employee_id FROM employee WHERE employee_no='STUDENT_LOCAL_TEACHER'"
            )
            teacher_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT IGNORE INTO student_profile(student_no,full_name,department_id,status,external_student_id,crm_student_id,is_archived) VALUES ('STUDENT_LOCAL_DEMO','本地演示学生',%s,'active','local-education-student','local-crm-student',0)",
                (department_id,),
            )
            cursor.execute(
                "SELECT student_id FROM student_profile WHERE student_no='STUDENT_LOCAL_DEMO'"
            )
            student_id = cursor.fetchone()[0]
            cursor.execute(
                "SELECT binding_id FROM student_staff_binding WHERE student_id=%s AND employee_id=%s AND relation_type='class_teacher'",
                (student_id, teacher_id),
            )
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO student_staff_binding(student_id,employee_id,relation_type,is_primary,valid_from,status) VALUES (%s,%s,'class_teacher',1,UTC_TIMESTAMP(3),'active')",
                    (student_id, teacher_id),
                )
    configure(state)
    sys.path.insert(0, str(ROOT))
    from scripts.init_student_tables import main as initialize

    if initialize(["--apply"]):
        raise RuntimeError("学生表初始化未通过；已有数据已保留")
    print(
        f"本地演示数据已就绪：学生ID={student_id}，老师ID={teacher_id}；均为本地测试身份。"
    )


def configure(state):
    path = ROOT / ".env.student.local"
    content = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    backup = STATE_DIR / "env.before-local"
    if not backup.exists():
        original = ROOT / ".env"
        backup.write_text(
            original.read_text(encoding="utf-8-sig") if original.exists() else "",
            encoding="utf-8",
        )
    values = {
        "DB_HOST": "127.0.0.1",
        "DB_PORT": str(state["port"]),
        "DB_USER": "student_local",
        "DB_PASSWORD": state["app_password"],
        "DB_NAME": "education_agent",
        "DB_ECHO": "false",
        "STUDENT_AUTH_SECRET": state["auth_secret"],
        "STUDENT_QUERY_BACKEND": "local",
    }
    for key, value in values.items():
        line = key + "=" + value
        if re.search(r"^" + key + "=.*$", content, re.M):
            content = re.sub(r"^" + key + "=.*$", lambda _: line, content, flags=re.M)
        else:
            content += "\n" + line
        os.environ[key] = value
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    print(
        "学生.env.student.local已连接专用本地实例；原配置备份保存在实例目录，未输出凭证。"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "status", "stop", "setup"])
    parser.add_argument("--port", type=int, default=3307)
    parser.add_argument("--mysqld")
    args = parser.parse_args()
    try:
        state = load()
        if args.action == "status":
            print(
                json.dumps(
                    {
                        "running": bool(state and alive(state)),
                        "host": "127.0.0.1",
                        "port": state["port"] if state else None,
                    },
                    ensure_ascii=False,
                )
            )
        elif args.action == "stop":
            if state and alive(state):
                with connect(state) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SHUTDOWN")
                print("学生专用本地实例已停止，数据保留。")
            else:
                print("学生专用本地实例未运行。")
        else:
            state = start(args)
            if args.action == "setup":
                bootstrap(state)
        return 0
    except (RuntimeError, OSError, pymysql.Error) as exc:
        code = exc.args[0] if isinstance(exc, pymysql.Error) and exc.args else None
        print(
            f"本地学生实例操作失败（数据库码={code}）；"
            + (
                str(exc)
                if not isinstance(exc, pymysql.Error)
                else "请检查实例日志，原数据未清除。"
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
