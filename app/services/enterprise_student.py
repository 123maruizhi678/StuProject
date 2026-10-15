"""学生与成绩固定业务规则：真实员工身份、课程范围、幂等、并发与审计。"""
from datetime import datetime, timezone
import hashlib
import json

import yaml
from fastapi import Depends
from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import get_current_account
from app.core.response import BusinessException
from app.database import get_db
from app.models.enterprise_student import Employee, OperationLog, StudentProfile, StudentScore, StudentStaffBinding
from app.models.user_account import UserAccount


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def error(code, message):
    raise BusinessException(message, code)


def current_employee(account: UserAccount = Depends(get_current_account), db: Session = Depends(get_db)) -> Employee:
    if account.identity_type != "employee" or not account.employee_id:
        error(403, "需要绑定员工身份")
    actor = db.get(Employee, account.employee_id)
    if actor is None or actor.status != "active":
        error(403, "员工不存在、已停用或已离职")
    if not set(actor.role_codes or []) & {"academic", "teacher"}:
        error(403, "需要教务或老师职责；管理员身份不自动授予学生数据权限")
    return actor


def course_catalog():
    with settings.ENTERPRISE_COURSES_FILE.open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
        error(503, "受控教务课程目录不可用")
    return data


def binding_conditions(actor, now=None):
    b = StudentStaffBinding
    now = now or utcnow()
    return [b.employee_id == actor.employee_id, b.status == "active", b.valid_from <= now,
            or_(b.valid_to.is_(None), b.valid_to > now)]


def student_scope(actor):
    b = StudentStaffBinding
    relations = []
    if "academic" in actor.role_codes:
        relations.append("score_editor")
    if "teacher" in actor.role_codes:
        relations += ["class_teacher", "service_advisor"]
    return exists(select(b.binding_id).where(*binding_conditions(actor), b.student_id == StudentProfile.student_id,
                                            b.relation_type.in_(relations)))


def score_scope(actor):
    b = StudentStaffBinding
    if "academic" not in actor.role_codes:
        error(403, "成绩查询和写入需要 academic 角色")
    return exists(select(b.binding_id).where(*binding_conditions(actor), b.student_id == StudentScore.student_id,
        b.relation_type == "score_editor", b.course_scope_code == StudentScore.course_code,
        b.course_scope_code.is_not(None), b.course_scope_code != ""))


def student_data(row, actor):
    result = {"student_id": str(row.student_id), "student_no": row.student_no, "full_name": row.full_name,
              "department_id": str(row.department_id), "status": row.status, "is_archived": row.is_archived,
              "version": row.row_version}
    if actor.employee_id in settings.ENTERPRISE_STUDENT_MAINTAINER_IDS:
        result.update(external_student_id=row.external_student_id, crm_student_id=row.crm_student_id)
    return result


def get_student(db, actor, student_id):
    row = db.scalar(select(StudentProfile).where(StudentProfile.student_id == student_id, student_scope(actor)))
    if row is None:
        error(404, "学生不存在或无权访问")
    result = student_data(row, actor)
    bindings = db.scalars(select(StudentStaffBinding).where(*binding_conditions(actor), StudentStaffBinding.student_id == student_id)).all()
    result["staff_bindings"] = [{"binding_id": str(b.binding_id), "employee_id": str(b.employee_id),
        "relation_type": b.relation_type, "course_scope_code": b.course_scope_code,
        "valid_from": b.valid_from, "valid_to": b.valid_to} for b in bindings]
    return result


def paginate(db, statement, page, page_size, serialize):
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
    rows = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [serialize(r) for r in rows], "total": total, "page": page, "page_size": page_size}


def list_students(db, actor, *, page=1, page_size=20, keyword=None, student_no=None, department_id=None, status=None, is_archived=False):
    s = StudentProfile
    stmt = select(s).where(student_scope(actor), s.is_archived == is_archived)
    if keyword:
        stmt = stmt.where(or_(s.full_name.contains(keyword, autoescape=True), s.student_no.contains(keyword, autoescape=True)))
    for name, value in (("student_no", student_no), ("department_id", department_id), ("status", status)):
        if value is not None:
            stmt = stmt.where(getattr(s, name) == value)
    return paginate(db, stmt.order_by(s.student_id), page, page_size, lambda row: student_data(row, actor))


def score_data(row, catalog=None):
    catalog = catalog if catalog is not None else course_catalog()
    return {"score_id": str(row.score_id), "student_id": str(row.student_id), "course_code": row.course_code,
            "course_name": catalog.get(row.course_code), "term_code": row.term_code,
            "assessment_code": row.assessment_code, "attempt_no": row.attempt_no,
            "score_value": str(row.score_value), "max_score": str(row.max_score),
            "employee_id": str(row.employee_id), "status": row.status, "version": row.row_version}


def authorized_score(db, actor, score_id):
    row = db.scalar(select(StudentScore).where(StudentScore.score_id == score_id, score_scope(actor)))
    if row is None:
        error(404, "成绩不存在或无课程访问权限")
    return row


