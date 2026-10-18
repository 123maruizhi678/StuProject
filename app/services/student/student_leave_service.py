"""学生请假业务：可信身份、Dify分析、分派与原子写入。"""
from datetime import datetime, timezone
from sqlalchemy import select, or_
from app.models import common as shared
from app.models.student.student_types import utcnow
from app.core.common.response import BusinessException

from sqlalchemy.exc import IntegrityError

from app.repositories.student.student_leave_repository import StudentLeaveRepository
from app.repositories.student.student_schema import require_student_schema
from app.clients.student.student_leave_dify import StudentLeaveDifyError


from app.services.student.student_common import (StudentBusinessService, StudentBusinessError as LeaveError, digest, utc_naive)


class StudentLeaveService(StudentBusinessService):
    def __init__(self, db, workflow):
        self.repository = StudentLeaveRepository(db)
        self.workflow = workflow

    def submit(self, account, request_key, payload):
        start, end = utc_naive(payload.leave_start_at), utc_naive(payload.leave_end_at)
        parameters_hash = digest({
            "leave_content": payload.leave_content, "leave_type": payload.leave_type,
            "leave_start_at": start.isoformat(), "leave_end_at": end.isoformat(),
        })
        if payload.generate_ai_summary:
            parameters_hash = digest([parameters_hash, "generate_ai_summary"])
        operation_key = digest(["student", account.student_id, "student.leave.submit", request_key])
        repository = self.repository
        try:
            require_student_schema(repository.db, "leave")
            student_id = self._student(account)
            receipt = self._replay(operation_key, parameters_hash)
            repository.rollback()  # 结束预检读事务；不持有数据库锁等待大模型。
            if receipt is not None:
                return receipt
            analysis, ai_status = None, "not_requested"
            if payload.generate_ai_summary:
                try:
                    analysis = self.workflow.analyze_leave(student_id, payload)
                    ai_status = "available"
                except StudentLeaveDifyError:
                    ai_status = "unavailable"  # AI 增强失败，仍保留原始请假申请。

            # 外部调用之后重新校验档案与幂等，防止期间账号变化或并发重试。
            if self._student(account, lock=True) != student_id:
                raise LeaveError(403, "账号关联发生变化，请重新提交")
            receipt = self._replay(operation_key, parameters_hash)
            if receipt is not None:
                repository.rollback()
                return receipt
            now = utc_naive(datetime.now(timezone.utc))
            reviewer_id = repository.find_teacher(student_id, now)
            repository.create_operation(dict(
                operation_key=operation_key, student_id=student_id,
                action_code="student.leave.submit", entity_type="student_admin_service",
                request_key=request_key, parameters_hash=parameters_hash,
                operation_status="processing", row_version=1, created_at=now, updated_at=now,
            ))
            apply_id = repository.create_application(dict(
                student_id=student_id, apply_type="leave", apply_content=payload.leave_content,
                approval_status="pending",
                edu_related_data={"leave_type": payload.leave_type, "ai_status": ai_status,
                                  "ai_analysis": analysis.model_dump() if analysis else None},
                leave_start_at=start, leave_end_at=end, reviewer_id=reviewer_id,
                request_key=request_key, request_hash=parameters_hash, row_version=1,
                created_at=now, updated_at=now,
            ))
            if reviewer_id is not None:
                from .student_service import StudentService
                StudentService(repository.db).notify('student_admin_service',apply_id,'leave.submitted','有新的学生请假待审批',employee_id=reviewer_id,version=1)
            receipt = dict(
                apply_id=apply_id, approval_status="pending", reviewer_id=reviewer_id,
                row_version=1, assignment_pending=reviewer_id is None,
                notification_queued=reviewer_id is not None, ai_status=ai_status,
                ai_analysis=analysis.model_dump() if analysis else None,
            )
            repository.complete_operation(operation_key, dict(
                entity_id=apply_id, operation_status="succeeded", result_reference=receipt,
                after_data={"approval_status": "pending", "reviewer_id": reviewer_id,
                            "ai_status": ai_status,
                            "workflow_run_id": analysis.workflow_run_id if analysis else None},
                updated_at=now, finished_at=now,
            ))
            repository.commit()
            return receipt
        except IntegrityError:
            repository.rollback()
            try:
                if self._student(account) != student_id:
                    raise LeaveError(403, "账号关联发生变化，请重新提交")
                receipt = self._replay(operation_key, parameters_hash)
                if receipt is not None:
                    return receipt
                raise LeaveError(409, "请假记录发生关联或重复冲突，请核对后重试") from None
            finally:
                repository.rollback()
        except Exception:
            repository.rollback()
            raise


    def withdraw(self, actor, key, entity_id, expected):
        from .student_service import StudentService
        service = StudentService(self.repository.db)
        def apply(_):
            t = shared.student_admin_service
            row = service._load(t, entity_id, actor)
            if row['approval_status'] != 'pending' or row['apply_type'] != 'leave':
                raise BusinessException('仅待审批请假可以撤回', 409)
            version = service._version_update(t, row, expected, {'approval_status':'cancelled'})
            if row['reviewer_id']:
                service.notify('student_admin_service',entity_id,'leave.cancelled','学生已撤回请假',employee_id=row['reviewer_id'],version=version)
            return {'apply_id':entity_id,'approval_status':'cancelled','row_version':version}, entity_id, {'status':'withdrawn'}
        return service._write(actor, 'leave.withdraw', key, [entity_id, expected], apply)

    def decide(self, actor, key, entity_id, body):
        from .student_service import StudentService
        service = StudentService(self.repository.db)
        from .student_service import public_time
        self.for_teacher(actor, entity_id)
        def apply(_):
            row = self.for_teacher(actor, entity_id, lock=True)
            if row['approval_status'] != 'pending':
                raise BusinessException('仅待审批请假可以审批', 409)
            reviewed_at=utcnow()
            version = service._version_update(shared.student_admin_service, row, body.expected_version, {'approval_status':body.decision,'reviewed_at':reviewed_at,'approval_comment':body.comment})
            service.notify('student_admin_service', entity_id, 'leave.'+body.decision, '你的请假已有审批结果', student_id=row['student_id'], version=version)
            receipt = {'apply_id':entity_id,'approval_status':body.decision,'row_version':version,'reviewed_at':public_time(reviewed_at),'reviewer_id':actor.actor_id}
            return receipt, entity_id, {**receipt, 'comment':body.comment}
        return service._write(actor, 'leave.decide', key, [entity_id, body.model_dump()], apply)

    def for_teacher(self, actor, entity_id, *, lock=False):
        from .student_service import StudentService
        service = StudentService(self.repository.db)
        service.employee(actor)
        row = service._load(shared.student_admin_service, entity_id, lock=lock)
        service.student_record(row['student_id'])
        if row['apply_type'] != 'leave' or row['reviewer_id'] != actor.actor_id or not service.bound(actor.actor_id, row['student_id'],primary=True):
            raise BusinessException('记录不存在', 404)
        return row

    def binding_condition(self, actor, student_column, *, primary=True):
        from .student_service import StudentService
        service = StudentService(self.repository.db)
        b, now = shared.student_staff_binding, utcnow()
        return select(b.c.binding_id).select_from(b.join(shared.student_profile,b.c.student_id==shared.student_profile.c.student_id).join(shared.employee,b.c.employee_id==shared.employee.c.employee_id)).where(
            b.c.student_id==student_column,b.c.employee_id==actor.actor_id,b.c.relation_type=='class_teacher',
            or_(not primary,b.c.is_primary.is_(True)),b.c.status=='active',b.c.valid_from<=now,or_(b.c.valid_to.is_(None),b.c.valid_to>now),
            shared.employee.c.department_id==shared.student_profile.c.department_id).exists()

    def list_for_teacher(self, actor, status=None, limit=20, offset=0):
        from .student_service import StudentService
        service = StudentService(self.repository.db)
        from sqlalchemy import func
        service.employee(actor)
        t = shared.student_admin_service
        where = [t.c.apply_type=="leave",t.c.reviewer_id == actor.actor_id, self.binding_condition(actor,t.c.student_id)]
        if status:
            where.append(t.c.approval_status == status)
        rows = service.db.execute(select(t).where(*where).order_by(t.c.id.desc()).limit(limit).offset(offset)).mappings().all()
        from .student_service import leave_public
        return {'items':[leave_public(r) for r in rows], 'total':service.db.scalar(select(func.count()).select_from(t).where(*where)), 'limit':limit,'offset':offset}
