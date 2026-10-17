"""文档权限矩阵、逐接口依赖及策略失效保护。"""
import tempfile
from pathlib import Path
from unittest.mock import patch
from typing import Annotated
from fastapi import Depends
from app.core.common.authorization import access_for, load_access_control, permissions_for, public_access, require_permission
from tests.common.support import AuthCase


class AuthorizationTests(AuthCase):
    def test_report_matrix(self):
        expected={"report.generate","report.read","report.config.read","report.config.write"}
        self.assertTrue(expected.issubset(permissions_for("admin")))
        for role in ["employee","admin","teacher","academic","analyst","reviewer","consultant"]:
            with self.subTest(role=role):
                self.assertNotIn("report.read",permissions_for("employee",[role]))
        manager=permissions_for("employee",["manager"])
        self.assertEqual(expected & manager,{"report.read"})

    def test_research_matrix(self):
        analyst=permissions_for("employee",["analyst"])
        for action in ["customer.source.create","customer.source.parse","customer.judge.create","customer.judge.batch"]:
            self.assertIn(action,analyst)
        self.assertNotIn("customer.rule.manage",analyst)
        reviewer=permissions_for("employee",["reviewer"])
        self.assertIn("customer.rule.read",reviewer)
        self.assertNotIn("customer.rule.manage",reviewer)
        admin=permissions_for("admin")
        self.assertNotIn("customer.source.create",admin)
        self.assertNotIn("customer.result.read",admin)
        self.assertIn("customer.result.read",permissions_for("employee"))

    def test_student_ticket_and_exact_permissions(self):
        student=permissions_for("student")
        self.assertTrue({"service_ticket.create","service_ticket.read_own","student.admin_service.withdraw_own",
                         "student.course.read_own","student.score.read_own","student.action.confirm"}.issubset(student))
        customer=permissions_for("customer")
        self.assertNotIn("service_ticket.create",customer)
        self.assertNotIn("service_ticket.read_own",customer)
        self.assertNotIn("student.admin_service.review",student)
        self.assertTrue(all("*" not in value for value in student))

    def test_employee_role_admin_is_separate_from_platform_admin(self):
        employee_admin=permissions_for("employee",["admin"])
        self.assertIn("enterprise.role.manage",employee_admin)
        self.assertNotIn("student.admin_service.review",employee_admin)
        self.assertNotIn("report.config.write",employee_admin)
        self.assertNotIn("enterprise.role.manage",permissions_for("admin"))

    def test_combined_roles_keep_action_grants(self):
        perms=permissions_for("employee",["teacher","academic"])
        self.assertIn("student.admin_service.review",perms)
        self.assertIn("enterprise.score.write",perms)
        # 公共层只合并动作，未生成“主管部门+教务写入”的组合数据范围。
        result=access_for("employee",1,role_codes=["manager","academic"])
        self.assertNotIn("data_scope",result)

    def test_each_route_requires_its_declared_permission(self):
        @self.app.get("/protected-report")
        def protected(account=Depends(require_permission("report.read"))):
            return {"user_id":account.user_id}
        self.assertEqual(self.client.get("/protected-report").status_code,401)
        self.assertEqual(self.client.get("/protected-report",headers=self.headers(120)).status_code,403)
        self.assertEqual(self.client.get("/protected-report",headers=self.headers(121)).status_code,200)
        self.assertEqual(self.client.get("/protected-report",headers=self.headers(1)).status_code,200)
        self.assertEqual(self.client.get("/protected-report",headers=self.headers(122)).status_code,403)

    def test_anonymous_policy_does_not_touch_database_or_expose_private_pages(self):
        r=self.client.get("/api/v1/auth/public-access")
        self.assertEqual(r.status_code,200)
        self.assertNotIn("account",r.json()["data"]["pages"])
        self.assertEqual(set(r.json()["data"]["modules"]),{"common"})

    def test_visible_modules_follow_same_permissions(self):
        self.assertNotIn("report",access_for("employee",120)["modules"])
        self.assertIn("report",access_for("employee",121,role_codes=["manager"])["modules"])
        self.assertIn("report",access_for("admin",1)["modules"])
        self.assertNotIn("report",access_for("student",2)["modules"])

    def test_wildcards_are_not_accepted(self):
        for value in ["report.*","*",""]:
            with self.assertRaises(ValueError):
                require_permission(value)

    def test_invalid_or_duplicate_policy_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"policy.yaml"
            for content in ["roles: []", "version: 1\nversion: 1\n", "roles: {admin: {permissions: '*'}}"]:
                path.write_text(content,encoding="utf-8")
                load_access_control.cache_clear()
                with patch("app.config.settings.ACCESS_CONTROL_FILE",path):
                    with self.assertRaises(RuntimeError):
                        load_access_control()
        load_access_control.cache_clear()
        load_access_control()