def get_score(db, actor, score_id):
    row = authorized_score(db, actor, score_id)
    result = score_data(row)
    editor = db.get(Employee, row.employee_id)
    result["employee_name"] = editor.full_name if editor else None
    result.update(created_at=row.created_at, updated_at=row.updated_at)
    logs = db.scalars(select(OperationLog).where(OperationLog.entity_type == "student_score",
        OperationLog.entity_id == score_id, OperationLog.operation_status == "succeeded").order_by(OperationLog.operation_log_id)).all()
    result["history"] = [{"operation_id": str(log.operation_log_id), "employee_id": str(log.employee_id),
        "action": log.action_code, "before": log.before_data, "after": log.after_data,
        "change_reason": log.change_reason, "finished_at": log.finished_at} for log in logs]
    return result


def list_scores(db, actor, *, page=1, page_size=20, student_id=None, course_code=None, term_code=None,
                assessment_code=None, attempt_no=None, status="valid"):
    s = StudentScore
    stmt = select(s).where(score_scope(actor))
    for name, value in (("student_id", student_id), ("course_code", course_code), ("term_code", term_code),
                        ("assessment_code", assessment_code), ("attempt_no", attempt_no), ("status", status)):
        if value is not None:
            stmt = stmt.where(getattr(s, name) == value)
    catalog = course_catalog()
    return paginate(db, stmt.order_by(s.created_at.desc(), s.score_id.desc()), page, page_size, lambda row: score_data(row, catalog))


def can_write(db, actor, student_id, course):
    score_scope(actor)  # 固定角色检查，即便目录与绑定存在也不能替代。
    if settings.ENTERPRISE_SCORE_AUTHORITY != "local":
        error(403, "教务为只读权威来源，禁止本地修改成绩")
    student = db.scalar(select(StudentProfile).where(StudentProfile.student_id == student_id, student_scope(actor)))
    if student is None:
        error(404, "学生不存在或无权访问")
    if student.is_archived:
        error(409, "已归档学生不能新增或更改成绩")
    b = StudentStaffBinding
    if db.scalar(select(b.binding_id).where(*binding_conditions(actor), b.student_id == student_id,
        b.relation_type == "score_editor", b.course_scope_code == course, b.course_scope_code != "")) is None:
        error(403, "没有该学生及课程的有效成绩编辑关系")
    if course not in course_catalog():
        error(400, "课程编码不在受控教务目录中")


def operation_identity(actor, action, key, payload):
    op_key = hashlib.sha256(f"{actor.employee_id}:{action}:{key}".encode()).hexdigest()
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return op_key, digest


def replay(db, op_key, digest):
    log = db.scalar(select(OperationLog).where(OperationLog.operation_key == op_key))
    if log is None:
        return None
    if log.parameters_hash != digest:
        error(409, "同一 Idempotency-Key 的参数不同")
    if log.operation_status != "succeeded":
        error(409, "该逻辑请求正在处理或需核实")
    return log.result_reference


def mutate_score(db, actor, action, payload, key, score_id=None):
    data = payload.model_dump(mode="json")
    for name in ("score_value", "max_score"):
        if data.get(name) is not None:
            data[name] = format(getattr(payload, name), ".2f")
    before_row = None
    if score_id is None:
        student_id, course = payload.student_id, payload.course_code
    else:
        before_row = authorized_score(db, actor, score_id)
        student_id, course = before_row.student_id, before_row.course_code
        data["score_id"] = str(score_id)
    can_write(db, actor, student_id, course)
    op_key, digest = operation_identity(actor, action, key, data)
    repeated = replay(db, op_key, digest)
    if repeated is not None:
        return repeated
    before = score_data(before_row) if before_row else None
    log = OperationLog(operation_key=op_key, employee_id=actor.employee_id, action_code=action,
        entity_type="student_score", request_key=key, parameters_hash=digest, before_data=before,
        change_reason=getattr(payload, "change_reason", None), operation_status="processing")
    try:
        db.add(log)
        db.flush()  # 先占用操作唯一键，阻止同请求并发重复执行。
        if before_row is None:
            row = StudentScore(**payload.model_dump(), employee_id=actor.employee_id)
            db.add(row)
            db.flush()  # 包括 void 行的组合唯一键仍由数据库约束。
        else:
            if before_row.status != "valid":
                error(409, "已作废成绩不能更正或重复作废")
            if before_row.row_version != payload.expected_version:
                error(409, "成绩版本冲突，请刷新后重试")
            values = {"employee_id": actor.employee_id, "row_version": StudentScore.row_version + 1, "updated_at": utcnow()}
            if action == "score.void":
                values["status"] = "void"
            else:
                value = payload.score_value if payload.score_value is not None else before_row.score_value
                maximum = payload.max_score if payload.max_score is not None else before_row.max_score
                if maximum <= 0 or value < 0 or value > maximum:
                    error(400, "要求 max_score > 0 且 0 <= score_value <= max_score")
                values.update(score_value=value, max_score=maximum)
            changed = db.execute(update(StudentScore).where(StudentScore.score_id == score_id,
                StudentScore.row_version == payload.expected_version, StudentScore.status == "valid").values(**values))
            if changed.rowcount != 1:
                error(409, "成绩状态或版本冲突")
            db.flush()
            db.refresh(before_row)
            row = before_row
        after = score_data(row)
        result = {**after, "operation_id": str(log.operation_log_id), "operation_status": "succeeded"}
        log.entity_id, log.after_data = row.score_id, after
        log.result_reference, log.operation_status, log.finished_at = result, "succeeded", utcnow()
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        repeated = replay(db, op_key, digest)
        if repeated is not None:
            return repeated
        error(409, "成绩业务键已存在（包括已作废记录），或关联对象发生冲突")
    except Exception:
        db.rollback()
        raise
