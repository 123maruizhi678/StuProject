"""请假与心理预警的受控接管；企业页面复用此服务，不复制审批逻辑。"""
from sqlalchemy import select, update, or_, func
from app.config import settings
from app.core.common.response import BusinessException
from app.models import common as t
from .student_service import StudentService, warnings, public_row, utcnow


class StudentAssignments(StudentService):
    def assignment_scope(self, actor, kind):
        permission = 'student.admin_service.assign' if kind == 'leave' else 'student.warning.assign'
        if permission not in actor.scopes or actor.actor_type != 'employee':
            raise BusinessException('缺少专属分派权限', 403)
        employee = self.db.execute(select(t.employee).where(t.employee.c.employee_id == actor.actor_id)).mappings().first()
        if not employee or employee['status'] != 'active':
            raise BusinessException('员工身份无效', 403)
        if kind == 'leave':
            departments=set(settings.STUDENT_LEAVE_ASSIGNMENT_SCOPES.get(actor.actor_id,[]))
            if 'manager' in (employee['role_codes'] or []):
                departments.add(employee['department_id'])
            return [t.student_profile.c.department_id.in_(departments)]
        allowed = settings.STUDENT_WARNING_ASSIGNMENT_SCOPES.get(actor.actor_id, [])
        return [t.student_profile.c.student_id.in_(allowed)]

    def valid_owner_condition(self, table, owner_column):
        b, e, s = t.student_staff_binding, t.employee, t.student_profile
        now = utcnow()
        return select(b.c.binding_id).select_from(b.join(e,b.c.employee_id==e.c.employee_id).join(s,s.c.student_id==b.c.student_id)).where(
            b.c.student_id==table.c.student_id,b.c.employee_id==owner_column,
            b.c.relation_type=='class_teacher',or_(table is not t.student_admin_service,b.c.is_primary.is_(True)),
            b.c.status=='active',b.c.valid_from<=now,or_(b.c.valid_to.is_(None),b.c.valid_to>now),
            e.c.status=='active',e.c.department_id==s.c.department_id,
            e.c.role_codes.cast(__import__('sqlalchemy').String).like('%"teacher"%'),
        ).exists()

    def list_assignments(self, actor, kind, limit=20, offset=0):
        table = t.student_admin_service if kind == 'leave' else warnings
        owner = table.c.reviewer_id if kind == 'leave' else table.c.follower_id
        version = table.c.row_version if kind == 'leave' else table.c.version
        where = self.assignment_scope(actor,kind)
        where += [table.c.approval_status=='pending', table.c.apply_type=='leave'] if kind=='leave' else [table.c.follower_status!='closed']
        where += [~self.valid_owner_condition(table,owner)]
        source = table.join(t.student_profile,table.c.student_id==t.student_profile.c.student_id)
        # JSON teacher 角色不能跨方言直接比较；最终分派还会核验目标完整角色。
        rows = self.db.execute(select(table.c.id,table.c.student_id,owner,version.label('row_version')).select_from(source).where(*where).order_by(table.c.id).limit(limit).offset(offset)).mappings().all()
        return {'items':[dict(row) for row in rows],'total':self.db.scalar(select(func.count()).select_from(source).where(*where)),'limit':limit,'offset':offset}

    def assign(self, actor, key, kind, entity_id, body):
        table = t.student_admin_service if kind=='leave' else warnings
        owner_name = 'reviewer_id' if kind=='leave' else 'follower_id'
        scope = self.assignment_scope(actor,kind)
        source = table.join(t.student_profile,table.c.student_id==t.student_profile.c.student_id)
        visible = self.db.execute(select(table.c.id).select_from(source).where(table.c.id==entity_id,*scope)).first()
        if not visible:
            raise BusinessException('记录不存在',404)

        def apply(_):
            # 同事务锁定主档、目标员工、有效关系及业务对象。
            snapshot = self._load(table,entity_id,lock=False)
            self.lock_business_prefix(snapshot['student_id'],[actor.actor_id,body.employee_id])
            if not self.db.execute(select(table.c.id).select_from(source).where(table.c.id==entity_id,*self.assignment_scope(actor,kind))).first():
                raise BusinessException('记录不存在',404)
            target = self.db.execute(select(t.employee).where(t.employee.c.employee_id==body.employee_id).with_for_update()).mappings().first()
            student = self.student_record(snapshot['student_id'])
            if not target or target['status']!='active' or 'teacher' not in (target['role_codes'] or []) or target['department_id']!=student['department_id']:
                raise BusinessException('目标老师无有效同部门权限',403)
            if kind!='leave':
                from app.core.student.student_permissions import employee_permissions
                if 'student.warning.handle' not in employee_permissions(self.db,body.employee_id):
                    raise BusinessException('目标人员缺少心理处置专属权限',403)
            binding = self.db.execute(select(t.student_staff_binding).where(t.student_staff_binding.c.student_id==student['student_id'],t.student_staff_binding.c.employee_id==body.employee_id,t.student_staff_binding.c.relation_type=='class_teacher',or_(kind!='leave',t.student_staff_binding.c.is_primary.is_(True)),t.student_staff_binding.c.status=='active',t.student_staff_binding.c.valid_from<=utcnow(),or_(t.student_staff_binding.c.valid_to.is_(None),t.student_staff_binding.c.valid_to>utcnow())).with_for_update()).first()
            if not binding:
                raise BusinessException('目标人员不是当前有效主班主任',403)
            row = self._load(table,entity_id)
            eligible = row['approval_status']=='pending' and row['apply_type']=='leave' if kind=='leave' else row['follower_status']!='closed'
            if not eligible:
                raise BusinessException('当前状态不允许分派',409)
            if self.db.scalar(select(self.valid_owner_condition(table,table.c[owner_name])).where(table.c.id==entity_id)):
                raise BusinessException('当前负责人仍有效，不在失效接管范围',409)
            values = {owner_name:body.employee_id}
            if kind!='leave':
                values.update(follower_status='pending',acknowledged_at=None)
            version = self._version_update(table,row,body.expected_version,values)
            result = {'id':entity_id,owner_name:body.employee_id,'row_version':version}
            op = t.operation_log
            self.db.execute(op.update().where(op.c.operation_key==_).values(before_data={owner_name:row[owner_name]},change_reason=body.reason))
            self.db.execute(update(t.operation_log).where(t.operation_log.c.action_code=='takeover.discover',t.operation_log.c.entity_type==table.name,t.operation_log.c.entity_id==entity_id,t.operation_log.c.finished_at.is_(None)).values(finished_at=utcnow(),updated_at=utcnow()))
            self.notify(table.name,entity_id,kind+'.assigned','有业务需要处理',employee_id=body.employee_id,version=version)
            if row[owner_name] is not None and row[owner_name]!=body.employee_id:
                self.notify(table.name,entity_id,kind+'.transferred','业务负责人已调整',employee_id=row[owner_name],version=version)
            return result,entity_id,{**result,'reason':body.reason}
        return self._write(actor,kind+'.assign',key,[entity_id,body.model_dump()],apply)
