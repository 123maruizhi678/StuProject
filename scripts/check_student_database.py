"""只读检查学生模块数据库连接、版本和表结构；不打印密码、Dify Key或业务数据。"""

import argparse
import json
import sys
import socket
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pymysql
from app.config import settings

TABLES = {
    "student_profile",
    "employee",
    "student_staff_binding",
    "student_leave_request",
    "service_ticket",
    "service_ticket_record",
    "business_notification",
    "operation_log",
    "mental_health_profile",
    "mental_warning",
    "student_academic_event",
    "student_academic_reminder",
    "student_application_progress",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=None)
    parser.add_argument(
        "--report",
        default=None,
        help="将结构报告保存到本地JSON文件（不含业务数据或密钥）",
    )
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument(
        "--diagnose", action="store_true", help="额外只读检查TCP和MySQL初始握手"
    )
    args = parser.parse_args()
    host, port = args.host or settings.DB_HOST, args.port or settings.DB_PORT
    stage = "mysql_login"
    if args.diagnose:
        try:
            with socket.create_connection((host, port), timeout=10) as tcp:
                tcp.settimeout(10)
                header = tcp.recv(4)
                if len(header) != 4:
                    raise OSError("TCP已连通，但没有完整的MySQL握手头")
                length = int.from_bytes(header[:3], "little")
                packet = tcp.recv(min(length, 4096))
                if not packet:
                    raise OSError("连接在MySQL握手前被服务端关闭")
                print(
                    json.dumps(
                        {
                            "tcp_connected": True,
                            "mysql_protocol_byte": packet[0],
                            "server_greeting": (
                                packet[1:]
                                .split(b"\x00", 1)[0]
                                .decode("ascii", "replace")[:100]
                                if packet[0] == 10
                                else "非标准MySQL握手或服务端拒绝"
                            ),
                        },
                        ensure_ascii=False,
                    )
                )
        except OSError as error:
            print(
                json.dumps(
                    {"tcp_or_handshake_failed": True, "detail": str(error)[:240]},
                    ensure_ascii=False,
                )
            )
    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            charset="utf8mb4",
            connect_timeout=10,
            read_timeout=10,
            write_timeout=10,
        )
        with connection.cursor() as cursor:
            stage = "server_version"
            cursor.execute("SELECT VERSION(), DATABASE()")
            version, database = cursor.fetchone()
            stage = "table_list"
            cursor.execute("SHOW TABLES")
            names = {row[0] for row in cursor.fetchall()}
            columns = {}
            create_sql = {}
            for table in sorted(TABLES & names):
                stage = "columns:" + table
                cursor.execute("SHOW COLUMNS FROM \x60" + table + "\x60")
                columns[table] = [
                    {"name": r[0], "type": r[1], "nullable": r[2], "key": r[3]}
                    for r in cursor.fetchall()
                ]
                cursor.execute("SHOW CREATE TABLE `" + table + "`")
                create_sql[table] = cursor.fetchone()[1]
        connection.close()
        report = {
            "connected": True,
            "host": host,
            "port": port,
            "version": version,
            "database": database,
            "relevant_tables": sorted(TABLES & names),
            "missing_tables": sorted(TABLES - names),
            "columns": columns,
            "create_sql": create_sql,
            "all_table_names": sorted(names),
        }
        if args.report:
            destination = Path(args.report).resolve()
            destination.write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(
                json.dumps(
                    {
                        "connected": True,
                        "report": str(destination),
                        "tables_checked": len(columns),
                    },
                    ensure_ascii=False,
                )
            )
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except pymysql.Error as error:
        code = error.args[0] if error.args else None
        print(
            json.dumps(
                {
                    "connected": False,
                    "host": host,
                    "port": port,
                    "error_code": code,
                    "stage": stage,
                    "detail": (
                        str(error.args[1])[:240] if len(error.args) > 1 else "unknown"
                    ),
                    "message": (
                        "登录或授权被拒绝"
                        if code == 1045
                        else "网络、端口、数据库名称或连接授权需要核验"
                    ),
                },
                ensure_ascii=False,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
