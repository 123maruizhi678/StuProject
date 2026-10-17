"""演示数据种子：部门、员工角色账号、产品、规则。

幂等：按 username / employee_no / product_code 判断存在则跳过。
运行：python scripts/seed_demo.py
"""

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.common.security import hash_password
from app.database import SessionLocal
from app.models.common.employee import Employee
from app.models.common.org_department import OrgDepartment
from app.models.common.user_account import UserAccount
from app.models.customer.product import Product
from app.models.customer.research_rule import ResearchRule

DEMO_PASSWORD = "123456"


def _rule_content_steady() -> dict:
    return {
        "match_logic": "all",
        "conditions": [
            {"field": "education_level", "op": "in", "value": ["本科", "硕士", "博士"]},
            {"field": "work_years", "op": "ge", "value": 3},
        ],
        "score_rules": [
            {"field": "education_level", "points": {"博士": 50, "硕士": 40, "本科": 30}},
            {"field": "work_years", "points": {"10": 30, "5": 20, "3": 10}},
        ],
        "score_threshold": 40,
    }


def _rule_content_annuity() -> dict:
    return {
        "match_logic": "all",
        "conditions": [
            {"field": "age", "op": "ge", "value": 35},
            {"field": "income_level", "op": "in", "value": ["中高", "高"]},
        ],
        "score_rules": [
            {"field": "age", "points": {"55": 50, "45": 40, "35": 30}},
            {"field": "income_level", "points": {"高": 40, "中高": 30}},
        ],
        "score_threshold": 60,
    }


def main() -> None:
    db = SessionLocal()
    try:
        # ---- 部门 ----
        dept = db.scalar(select(OrgDepartment).where(
            OrgDepartment.department_code == "D-CUST"))
        if dept is None:
            dept = OrgDepartment(
                department_code="D-CUST",
                department_name="客户经营部",
                parent_department_id=None,
                status="active",
            )
            db.add(dept)
            db.flush()

        # ---- 员工角色 ----
        employees = [
            ("E-ANALYST", "研判分析员", ["analyst"], "分析师"),
            ("E-REVIEWER", "规则复核员", ["reviewer"], "复核员"),
            ("E-CONSULTANT", "客户顾问", ["consultant"], "顾问"),
        ]
        emp_by_no = {}
        for emp_no, full_name, roles, title in employees:
            emp = db.scalar(select(Employee).where(Employee.employee_no == emp_no))
            if emp is None:
                emp = Employee(
                    employee_no=emp_no,
                    full_name=full_name,
                    department_id=dept.department_id,
                    position_title=title,
                    login_provider="local",
                    login_subject=emp_no,
                    role_codes=roles,
                    status="active",
                    joined_date=dt.date.today(),
                )
                db.add(emp)
                db.flush()
            emp_by_no[emp_no] = emp

        # ---- 账号 ----
        # 平台真实 admin 账号已在公共库中，此处另建客户模块演示管理员，避免覆盖真实凭据
        accounts = [
            ("cust_admin", "admin", None),
            ("analyst", "employee", emp_by_no["E-ANALYST"].employee_id),
            ("reviewer", "employee", emp_by_no["E-REVIEWER"].employee_id),
            ("consultant", "employee", emp_by_no["E-CONSULTANT"].employee_id),
        ]
        for username, identity_type, employee_id in accounts:
            existing = db.scalar(select(UserAccount).where(UserAccount.username == username))
            if existing is None:
                db.add(UserAccount(
                    username=username,
                    password_hash=hash_password(DEMO_PASSWORD),
                    identity_type=identity_type,
                    employee_id=employee_id,
                ))

        # ---- 产品 ----
        products = [
            ("PROD-A", "稳健理财", "面向高学历、稳定工作客户的中低风险理财产品",
             "本科及以上、工作满 3 年"),
            ("PROD-B", "高端养老险", "面向 35 岁以上、收入中高客户的养老保障产品",
             "35 岁以上、收入中高及以上"),
        ]
        prod_by_code = {}
        for code, name, desc, summary in products:
            prod = db.scalar(select(Product).where(Product.product_code == code))
            if prod is None:
                prod = Product(
                    product_code=code, product_name=name, description=desc,
                    target_profile_summary=summary, status="active",
                )
                db.add(prod)
                db.flush()
            prod_by_code[code] = prod

        # ---- 规则 v1 ----
        rules = {
            "PROD-A": (_rule_content_steady, "稳健理财客户画像研判规则 v1"),
            "PROD-B": (_rule_content_annuity, "高端养老险客户画像研判规则 v1"),
        }
        for code, (fn, desc) in rules.items():
            prod = prod_by_code[code]
            has = db.scalar(select(ResearchRule).where(
                ResearchRule.product_id == prod.id,
                ResearchRule.rule_version == "v1",
            ))
            if has is None:
                db.add(ResearchRule(
                    product_id=prod.id,
                    rule_version="v1",
                    rule_content=fn(),
                    rule_description=desc,
                    is_active=True,
                    active_slot=1,
                    effective_from=dt.datetime.now(),
                ))

        db.commit()
        print("种子完成：")
        print(f"  账号: cust_admin / analyst / reviewer / consultant  密码: {DEMO_PASSWORD}")
        print(f"  部门: 客户经营部 (id={dept.department_id})")
        print(f"  产品: PROD-A 稳健理财, PROD-B 高端养老险")
        print("  规则: 各产品 v1 已生效")
    finally:
        db.close()


if __name__ == "__main__":
    main()
