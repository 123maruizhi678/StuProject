"""学生业务固定写入规则；所有变更、幂等回执和通知在同一数据库事务中保存。"""

import hashlib
import json
from datetime import timedelta, datetime
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import select, insert, update, and_, or_
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.core.common.response import BusinessException
from app.core.student.student_auth import Principal
from app.models import common as shared
from app.models.student.student import (
    MentalHealthProfile,
    MentalWarning,
    StudentAcademicEvent,
    StudentAcademicReminder,
    StudentApplicationProgress,
)
from app.models.student.student_types import utcnow
from app.schemas.student.student import as_utc

profiles = MentalHealthProfile.__table__
warnings = MentalWarning.__table__
events = StudentAcademicEvent.__table__
reminders = StudentAcademicReminder.__table__
progress = StudentApplicationProgress.__table__


def digest(value):
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def notification_key(entity_type,entity_id,event,student_id,employee_id,version,channel='in_app'):
    return event+':'+digest([entity_type,entity_id,event,student_id,employee_id,version,channel])


def reminder_generation(row):
    # DATETIME(6)更新时间是提醒设置代次；任务状态更新必须保留该时间。
    return digest([row["id"], row["event_version"], row["updated_at"].isoformat(timespec="microseconds")])[
        :16
    ]


def next_setting_time(row=None):
    now = utcnow()
    return max(now, row["updated_at"] + timedelta(microseconds=1)) if row else now


def row_id(table):
    return next(iter(table.primary_key.columns))


def public_time(value):
    return value.isoformat(timespec="microseconds") + "Z" if value else None


def public_row(row):
    return {k: public_time(v) if isinstance(v, datetime) else v for k, v in row.items()}


def leave_public(row):
    """B.5唯一对外字段，禁止透传请求摘要和内部JSON。"""
    fields=('student_id','apply_type','apply_content','approval_status','leave_start_at','leave_end_at',
            'reviewer_id','reviewed_at','approval_comment','row_version','created_at','updated_at')
    return public_row({'apply_id':row['id'],'leave_type':(row['edu_related_data'] or {}).get('leave_type'),**{k:row[k] for k in fields}})


