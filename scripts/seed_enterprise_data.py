"""Export and optionally insert synthetic fixtures into the local enterprise database.

Uses the primary .env and mysql CLI, deliberately excluding .env.student.local.
No persistent schema, existing business rows, authentication secrets, or external services are changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "scripts/sql/bk/企业智能助手/企业智能助手_测试数据.sql"
BASE = 910000
DATA: dict[str, list[dict]] = {}
PRIMARY_KEYS = {
    "org_department": "department_id", "employee": "employee_id",
    "customer_profile": "customer_id", "customer_followup": "followup_id",
    "employee_daily_report": "daily_report_id", "student_profile": "student_id",
    "student_staff_binding": "binding_id", "student_score": "score_id",
    "student_leave_request": "leave_request_id", "service_ticket": "ticket_id",
    "service_ticket_record": "ticket_record_id", "knowledge_entry": "knowledge_id",
    "business_notification": "notification_id", "operation_log": "operation_log_id",
}


class SQL(str):
    """A fixed SQL expression, never populated from user input."""


def at(hours=0):
    return SQL(f"TIMESTAMPADD(HOUR, {hours}, @eit_now)")


def add(table, **row):
    row.setdefault("created_at", at(-168))
    if table != "service_ticket_record":
        row.setdefault("updated_at", row["created_at"])
        row.setdefault("row_version", 1)
    DATA.setdefault(table, []).append(row)
    return row


def literal(value):
    if isinstance(value, SQL):
        return str(value)
    if value is None:
        return "NULL"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if isinstance(value, str):
        return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"
    return str(int(value)) if isinstance(value, bool) else str(value)


def build_data():
    DATA.clear()
    for n, code, name, parent in [
        (1, "HQ", "测试总部", None), (2, "SALES-A", "测试咨询一部", 1),
        (3, "SALES-B", "测试咨询二部", 1), (4, "ACADEMIC", "测试教务服务部", 1),
    ]:
        add("org_department", department_id=BASE+n, department_code="EIT-"+code,
            department_name=name, parent_department_id=BASE+parent if parent else None,
            function_description="接口测试组织，仅包含虚构人员和业务", employee_id=None)

    employees = [
        (1, "测试管理员", 1, ["employee", "admin"], "系统管理员", "active"),
        (2, "测试顾问甲", 2, ["employee", "consultant"], "留学顾问", "active"),
        (3, "测试主管甲", 2, ["employee", "manager"], "咨询主管", "active"),
        (4, "测试班主任甲", 4, ["employee", "teacher"], "班主任", "active"),
        (5, "测试教务", 4, ["employee", "academic"], "成绩管理员", "active"),
        (6, "测试普通员工", 2, ["employee"], "运营助理", "active"),
        (7, "测试顾问乙", 3, ["employee", "consultant"], "留学顾问", "active"),
        (8, "测试主管乙", 3, ["employee", "manager"], "咨询主管", "active"),
        (9, "测试班主任乙", 4, ["employee", "teacher"], "班主任", "active"),
        (10, "测试停用员工", 2, ["employee", "consultant"], "停用测试账号", "disabled"),
    ]
    for n, name, dep, roles, position, status in employees:
        add("employee", employee_id=BASE+n, employee_no=f"EIT-E{n:03}", full_name=name,
            department_id=BASE+dep, position_title=position, login_provider="test_fixture",
            login_subject=f"eit-employee-{n:03}", role_codes=roles,
            work_email=f"eit.employee.{n:03}@example.invalid", status=status,
            joined_date=SQL("DATE_SUB(@eit_day, INTERVAL 180 DAY)"))

    customers = [
        (1, "测试新客户", 2, 2, "new", "GB"),
        (2, "测试跟进客户", 2, 2, "contacting", "AU"),
        (3, "测试意向客户", 2, 2, "qualified", "GB"),
        (4, "测试签约客户甲", 2, 2, "signed", "GB"),
        (5, "测试流失客户", 7, 3, "lost", "CA"),
        (6, "测试签约客户乙", 7, 3, "signed", "AU"),
        (7, "测试归档客户", 2, 2, "signed", "GB"),
    ]
    for n, name, owner, dep, status, country in customers:
        add("customer_profile", customer_id=BASE+n, customer_no=f"EIT-C{n:03}",
            full_name=name, education_level="bachelor", target_country_code=country,
            source_channel="manual", source_reference=f"EIT-fixture-customer-{n:03}",
            employee_id=BASE+owner, department_id=BASE+dep, status=status,
            status_changed_at=at(-72), lost_reason="测试原因：预算调整，暂缓申请" if status=="lost" else None,
            is_archived=n==7, authority_source="local")

    for n, customer, employee, when, status, next_when, content in [
        (1, 2, 2, -48, "done", -24, "已完成首次意向沟通，下一次安排已执行"),
        (2, 2, 2, -24, "pending", -2, "约定回访申请材料，目前已到期待跟进"),
        (3, 3, 2, -12, "pending", 24, "已确认意向国家，明日核对院校清单"),
        (4, 4, 2, -96, "none", None, "签约资料已确认，暂无新的跟进安排"),
        (5, 5, 7, -80, "cancelled", -60, "客户暂缓申请，取消后续回访计划"),
        (6, 6, 7, -36, "pending", 48, "已签约，约定回访服务体验"),
        (7, 7, 2, -100, "done", -90, "服务已完成，历史记录随客户归档保留"),
    ]:
        add("customer_followup", followup_id=BASE+n, customer_id=BASE+customer,
            employee_id=BASE+employee, followup_at=at(when), channel="online",
            content=content, summary=content, followup_status=status,
            next_followup_at=at(next_when) if next_when is not None else None,
            created_at=at(when), updated_at=at(when+1))
    for row in DATA["customer_profile"]:
        history = [f for f in DATA["customer_followup"] if f["customer_id"]==row["customer_id"]]
        row["last_followup_at"] = history[-1]["followup_at"] if history else None

    for n, employee, dep, days, status, content in [
        (1, 2, 2, 0, "submitted", "跟进两位意向客户，完成一份院校清单，明日核对材料。"),
        (2, 6, 2, 0, "submitted", "整理咨询资料，协助核对三份客户档案。"),
        (3, 7, 3, 0, "submitted", "回访已签约客户，确认后续服务安排。"),
        (4, 4, 4, 0, "submitted", "处理学生请假及投诉，关注尚待学生确认的工单。"),
        (5, 2, 2, 1, "submitted", "完成昨日客户回访与资料整理。"),
        (6, 6, 2, 1, "void", "测试误提交内容，已作废，用于状态过滤。"),
    ]:
        submitted = SQL(f"TIMESTAMPADD(DAY, -{days}, GREATEST(TIMESTAMP(@eit_day) - INTERVAL 8 HOUR, TIMESTAMPADD(MINUTE,-5,@eit_now)))")
        add("employee_daily_report", daily_report_id=BASE+n, employee_id=BASE+employee,
            report_date=SQL(f"DATE_SUB(@eit_day, INTERVAL {days} DAY)"),
            department_id_at_submit=BASE+dep, submitted_content=content,
            ai_summary=content, status=status, submitted_at=submitted,
            created_at=submitted, updated_at=at(-1) if status=="void" else submitted,
            row_version=2 if status=="void" else 1)

    for n, name, customer, status, archived in [
        (1, "测试张同学", 4, "enrolled", False),
        (2, "测试张同学", None, "enrolled", False),
        (3, "测试李同学", 6, "enrolled", False),
        (4, "测试待分派学生", None, "enrolled", False),
        (5, "测试归档学生", 7, "completed", True),
    ]:
        add("student_profile", student_id=BASE+n, student_no=f"EIT-S{n:03}", full_name=name,
            customer_id=BASE+customer if customer else None, department_id=BASE+4,
            login_provider="test_fixture", login_subject=f"eit-student-{n:03}",
            status=status, is_archived=archived)

    bindings = [
        (1, 1, 4, "class_teacher", None, True, False),
        (2, 2, 4, "class_teacher", None, True, False),
        (3, 3, 9, "class_teacher", None, True, False),
        (4, 1, 4, "service_advisor", None, True, False),
        (5, 2, 4, "service_advisor", None, True, False),
        (6, 3, 9, "service_advisor", None, True, False),
        (7, 1, 5, "score_editor", "EIT-ENGLISH", False, False),
        (8, 1, 5, "score_editor", "EIT-MATH", False, False),
        (9, 2, 5, "score_editor", "EIT-ENGLISH", False, False),
        (10, 2, 5, "score_editor", "EIT-MATH", False, False),
        (11, 3, 5, "score_editor", "EIT-ENGLISH", False, False),
        (12, 5, 9, "class_teacher", None, True, True),
        (13, 1, 9, "class_teacher", None, False, True),
    ]
    for n, student, employee, relation, course, primary, expired in bindings:
        add("student_staff_binding", binding_id=BASE+n, student_id=BASE+student,
            employee_id=BASE+employee, relation_type=relation, course_scope_code=course,
            is_primary=primary, valid_from=at(-720), valid_to=at(-72) if expired else None,
            status="disabled" if expired else "active", created_at=at(-720))

    for n, student, course, assessment, attempt, score, maximum, status in [
        (1, 1, "EIT-ENGLISH", "MIDTERM", 1, 86, 100, "valid"),
        (2, 1, "EIT-MATH", "MIDTERM", 1, 92, 100, "valid"),
        (3, 2, "EIT-ENGLISH", "MIDTERM", 1, 58, 100, "valid"),
        (4, 2, "EIT-ENGLISH", "MIDTERM", 2, 76, 100, "valid"),
        (5, 3, "EIT-ENGLISH", "MIDTERM", 1, 41, 50, "valid"),
        (6, 2, "EIT-MATH", "QUIZ-VOID", 1, 0, 100, "void"),
    ]:
        add("student_score", score_id=BASE+n, student_id=BASE+student,
            course_code=course, term_code="EIT-2026-AUTUMN", assessment_code=assessment,
            attempt_no=attempt, score_value=score, max_score=maximum,
            employee_id=BASE+5, status=status, created_at=at(-96), updated_at=at(-72),
            row_version=2 if n in (1, 6) else 1)

    for n, student, approver, status, start, end, reason, comment in [
        (1, 1, 4, "submitted", 24, 48, "测试病假：需要休息一天", None),
        (2, 2, 4, "approved", 72, 80, "测试事假：办理学校手续", "同意，请按时返校"),
        (3, 3, 9, "rejected", 48, 56, "测试事假：申请时间与考试冲突", "请调整时间后重新提交"),
        (4, 2, 4, "withdrawn", 96, 104, "测试撤回：原计划已经取消", None),
        (5, 4, None, "submitted", 24, 32, "测试异常分派：尚未关联有效班主任", None),
    ]:
        decided = status in ("approved", "rejected")
        add("student_leave_request", leave_request_id=BASE+n, request_no=f"EIT-L{n:03}",
            student_id=BASE+student, leave_type="sick" if n==1 else "personal",
            start_at=at(start), end_at=at(end), reason=reason,
            approver_employee_id=BASE+approver if approver else None, status=status,
            submitted_at=at(-24), decision_employee_id=BASE+approver if decided else None,
            decision_at=at(-12) if decided else None, decision_comment=comment,
            created_at=at(-24), updated_at=at(-12) if status!="submitted" else at(-24),
            row_version=2 if status!="submitted" else 1)

    for n, student, owner, status, category, text in [
        (1, 4, None, "open", "application", "测试投诉：尚未分派处理人"),
        (2, 1, 4, "assigned", "visa", "测试投诉：希望了解签证办理进度"),
        (3, 2, 4, "processing", "teaching", "测试投诉：课程安排需要进一步协调"),
        (4, 1, 4, "awaiting_student", "application", "测试建议：希望补充申请材料说明"),
        (5, 3, 9, "closed", "service", "测试投诉：希望补充服务时间说明"),
        (6, 3, 9, "reopened", "teaching", "测试投诉：首次处理后仍有问题，学生已重开"),
    ]:
        solved = n in (4, 5, 6)
        add("service_ticket", ticket_id=BASE+n, ticket_no=f"EIT-T{n:03}",
            student_id=BASE+student, ticket_type="suggestion" if n==4 else "complaint",
            category_code=category, content=text, ai_summary=text,
            priority="high" if n in (1, 6) else "normal",
            employee_id=BASE+owner if owner else None, handling_department_id=BASE+4,
            status=status, first_response_at=at(-36) if n>=3 else None,
            response_due_at=at(-24), resolution_due_at=at(-1) if n==3 else at(24),
            solution="测试解决方案：已补充说明并与学生确认后续安排" if solved else None,
            resolved_at=at(-12) if solved else None, closed_at=at(-6) if n==5 else None,
            reopen_count=1 if n==6 else 0, satisfaction_score=5 if n==5 else None,
            created_at=at(-48), updated_at=at({1:-48,2:-47,3:-24,4:-12,5:-5,6:-3}[n]),
            row_version={1:1, 2:2, 3:4, 4:4, 5:6, 6:5}[n])

    record_no = 0
    def record(ticket, kind, who, actor, status, when, content, visibility="student_visible", cycle=1):
        nonlocal record_no
        record_no += 1
        add("service_ticket_record", ticket_record_id=BASE+record_no,
            ticket_id=BASE+ticket, record_type=kind,
            employee_id=BASE+actor if who=="employee" else None,
            student_id=BASE+actor if who=="student" else None,
            service_code="test_fixture_seed" if who=="service" else None,
            content=content, visibility=visibility, to_status=status, cycle_no=cycle,
            record_key=f"EIT-record-{record_no:03}", created_at=at(when))
    record(1, "create", "service", None, "open", -48, "测试自动回执：已收到反馈，尚未分派")
    for ticket, teacher in [(2,4), (3,4), (4,4), (5,9), (6,9)]:
        record(ticket, "assign", "service", None, "assigned", -47,
            "按测试关系分派给处理老师", "internal")
        if ticket>=3:
            record(ticket, "response", "employee", teacher, "processing", -36,
                "已人工接手，正在核实并协调处理")
        if ticket in (4,5,6):
            record(ticket, "resolve", "employee", teacher, "awaiting_student", -12,
                "测试解决方案：已补充说明并与学生确认后续安排")
    record(3, "note", "employee", 4, "processing", -24, "内部测试备注：等待相关部门回复", "internal")
    record(5, "confirm", "student", 3, "closed", -6, "学生确认问题已解决")
    record(5, "rate", "student", 3, "closed", -5, "学生实际评价：5分")
    record(6, "reopen", "student", 3, "reopened", -3, "学生反馈仍未解决，进入第2轮", cycle=2)

    for n, title, kind, state, scope, index, expiry in [
        (1, "测试新人入职指南", "faq", "published", None, "ready", None),
        (2, "测试咨询部客户跟进规范", "faq", "published", 2, "ready", None),
        (3, "测试请假流程制度", "document", "published", None, "ready", None),
        (4, "测试待审核制度", "document", "draft", None, "pending", None),
        (5, "测试停用旧制度", "faq", "disabled", None, "ready", -24),
        (6, "测试索引失败制度", "document", "draft", None, "failed", None),
    ]:
        reviewed = state in ("published", "disabled")
        add("knowledge_entry", knowledge_id=BASE+n, entry_code=f"EIT-K{n:03}", title=title,
            entry_type=kind, category_code="onboarding" if n==1 else "policy",
            question="测试问题：新人如何了解工作流程？" if kind=="faq" else None,
            answer="测试答案：先查看内部指南，再联系本部门负责人确认安排。" if kind=="faq" else None,
            content_text="测试制度正文：学生提交申请，由当前有效班主任审批，结果通过站内消息通知。" if kind=="document" else None,
            source_reference=f"EIT-inline-knowledge-{n:03}", employee_id=BASE+1,
            access_department_id=BASE+scope if scope else None, status=state,
            reviewer_employee_id=BASE+1 if reviewed else None,
            reviewed_at=at(-96) if reviewed else None,
            effective_from=at(-72) if reviewed else None,
            expires_at=at(expiry) if expiry else None, index_status=index)

    notification_specs = [
        (1, "leave", 1, "leave.submitted", "employee", 4, "sent", False),
        (2, "leave", 2, "leave.approved", "student", 2, "sent", True),
        (3, "ticket", 4, "ticket.resolved", "student", 1, "sent", False),
        (4, "customer_followup", 2, "followup.due", "employee", 2, "pending", False),
        (5, "ticket", 3, "ticket.overdue", "employee", 4, "failed", False),
        (6, "leave", 3, "leave.rejected", "student", 3, "dead_letter", False),
        (7, "leave", 5, "leave.unassigned", "employee", 1, "pending", False),
    ]
    for n, entity, target, event, who, recipient, state, read in notification_specs:
        add("business_notification", notification_id=BASE+n, entity_type=entity,
            entity_id=BASE+target, event_code="seed."+event,
            employee_id=BASE+recipient if who=="employee" else None,
            student_id=BASE+recipient if who=="student" else None, channel="in_app",
            title="接口测试业务通知", content="这是虚构的站内测试通知，请进入对应业务查看详情。",
            dedupe_key=f"EIT-notification-{n:03}", delivery_status=state,
            attempt_count=1 if state=="sent" else 2 if state=="failed" else 5 if state=="dead_letter" else 0,
            next_retry_at=at(1) if state=="failed" else None,
            sent_at=at(-1) if state=="sent" else None, read_at=at(0) if read else None,
            last_error_code="TEST_RETRY_EXHAUSTED" if state=="dead_letter" else "TEST_TRANSIENT_FAILURE" if state=="failed" else None,
            created_at=at(-2), updated_at=at(0) if read else at(-1))

    def audit(n, entity_type, entity_id, action, before=None, after=None, employee=None,
              student=None, status="succeeded", reason="导入虚构接口测试数据", when=-1):
        request_key=f"EIT-operation-{n:03}"
        actor = ["employee", employee] if employee else ["student", student] if student else ["service", "test_fixture_seed"]
        parameters={"entity_type":entity_type,"entity_id":entity_id,"action":action,"after":after}
        canonical=lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        add("operation_log", operation_log_id=BASE+n,
            operation_key=hashlib.sha256(canonical([actor,action,request_key]).encode()).hexdigest(),
            employee_id=BASE+employee if employee else None,
            student_id=BASE+student if student else None,
            service_code="test_fixture_seed" if not employee and not student else None,
            action_code=action, entity_type=entity_type, entity_id=entity_id,
            request_key=request_key, parameters_hash=hashlib.sha256(canonical(parameters).encode()).hexdigest(),
            before_data=before, after_data=after, change_reason=reason,
            operation_status=status, result_reference={"entity_id":entity_id,"seed":True} if status=="succeeded" else None,
            error_code="TEST_DUPLICATE_REQUEST" if status=="failed" else None,
            finished_at=at(when) if status in ("succeeded","failed") else None,
            created_at=at(when), updated_at=at(when))

    entity_types={"org_department":"department", "employee":"employee", "customer_profile":"customer",
        "customer_followup":"customer_followup", "employee_daily_report":"daily_report",
        "student_profile":"student", "student_staff_binding":"student_binding", "student_score":"score",
        "student_leave_request":"leave", "service_ticket":"ticket", "service_ticket_record":"ticket_record",
        "knowledge_entry":"knowledge", "business_notification":"notification"}
    for n, (table, rows) in enumerate(list(DATA.items()), 1):
        audit(n, entity_types[table], rows[0][PRIMARY_KEYS[table]], "seed.import",
            after={"fixture_table":table,"fixture_count":len(rows)}, when=0)
    audit(14, "score", BASE+1, "correct_score", {"score_value":82,"max_score":100},
        {"score_value":86,"max_score":100,"row_version":2}, employee=5,
        reason="测试更正：原试卷核分遗漏4分", when=-72)
    audit(15, "score", BASE+6, "void_score", {"status":"valid","score_value":0,"max_score":100},
        {"status":"void","score_value":0,"max_score":100,"row_version":2}, employee=5,
        reason="测试作废：误录的随堂考核", when=-72)
    audit(16, "leave", BASE+2, "approve_leave", {"status":"submitted"},
        {"status":"approved","row_version":2}, employee=4, reason="同意，请按时返校", when=-12)
    audit(17, "leave", BASE+3, "reject_leave", {"status":"submitted"},
        {"status":"rejected","row_version":2}, employee=9, reason="请调整时间后重新提交", when=-12)
    audit(18, "ticket", BASE+6, "reopen_ticket", {"status":"awaiting_student","reopen_count":0},
        {"status":"reopened","reopen_count":1,"row_version":5}, student=3,
        reason="测试反馈：首次处理未解决", when=-3)
    audit(19, "daily_report", BASE+6, "void_daily_report", {"status":"submitted"},
        {"status":"void","row_version":2}, employee=6, reason="测试误提交日报")
    audit(20, "customer", None, "create_customer", employee=2, status="failed",
        reason="测试失败回执：模拟重复业务请求，未创建客户")


def assertions():
    checks=[]
    for table, rows in DATA.items():
        pk=PRIMARY_KEYS[table]
        ids=",".join(str(row[pk]) for row in rows)
        checks.append(("count_"+table, f"(SELECT COUNT(*) FROM `{table}` WHERE `{pk}` IN ({ids}))={len(rows)}"))
    checks += [
        ("one_primary_teacher", "NOT EXISTS (SELECT student_id FROM student_staff_binding WHERE student_id BETWEEN 910001 AND 910005 AND relation_type='class_teacher' AND status='active' AND is_primary=1 AND valid_from<=@eit_now AND (valid_to IS NULL OR valid_to>@eit_now) GROUP BY student_id HAVING COUNT(*)>1)"),
        ("score_permissions", "NOT EXISTS (SELECT 1 FROM student_score s WHERE s.score_id BETWEEN 910001 AND 910006 AND NOT EXISTS (SELECT 1 FROM student_staff_binding b WHERE b.student_id=s.student_id AND b.employee_id=s.employee_id AND b.relation_type='score_editor' AND b.course_scope_code=s.course_code AND b.status='active' AND b.valid_from<=@eit_now AND (b.valid_to IS NULL OR b.valid_to>@eit_now)))"),
        ("leave_approvers", "NOT EXISTS (SELECT 1 FROM student_leave_request l WHERE l.leave_request_id BETWEEN 910001 AND 910005 AND l.approver_employee_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM student_staff_binding b WHERE b.student_id=l.student_id AND b.employee_id=l.approver_employee_id AND b.relation_type='class_teacher' AND b.status='active' AND b.valid_from<=@eit_now AND (b.valid_to IS NULL OR b.valid_to>@eit_now)))"),
        ("ticket_owners", "NOT EXISTS (SELECT 1 FROM service_ticket t WHERE t.ticket_id BETWEEN 910001 AND 910006 AND t.employee_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM student_staff_binding b WHERE b.student_id=t.student_id AND b.employee_id=t.employee_id AND b.relation_type='service_advisor' AND b.status='active'))"),
        ("student_ticket_records", "NOT EXISTS (SELECT 1 FROM service_ticket_record r JOIN service_ticket t ON t.ticket_id=r.ticket_id WHERE r.ticket_record_id BETWEEN 910001 AND 910100 AND r.student_id IS NOT NULL AND r.student_id<>t.student_id)"),
        ("record_cycles", "NOT EXISTS (SELECT 1 FROM service_ticket_record r JOIN service_ticket t ON t.ticket_id=r.ticket_id WHERE r.ticket_record_id BETWEEN 910001 AND 910100 AND r.cycle_no>t.reopen_count+1)"),
        ("notification_targets", "NOT EXISTS (SELECT 1 FROM business_notification n WHERE n.notification_id BETWEEN 910001 AND 910007 AND ((n.entity_type='leave' AND NOT EXISTS (SELECT 1 FROM student_leave_request l WHERE l.leave_request_id=n.entity_id)) OR (n.entity_type='ticket' AND NOT EXISTS (SELECT 1 FROM service_ticket t WHERE t.ticket_id=n.entity_id)) OR (n.entity_type='customer_followup' AND NOT EXISTS (SELECT 1 FROM customer_followup f WHERE f.followup_id=n.entity_id))))"),
        ("notification_students", "NOT EXISTS (SELECT 1 FROM business_notification n WHERE n.notification_id BETWEEN 910001 AND 910007 AND n.student_id IS NOT NULL AND ((n.entity_type='leave' AND NOT EXISTS (SELECT 1 FROM student_leave_request l WHERE l.leave_request_id=n.entity_id AND l.student_id=n.student_id)) OR (n.entity_type='ticket' AND NOT EXISTS (SELECT 1 FROM service_ticket t WHERE t.ticket_id=n.entity_id AND t.student_id=n.student_id))))"),
        ("six_roles", "(SELECT COUNT(DISTINCT j.role_code) FROM employee e,JSON_TABLE(e.role_codes,'$[*]' COLUMNS(role_code VARCHAR(32) PATH '$')) j WHERE e.employee_id BETWEEN 910001 AND 910010)=6"),
        ("terminal_ticket_times", "NOT EXISTS (SELECT 1 FROM service_ticket WHERE ticket_id BETWEEN 910001 AND 910006 AND ((status='closed' AND (closed_at IS NULL OR resolved_at IS NULL)) OR (status='awaiting_student' AND (resolved_at IS NULL OR closed_at IS NOT NULL)) OR (status='reopened' AND (reopen_count<1 OR closed_at IS NOT NULL))))"),
    ]
    return checks


def export_sql():
    build_data()
    lines=[
        "-- 企业智能助手虚构接口测试数据；由 scripts/seed_enterprise_data.py 生成。",
        "-- 仅适用于企业独立14表模型；固定ID从910001起，业务编号EIT-前缀。",
        "-- 全部INSERT为普通写入，重复ID或唯一键冲突会报错，不忽略错误、不覆盖已有记录。",
        "-- 整体执行；失败必须ROLLBACK并断开连接，禁止客户端遇错继续执行COMMIT。",
        "-- 联系电话密文留空，不伪造加密格式；不会创建真实登录账号、Dify索引或外部通知。",
        "SET NAMES utf8mb4;", "SET SESSION time_zone = '+00:00';",
        "SET SESSION sql_mode = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';",
        "USE `education_agent`;", "SET @eit_now = UTC_TIMESTAMP(3);",
        "SET @eit_day = DATE(TIMESTAMPADD(HOUR,8,@eit_now));",
        "CREATE TEMPORARY TABLE `_eit_seed_check` (`assertion` VARCHAR(100), `passed` INT NOT NULL, CHECK (`passed`=1));",
        "START TRANSACTION;",
    ]
    for table, rows in DATA.items():
        lines.append(f"\n-- {table}: {len(rows)} rows")
        for row in rows:
            columns=", ".join("`"+key+"`" for key in row)
            values=", ".join(literal(value) for value in row.values())
            lines.append(f"INSERT INTO `{table}` ({columns}) VALUES ({values});")
        if table=="employee":
            lines += [
                "UPDATE org_department SET employee_id=910003,row_version=2,updated_at=@eit_now WHERE department_id=910002 AND department_code='EIT-SALES-A';",
                "UPDATE org_department SET employee_id=910008,row_version=2,updated_at=@eit_now WHERE department_id=910003 AND department_code='EIT-SALES-B';",
            ]
    lines.append("\n-- Any failed assertion aborts the client and rolls back this transaction.")
    for name, condition in assertions():
        lines.append(f"INSERT INTO `_eit_seed_check` VALUES ({literal(name)}, ({condition}));")
    lines += ["COMMIT;", "SELECT COUNT(*) AS passed_seed_assertions FROM `_eit_seed_check`;", "DROP TEMPORARY TABLE `_eit_seed_check`;", ""]
    SQL_PATH.write_text("\n".join(lines), encoding="utf-8")
    return "\n".join(lines)


def mysql(cfg, query=None, sql=None):
    executable=shutil.which("mysql")
    if not executable:
        raise RuntimeError("mysql CLI is required on PATH")
    env=os.environ.copy()
    env["MYSQL_PWD"]=cfg.get("DB_PASSWORD") or ""
    args=[executable,"--no-defaults","--protocol=TCP", "--host="+cfg.get("DB_HOST","127.0.0.1"),
        "--port="+cfg.get("DB_PORT","3306"),"--user="+cfg.get("DB_USER","root"),
        "--connect-timeout=5","--default-character-set=utf8mb4","--batch","--raw","--skip-column-names"]
    if query:
        args += ["--execute",query]
    result=subprocess.run(args, input=sql.encode("utf-8") if sql else None, env=env, capture_output=True)
    if result.returncode:
        # mysql is invoked WITHOUT --force: any failed INSERT/assertion closes
        # the connection before COMMIT and rolls back InnoDB changes.
        raise RuntimeError(result.stderr.decode("utf-8",errors="replace").strip())
    return result.stdout.decode("utf-8",errors="replace")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply",action="store_true",help="Insert fixtures into primary .env local education_agent")
    args=parser.parse_args()
    sql=export_sql()
    print(json.dumps({"exported_sql":SQL_PATH.relative_to(ROOT).as_posix(),
        "planned_counts":{table:len(rows) for table,rows in DATA.items()},
        "total_rows":sum(map(len,DATA.values()))},ensure_ascii=True,indent=2))
    if not args.apply:
        return
    cfg=dotenv_values(ROOT/".env")
    if cfg.get("DB_HOST","127.0.0.1") not in ("127.0.0.1","localhost","::1") or cfg.get("DB_NAME","education_agent")!="education_agent":
        raise RuntimeError("Only local education_agent from the primary .env is allowed")
    tables=set(mysql(cfg,"SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='education_agent' AND TABLE_TYPE='BASE TABLE';").split())
    if set(DATA)-tables:
        raise RuntimeError("Missing enterprise tables: "+", ".join(sorted(set(DATA)-tables)))
    probes=[]
    for table,rows in DATA.items():
        pk=PRIMARY_KEYS[table]
        ids=",".join(str(row[pk]) for row in rows)
        probes.append(f"SELECT '{table}',COUNT(*) FROM education_agent.`{table}` WHERE `{pk}` IN ({ids})")
    collisions=[line for line in mysql(cfg,";".join(probes)+";").splitlines() if line.strip() and int(line.split("\t")[1])]
    if collisions:
        raise RuntimeError("Seed IDs already exist; no data changed. Existing fixtures may have been modified by API tests. Do not overwrite them: "+"; ".join(collisions))
    print("SEED_ASSERTIONS_PASSED="+mysql(cfg,sql=sql).strip())
    result=mysql(cfg,";".join(probes)+";")
    counts={line.split("\t")[0]:int(line.split("\t")[1]) for line in result.splitlines() if line.strip()}
    if counts!={table:len(rows) for table,rows in DATA.items()}:
        raise RuntimeError("Post-commit seed counts do not match the manifest")
    print(json.dumps({"database":"education_agent","inserted_counts":counts,"total_rows":sum(counts.values())},indent=2))


if __name__=="__main__":
    main()
