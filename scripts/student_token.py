"""本机联调签发短期学生模块凭证；正式环境接统一登录，不提供HTTP签发接口。"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.student_auth import sign_token


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--type", choices=["student", "employee", "service"], required=True)
    p.add_argument("--id", type=int)
    p.add_argument("--service-code")
    p.add_argument("--scope", action="append", default=[])
    p.add_argument("--seconds", type=int, default=3600)
    args = p.parse_args()
    if not 1 <= args.seconds <= 86400:
        p.error("有效期必须在1至86400秒之间")
    if args.type != "service" and (args.id is None or args.id < 1):
        p.error("学生/员工需要正整数--id")
    if args.type == "service" and (
        not args.service_code or len(args.service_code) > 64
    ):
        p.error("服务身份需要--service-code（不超过64字符）")
    claims = {
        "actor_type": args.type,
        "actor_id": args.id if args.type != "service" else None,
        "service_code": args.service_code if args.type == "service" else None,
        "scopes": args.scope,
    }
    print(sign_token(claims, lifetime=args.seconds))


if __name__ == "__main__":
    main()