class StudentService:
    def __init__(self, db):
        self.db = db

    def lock_business_prefix(self, student_id, employee_ids=()):
        """052总锁序：部门→员工→学生→关系；之后才锁业务对象。"""
        student = self.student_record(student_id)
        e, d, b = shared.employee, shared.org_department, shared.student_staff_binding
        related = self.db.execute(select(b.c.employee_id).where(b.c.student_id==student_id)).scalars().all()
        ids = sorted(set(related) | {i for i in employee_ids if i is not None})
        departments = {student['department_id']}
        if ids:
            departments.update(self.db.execute(select(e.c.department_id).where(e.c.employee_id.in_(ids))).scalars())
        self.db.execute(select(d.c.department_id).where(d.c.department_id.in_(departments)).order_by(d.c.department_id).with_for_update()).all()
        if ids:
            self.db.execute(select(e.c.employee_id).where(e.c.employee_id.in_(ids)).order_by(e.c.employee_id).with_for_update()).all()
        self.db.execute(select(shared.student_profile.c.student_id).where(shared.student_profile.c.student_id==student_id).with_for_update()).all()
        self.db.execute(select(b.c.binding_id).where(b.c.student_id==student_id).order_by(b.c.binding_id).with_for_update()).all()

    def student(self, actor):
        if actor.actor_type != "student":
            raise BusinessException("此操作仅限学生本人", 403)
        self.check_account_link(actor)
        return self.student_record(actor.actor_id)

    def check_account_link(self,actor):
        """模型调用或等待锁之后再次核对账号当前关联，业务签名不替代登录身份。"""
        if actor.user_id is None:
            return
        account=shared.UserAccount.__table__
        field=account.c.student_id if actor.actor_type=='student' else account.c.employee_id
        linked=self.db.scalar(select(field).where(account.c.user_id==actor.user_id,account.c.identity_type==actor.actor_type))
        if linked!=actor.actor_id:
            raise BusinessException('账号关联已变化，请重新登录',401)

    def student_record(self, student_id):
        row = (
            self.db.execute(
                select(shared.student_profile).where(
                    shared.student_profile.c.student_id == student_id
                )
            )
            .mappings()
            .first()
        )
        if (
            not row
            or row["is_archived"]
            or row["status"] in ("disabled", "inactive", "withdrawn", "suspended")
        ):
            raise BusinessException("学生身份不可用", 403)
        if self.db.scalar(select(shared.org_department.c.status).where(shared.org_department.c.department_id==row['department_id']))!='active':
            raise BusinessException('学生归属部门不可用',403)
        return row

    def employee(self, actor):
        if actor.actor_type != "employee":
            raise BusinessException("需要员工身份", 403)
        self.check_account_link(actor)
        row = (
            self.db.execute(
                select(shared.employee).where(
                    shared.employee.c.employee_id == actor.actor_id
                )
            )
            .mappings()
            .first()
        )
        if (
            not row
            or row["status"] != "active"
            or not isinstance(row["role_codes"],list)
            or "teacher" not in (row["role_codes"] or [])
        ):
            raise BusinessException("需要有效的老师权限", 403)
        if self.db.scalar(select(shared.org_department.c.status).where(shared.org_department.c.department_id==row['department_id']))!='active':
            raise BusinessException('员工部门不可用',403)
        return row

    def bound(self, employee_id, student_id, *, primary=False):
        t = shared.student_staff_binding
        now = utcnow()
        return (
            self.db.execute(
                select(t.c.binding_id).select_from(t.join(shared.employee,t.c.employee_id==shared.employee.c.employee_id).join(shared.student_profile,t.c.student_id==shared.student_profile.c.student_id)).where(
                    t.c.student_id == student_id,
                    t.c.employee_id == employee_id,
                    t.c.relation_type == "class_teacher",
                    or_(not primary,t.c.is_primary.is_(True)),
                    t.c.status == "active",
                    t.c.valid_from <= now,
                    or_(t.c.valid_to.is_(None), t.c.valid_to > now),
                    shared.employee.c.employee_id == employee_id,
                    shared.employee.c.status == 'active',
                    shared.employee.c.role_codes.cast(__import__('sqlalchemy').String).like('%"teacher"%'),
                    shared.student_profile.c.student_id == student_id,
                    shared.employee.c.department_id == shared.student_profile.c.department_id,
                )
            ).first()
            is not None
        )

    def responsible_teacher(self, student_id, relation="class_teacher"):
        t, e = shared.student_staff_binding, shared.employee
        now = utcnow()
        rows = self.db.execute(
            select(t.c.employee_id, e.c.role_codes)
            .join(e, t.c.employee_id == e.c.employee_id)
            .where(
                t.c.student_id == student_id,
                t.c.relation_type == relation,
                t.c.status == "active",
                e.c.status == "active",
                t.c.is_primary.is_(True),
                e.c.department_id == select(shared.student_profile.c.department_id).where(shared.student_profile.c.student_id==student_id).scalar_subquery(),
                t.c.valid_from <= now,
                or_(t.c.valid_to.is_(None), t.c.valid_to > now),
            )
            .order_by(t.c.is_primary.desc(), t.c.binding_id)
        ).mappings()
        for row in rows:
            if "teacher" in (row["role_codes"] or []):
                return row["employee_id"]
        return None

    def fallback_teacher(self):
        # 052：无负责人时进入专属接管列表，禁止配置一个全局老师跨范围接手。
        return None

    def _load(self, table, entity_id, actor=None, *, lock=True):
        if lock and 'student_id' in table.c:
            owner = self.db.scalar(select(table.c.student_id).where(row_id(table)==entity_id))
            if owner is not None:
                self.lock_business_prefix(owner)
        statement = select(table).where(row_id(table) == entity_id)
        if lock:
            statement = statement.with_for_update()
        row = self.db.execute(statement).mappings().first()
        if not row or (actor is not None and row["student_id"] != actor.actor_id):
            raise BusinessException("记录不存在", 404)
        return row

    def _version_update(self, table, row, expected, values):
        version_column = (
            table.c.version if "version" in table.c else table.c.row_version
        )
        if row[version_column.name] != expected:
            raise BusinessException("数据已更新，请刷新后重试", 409)
        values = {**values, version_column.name: expected + 1, "updated_at": utcnow()}
        extra=[]
        if table is shared.student_admin_service:
            extra=[table.c.apply_type==row['apply_type'],table.c.approval_status==row['approval_status'],table.c.reviewer_id==row['reviewer_id']]
        result = self.db.execute(
            update(table)
            .where(row_id(table) == row[row_id(table).name], version_column == expected, *extra)
            .values(**values)
        )
        if result.rowcount != 1:
            raise BusinessException("并发更新冲突，请刷新后重试", 409)
        return expected + 1

    def notify(
        self,
        entity_type,
        entity_id,
        event,
        title,
        *,
        student_id=None,
        employee_id=None,
        version=1
    ):
        if (student_id is None) == (employee_id is None):
            raise ValueError("通知必须且只能指定一种接收人")
        event = event if event.startswith(("student.","enterprise.")) else "student." + event
        key = notification_key(entity_type,entity_id,event,student_id,employee_id,version)
        t = shared.business_notification
        if self.db.execute(
            select(t.c.notification_id).where(t.c.dedupe_key == key)
        ).first():
            return
        self.db.execute(
            insert(t).values(
                entity_type=entity_type,
                entity_id=entity_id,
                event_code=event,
                student_id=student_id,
                employee_id=employee_id,
                channel="in_app",
                title=title,
                content="请进入对应业务查看详情。",
                dedupe_key=key,
                delivery_status="pending",
                attempt_count=0,
                row_version=1,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
        )

    def _write(self, actor, action, key, parameters, handler):
        """唯一操作键处理并发重试；失败时业务和通知一起回滚。"""
        required = {
            'leave.withdraw':'student.admin_service.withdraw_own','leave.decide':'student.admin_service.review',
            'leave.assign':'student.admin_service.assign','warning.assign':'student.warning.assign',
            'ticket.reply':'student.ticket.reply_own','ticket.confirm':'student.ticket.confirm_own','ticket.rate':'student.ticket.rate_own',
            'reminder.set':'student.reminder.manage_own','reminder.cancel':'student.reminder.manage_own',
            'mental.ack':'student.warning.handle','mental.follow':'student.warning.handle','mental.close':'student.warning.handle',
            'local.academic':'student.academic.maintain','local.progress':'student.progress.maintain',
        }.get(action)
        if required and required not in actor.scopes:
            raise BusinessException('缺少业务动作权限',403)
        op = shared.operation_log
        operation_key = digest(
            [actor.key, "action.confirm" if key.startswith("confirm:") else action, key]
        )
        parameter_hash = digest([action, parameters])

        def replay(row):
            if row["parameters_hash"] != parameter_hash:
                raise BusinessException("相同请求键不能用于不同内容", 409)
            if row["operation_status"] != "succeeded":
                raise BusinessException("请求正在处理或需要核实", 409)
            return row["result_reference"]

        try:
            if action in (
                "mental.ack",
                "mental.follow",
                "mental.close",
                "leave.decide",
                "employee.notification.read",
            ):
                self.employee(actor)
            elif actor.actor_type == "employee":
                from app.core.common.authorization import employee_permissions
                if not employee_permissions(self.db, actor.actor_id):
                    raise BusinessException("员工权限已失效",403)
            elif action in ("academic.sync", "progress.sync"):
                actor.require_scope("student:sync")
            else:
                self.student(actor)
            existing = (
                self.db.execute(select(op).where(op.c.operation_key == operation_key))
                .mappings()
                .first()
            )
            if existing:
                result = replay(existing)
                self.db.rollback()
                return result
            result = self.db.execute(
                insert(op).values(
                    operation_key=operation_key,
                    student_id=(
                        actor.actor_id if actor.actor_type == "student" else None
                    ),
                    employee_id=(
                        actor.actor_id if actor.actor_type == "employee" else None
                    ),
                    service_code=(
                        actor.service_code if actor.actor_type == "service" else None
                    ),
                    action_code=action,
                    entity_type=action.split(".")[0],
                    request_key=key,
                    parameters_hash=parameter_hash,
                    operation_status="processing",
                    row_version=1,
                    created_at=utcnow(),
                    updated_at=utcnow(),
                )
            )
            op_id = result.inserted_primary_key[0]
            receipt, entity_id, audit = handler(operation_key)
            self.db.execute(
                update(op)
                .where(op.c.operation_log_id == op_id)
                .values(
                    entity_id=entity_id,
                    after_data=audit,
                    result_reference=receipt,
                    operation_status="succeeded",
                    finished_at=utcnow(),
                    updated_at=utcnow(),
                )
            )
            if not getattr(self, "defer_commit", False):
                self.db.commit()
            return receipt
        except IntegrityError:
            self.db.rollback()
            existing = (
                self.db.execute(select(op).where(op.c.operation_key == operation_key))
                .mappings()
                .first()
            )
            if existing:
                try:
                    return replay(existing)
                finally:
                    self.db.rollback()
            raise BusinessException(
                "数据发生重复或关联冲突，请核对后重试", 409
            ) from None
        except Exception:
            self.db.rollback()
            raise

    def _account(self, actor):
        from types import SimpleNamespace
        return SimpleNamespace(identity_type=actor.actor_type, user_id=actor.user_id, student_id=actor.actor_id if actor.actor_type == 'student' else None)

    def submit_leave(self, actor, key, body):
        self.student(actor)
        if 'student.admin_service.create' not in actor.scopes:
            raise BusinessException('缺少请假提交权限',403)
        from app.services.student.student_leave_service import StudentLeaveService
        from app.schemas.student.student_leave import LeaveInput
        from app.services.student.student_common import StudentBusinessError
        try:
            from app.clients.student.student_assistant_dify import LeaveWorkflowAdapter
            return StudentLeaveService(self.db, LeaveWorkflowAdapter()).submit(self._account(actor), key, LeaveInput.model_validate(body.model_dump()))
        except StudentBusinessError as exc:
            raise BusinessException(exc.message, exc.status) from None

    def withdraw_leave(self, actor, key, entity_id, expected):
        def apply(_):
            t = shared.student_admin_service
            row = self._load(t, entity_id, actor)
            if row['approval_status'] != 'pending' or row['apply_type'] != 'leave':
                raise BusinessException('仅待审批请假可以撤回', 409)
            version = self._version_update(t, row, expected, {'approval_status':'cancelled'})
            if row['reviewer_id']:
                self.notify('student_admin_service',entity_id,'leave.cancelled','学生已撤回请假',employee_id=row['reviewer_id'],version=version)
            return {'apply_id':entity_id,'approval_status':'cancelled','row_version':version}, entity_id, {'status':'withdrawn'}
        return self._write(actor, 'leave.withdraw', key, [entity_id, expected], apply)

    def leave_for_teacher(self, actor, entity_id, *, lock=False):
        self.employee(actor)
        row = self._load(shared.student_admin_service, entity_id, lock=lock)
        self.student_record(row['student_id'])
        if row['apply_type'] != 'leave' or row['reviewer_id'] != actor.actor_id or not self.bound(actor.actor_id, row['student_id'],primary=True):
            raise BusinessException('记录不存在', 404)
        return row

    def decide_leave(self, actor, key, entity_id, body):
        from .student_leave_service import StudentLeaveService
        return StudentLeaveService(self.db,None).decide(actor,key,entity_id,body)

    def _decide_leave(self, actor, key, entity_id, body):
        self.leave_for_teacher(actor, entity_id)
        def apply(_):
            row = self.leave_for_teacher(actor, entity_id, lock=True)
            if row['approval_status'] != 'pending':
                raise BusinessException('仅待审批请假可以审批', 409)
            reviewed_at=utcnow()
            version = self._version_update(shared.student_admin_service, row, body.expected_version, {'approval_status':body.decision,'reviewed_at':reviewed_at,'approval_comment':body.comment})
            self.notify('student_admin_service', entity_id, 'leave.'+body.decision, '你的请假已有审批结果', student_id=row['student_id'], version=version)
            receipt = {'apply_id':entity_id,'approval_status':body.decision,'row_version':version,'reviewed_at':public_time(reviewed_at),'reviewer_id':actor.actor_id}
            return receipt, entity_id, {**receipt, 'comment':body.comment}
        return self._write(actor, 'leave.decide', key, [entity_id, body.model_dump()], apply)

    def teacher_binding_condition(self, actor, student_column, *, primary=True):
        b, now = shared.student_staff_binding, utcnow()
        return select(b.c.binding_id).select_from(b.join(shared.student_profile,b.c.student_id==shared.student_profile.c.student_id).join(shared.employee,b.c.employee_id==shared.employee.c.employee_id)).where(
            b.c.student_id==student_column,b.c.employee_id==actor.actor_id,b.c.relation_type=='class_teacher',
            or_(not primary,b.c.is_primary.is_(True)),b.c.status=='active',b.c.valid_from<=now,or_(b.c.valid_to.is_(None),b.c.valid_to>now),
            shared.employee.c.department_id==shared.student_profile.c.department_id).exists()

    def teacher_leaves(self, actor, status=None, limit=20, offset=0):
        from sqlalchemy import func
        self.employee(actor)
        t = shared.student_admin_service
        where = [t.c.apply_type=="leave",t.c.reviewer_id == actor.actor_id, self.teacher_binding_condition(actor,t.c.student_id)]
        if status:
            where.append(t.c.approval_status == status)
        rows = self.db.execute(select(t).where(*where).order_by(t.c.id.desc()).limit(limit).offset(offset)).mappings().all()
        return {'items':[leave_public(r) for r in rows], 'total':self.db.scalar(select(func.count()).select_from(t).where(*where)), 'limit':limit,'offset':offset}

    def teacher_warnings(self, actor, status=None, limit=20, offset=0):
        from sqlalchemy import func

        self.employee(actor)
        relationship = self.teacher_binding_condition(actor, warnings.c.student_id,primary=False)
        where = [
            relationship,
            or_(
                warnings.c.follower_id == actor.actor_id,
            ),
        ]
        if status:
            where.append(warnings.c.follower_status == status)
        total = self.db.scalar(select(func.count()).select_from(warnings).where(*where))
        rows = (
            self.db.execute(
                select(warnings)
                .where(*where)
                .order_by(warnings.c.created_at.desc(), warnings.c.id.desc())
                .limit(limit)
                .offset(offset)
            )
            .mappings()
            .all()
        )
        result = []
        for row in rows:
            item = dict(row)
            item["row_version"] = item.pop("version")
            item["warning_id"]=item.pop("id")
            result.append(public_row(item))
        return {"items": result, "total": total, "limit": limit, "offset": offset}

    def submit_ticket(self, actor, key, body, summary=None, *, allow_ai=True):
        self.student(actor)
        if 'service_ticket.create' not in actor.scopes:
            raise BusinessException('缺少工单提交权限',403)
        from app.services.student.student_ticket_service import StudentTicketService
        from app.schemas.student.student_ticket import ComplaintInput, TicketAnalysis
        from app.clients.student.student_ticket_dify import StudentTicketDifyError
        from app.services.student.student_common import StudentBusinessError
        class PreparedSummary:
            def summarize(self, student_id, payload):
                if summary is None:
                    raise StudentTicketDifyError('summary_unavailable')
                return TicketAnalysis(summary=summary.summary, suggested_category=summary.category,
                    workflow_run_id=summary.workflow_run_id, analysis_version=settings.STUDENT_ANALYSIS_VERSION)
        try:
            from app.clients.student.student_assistant_dify import TicketWorkflowAdapter
            workflow = TicketWorkflowAdapter() if summary is None and allow_ai else PreparedSummary()
            return StudentTicketService(self.db, workflow).submit(self._account(actor), key,
                ComplaintInput(content=body.content, ticket_type=body.ticket_type, category_code=body.category_code))
        except StudentBusinessError as exc:
            raise BusinessException(exc.message, exc.status) from None

    def _ticket_record(self, entity_id, actor, opkey, kind, content, status, cycle):
        self.db.execute(
            insert(shared.service_ticket_record).values(
                ticket_id=entity_id,
                student_id=actor.actor_id,
                record_type=kind,
                content=content,
                visibility="student_visible",
                to_status=status,
                cycle_no=cycle,
                record_key=opkey,
                created_at=utcnow(),
            )
        )

    def ticket_reply(self, actor, key, entity_id, body):
        def apply(opkey):
            t = shared.service_ticket
            row = self._load(t, entity_id, actor)
            if row["status"] == "closed":
                raise BusinessException("工单已关闭", 409)
            version = self._version_update(t, row, body.expected_version, {})
            self._ticket_record(
                entity_id,
                actor,
                opkey,
                "student_reply",
                body.content,
                row["status"],
                row["reopen_count"] + 1,
            )
            if row['employee_id']:
                self.notify('service_ticket',entity_id,'enterprise.ticket.student_reply','学生补充了反馈内容',employee_id=row['employee_id'],version=version)
            return (
                {"ticket_id": entity_id, "row_version": version},
                entity_id,
                {"row_version": version},
            )

        return self._write(
            actor, "ticket.reply", key, [entity_id, body.model_dump()], apply
        )

    def confirm_ticket(self, actor, key, entity_id, body):
        def apply(opkey):
            t = shared.service_ticket
            row = self._load(t, entity_id, actor)
            if row["status"] != "awaiting_student":
                raise BusinessException("工单尚未进入学生确认阶段", 409)
            now = utcnow()
            status = "closed" if body.resolved else "reopened"
            values = {"status": status, "closed_at": now if body.resolved else None}
            if not body.resolved:
                from .student_policy import ticket_cycle
                cycle=ticket_cycle(row['ticket_type'],row['priority'],now,row['reopen_count']+2)
                values.update(
                    reopen_count=row["reopen_count"] + 1,
                                        resolved_at=None,
                    solution=None,
                    satisfaction_score=None,
                    resolution_due_at=datetime.fromisoformat(cycle["resolution_due_at"].rstrip("Z")),
                )
            version = self._version_update(t, row, body.expected_version, values)
            if not body.resolved:
                self.db.execute(update(shared.operation_log).where(shared.operation_log.c.operation_key==opkey).values(before_data={'cycle_policy':cycle}))
            self._ticket_record(
                entity_id,
                actor,
                opkey,
                "confirm" if body.resolved else "reopen",
                body.comment,
                status,
                row["reopen_count"] + (1 if body.resolved else 2),
            )
            if row["employee_id"]:
                self.notify(
                    "service_ticket",
                    entity_id,
                    "ticket." + status,
                    "学生已反馈处理结果",
                    employee_id=row["employee_id"],
                    version=version,
                )
            return (
                {
                    "ticket_id": entity_id,
                    "process_status": status,
                    "row_version": version,
                },
                entity_id,
                {"status": status},
            )

        return self._write(
            actor, "ticket.confirm", key, [entity_id, body.model_dump()], apply
        )

    def rate_ticket(self, actor, key, entity_id, body):
        def apply(opkey):
            t = shared.service_ticket
            row = self._load(t, entity_id, actor)
            if row["status"] != "closed":
                raise BusinessException("请先确认工单已解决，再评价", 409)
            version = self._version_update(
                t,
                row,
                body.expected_version,
                {"satisfaction_score": body.satisfaction_score},
            )
            self._ticket_record(
                entity_id,
                actor,
                opkey,
                "rating",
                str(body.satisfaction_score),
                "closed",
                row["reopen_count"] + 1,
            )
            return (
                {"ticket_id": entity_id, "row_version": version},
                entity_id,
                {"satisfaction_score": body.satisfaction_score},
            )

        return self._write(
            actor, "ticket.rate", key, [entity_id, body.model_dump()], apply
        )

    def record_mental(self, actor, key, text, assessment):
        def apply(_):
            now = utcnow()
            result = self.db.execute(
                insert(profiles).values(
                    student_id=actor.actor_id,
                    emotion_tag=assessment.emotion_tag,
                    emotion_score=assessment.emotion_score,
                    risk_level=assessment.risk_level,
                    observed_at=now,
                    source_event_id=digest([actor.key, key]),
                    analysis_version=settings.STUDENT_ANALYSIS_VERSION,
                    workflow_run_id=assessment.workflow_run_id,
                    created_at=now,
                )
            )
            profile_id = result.inserted_primary_key[0]
            if assessment.risk_level in ("high", "critical"):
                teacher = (
                    self.responsible_teacher(actor.actor_id) or None
                )
                result = self.db.execute(
                    insert(warnings).values(
                        student_id=actor.actor_id,
                        profile_id=profile_id,
                        trigger_reason=assessment.trigger_reason,
                        risk_level=assessment.risk_level,
                        follower_status="pending",
                        follower_id=teacher,
                        version=1,
                        created_at=now,
                        updated_at=now,
                    )
                )
                warning_id = result.inserted_primary_key[0]
                if teacher:
                    self.notify(
                        "mental_warning",
                        warning_id,
                        "warning.created",
                        "有学生关怀事项需要及时处理",
                        employee_id=teacher,
                    )
            # 学生回执不包含预警原因、老师笔记或内部处理ID。
            receipt = {
                "assessment_saved": True,
                "support_required": assessment.risk_level in ("high", "critical"),
            }
            return receipt, profile_id, {"assessment_id": profile_id}

        return self._write(
            actor, "mental.record", key, {"text_hash": digest(text)}, apply
        )

    def handle_warning(self, actor, key, entity_id, kind, body):
        self.employee(actor)
        authorized = self._load(warnings, entity_id)
        if (
            not self.bound(actor.actor_id, authorized["student_id"])
        ) or authorized["follower_id"] != actor.actor_id:
            raise BusinessException("记录不存在", 404)

        def apply(_):
            row = self._load(warnings, entity_id)
            if (
                not self.bound(actor.actor_id, row["student_id"])
                or row["follower_id"] != actor.actor_id
            ):
                raise BusinessException("无权处理该预警", 403)
            if kind == "ack" and row["follower_status"] != "pending":
                raise BusinessException("预警已被接手或关闭", 409)
            if kind in ("follow", "close") and row["follower_status"] != "processing":
                raise BusinessException("请先接手待处理预警", 409)
            values = {"follower_id": actor.actor_id}
            if kind == "ack":
                values.update(follower_status="processing", acknowledged_at=utcnow())
            elif kind == "close":
                values.update(
                    follower_status="closed",
                    closed_at=utcnow(),
                    handling_result=body.note,
                )
            version = self._version_update(warnings, row, body.expected_version, values)
            # 专属处置备注仅进入受限操作记录，不写应用日志和学生响应。
            self.db.execute(
                update(shared.operation_log)
                .where(
                    shared.operation_log.c.operation_key
                    == digest([actor.key, "mental." + kind, key])
                )
                .values(change_reason=body.note)
            )
            return (
                {"warning_id": entity_id, "row_version": version},
                entity_id,
                {"status": values.get("follower_status", "processing")},
            )

        return self._write(
            actor, "mental." + kind, key, [entity_id, body.model_dump()], apply
        )

    def set_reminder(self, actor, key, body):
        def apply(_):
            event = self._load(events, body.academic_event_id, actor)
            if event['event_version'] != body.expected_event_version:
                raise BusinessException('学业节点已更新，请刷新后重试',409)
            notify_at = event["due_at"] - timedelta(minutes=body.lead_minutes)
            if event["event_status"] != "active" or notify_at <= utcnow():
                raise BusinessException("节点已取消或提醒时间已过", 409)
            row = (
                self.db.execute(
                    select(reminders)
                    .where(
                        reminders.c.student_id == actor.actor_id,
                        reminders.c.academic_event_id == body.academic_event_id,
                        reminders.c.lead_minutes == body.lead_minutes,
                    )
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if row and (body.expected_updated_at is None or as_utc(body.expected_updated_at) != row['updated_at']):
                raise BusinessException('提醒设置代次已更新，请刷新后重试',409)
            if not row and body.expected_updated_at is not None:
                raise BusinessException('提醒设置不存在',409)
            values = dict(
                student_id=actor.actor_id,
                academic_event_id=body.academic_event_id,
                lead_minutes=body.lead_minutes,
                notify_at=notify_at,
                event_version=event["event_version"],
                status="pending",
                sent_at=None,
                updated_at=next_setting_time(row),
            )
            if row:
                if (
                    row["status"] != "cancelled"
                    and row["event_version"] == event["event_version"]
                ):
                    return (
                        {"reminder_id": row["id"], "status": row["status"], "event_version":row["event_version"], "updated_at":public_time(row["updated_at"])},
                        row["id"],
                        {"status": row["status"]},
                    )
                self.db.execute(
                    update(reminders)
                    .where(reminders.c.id == row["id"])
                    .values(**values)
                )
                entity_id = row["id"]
            else:
                result = self.db.execute(
                    insert(reminders).values(**values, created_at=utcnow())
                )
                entity_id = result.inserted_primary_key[0]
            return (
                {"reminder_id": entity_id, "status": "pending", "event_version":event["event_version"], "updated_at":public_time(values["updated_at"])},
                entity_id,
                {"status": "pending"},
            )

        return self._write(actor, "reminder.set", key, body.model_dump(), apply)

    def cancel_reminder(self, actor, key, entity_id, body):
        def apply(_):
            snapshot = self._load(reminders, entity_id, actor, lock=False)
            self._load(events, snapshot['academic_event_id'], actor)
            row = self._load(reminders, entity_id, actor)
            if row['event_version'] != body.expected_event_version or row['updated_at'] != as_utc(body.expected_updated_at):
                raise BusinessException('提醒设置代次已更新，请刷新后重试',409)
            self.db.execute(
                update(reminders)
                .where(reminders.c.id == entity_id)
                .values(status="cancelled", updated_at=next_setting_time(row))
            )
            n = shared.business_notification
            self.db.execute(
                update(n)
                .where(
                    n.c.entity_type == "academic_reminder",
                    n.c.entity_id == entity_id,
                    n.c.delivery_status.in_(["pending", "failed", "sending"]),
                )
                .values(
                    delivery_status="dead_letter",
                    last_error_code="REMINDER_CANCELLED",
                    row_version=n.c.row_version + 1,
                )
            )
            return (
                {"reminder_id": entity_id, "status": "cancelled"},
                entity_id,
                {"status": "cancelled"},
            )

        return self._write(actor, "reminder.cancel", key, [entity_id, body.model_dump(mode="json")], apply)

    def teacher_notifications(self, actor, limit=20, offset=0):
        from sqlalchemy import func

        self.employee(actor)
        n = shared.business_notification
        where = [
            n.c.employee_id == actor.actor_id,
            n.c.event_code.like("student.%"),
            n.c.channel == "in_app",
            n.c.delivery_status == "sent",
        ]
        columns = [
            n.c[name]
            for name in (
                "notification_id",
                "entity_type",
                "entity_id",
                "event_code",
                "title",
                "content",
                "sent_at",
                "read_at",
            )
        ]
        rows = self.db.execute(
            select(*columns)
            .where(*where)
            .order_by(n.c.notification_id.desc())
            .limit(limit)
            .offset(offset)
        ).mappings()
        return {
            "items": [public_row(row) for row in rows],
            "total": self.db.scalar(select(func.count()).select_from(n).where(*where)),
            "limit": limit,
            "offset": offset,
        }

    def read_teacher_notification(self, actor, key, entity_id):
        self.employee(actor)

        def apply(_):
            n = shared.business_notification
            row = self._load(n, entity_id)
            if (
                row["employee_id"] != actor.actor_id
                or not row["event_code"].startswith("student.")
                or row["channel"] != "in_app"
            ):
                raise BusinessException("记录不存在", 404)
            from .student_notifications import visible
            if not visible(self.db,row,actor):
                raise BusinessException('通知不存在',404)
            if row["read_at"] is None:
                self.db.execute(
                    update(n)
                    .where(n.c.notification_id == entity_id)
                    .values(read_at=utcnow(), row_version=n.c.row_version + 1)
                )
            return (
                {"notification_id": entity_id, "read": True},
                entity_id,
                {"read": True},
            )

        return self._write(actor, "employee.notification.read", key, [entity_id], apply)

    def read_notification(self, actor, key, entity_id):
        def apply(_):
            n = shared.business_notification
            row = self._load(n, entity_id, actor)
            if row["delivery_status"] != "sent":
                raise BusinessException("通知尚未送达", 409)
            if row["read_at"] is None:
                self.db.execute(
                    update(n)
                    .where(n.c.notification_id == entity_id)
                    .values(
                        read_at=utcnow(),
                        updated_at=utcnow(),
                        row_version=n.c.row_version + 1,
                    )
                )
            return (
                {"notification_id": entity_id, "read": True},
                entity_id,
                {"read": True},
            )

        return self._write(actor, "notification.read", key, [entity_id], apply)

    def warning_history(self,actor,warning_id):
        self.employee(actor)
        row=self._load(warnings,warning_id,lock=False)
        if row["follower_id"]!=actor.actor_id or not self.bound(actor.actor_id,row["student_id"]):
            raise BusinessException("记录不存在",404)
        op=shared.operation_log
        entries=self.db.execute(select(op.c.operation_log_id,op.c.employee_id,op.c.action_code,op.c.change_reason,op.c.created_at).where(op.c.entity_id==warning_id,op.c.action_code.in_(["mental.ack","mental.follow","mental.close","warning.assign"]),op.c.operation_status=="succeeded").order_by(op.c.operation_log_id)).mappings()
        return [public_row(entry) for entry in entries]
