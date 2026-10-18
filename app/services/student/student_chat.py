"""一个学生助手：会话、七类意图、可信查询及确认后办理。"""
from sqlalchemy import select,insert,update
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError
from app.core.common.response import BusinessException
from app.core.student.student_auth import sign_token,verify_token
from app.config import settings
from app.schemas.student.student import LeaveInput,TicketInput,ReminderInput,TicketSummary
from app.models.student.student_conversation import sessions,turns
from app.models.student.student_types import utcnow
from app.services.student.student_service import digest
from app.services.student.student_knowledge import retrieve
WRITE_ACTIONS={'leave.submit':LeaveInput,'ticket.submit':TicketInput,'reminder.set':ReminderInput}
READ_ACTIONS={'leave.query':'leave','ticket.query':'tickets','academic.query':'academic',
    'progress.query':'progress','reminders.query':'reminders','notifications.query':'notifications',
    'courses.query':'courses','scores.query':'scores'}
ACTION_PERMISSIONS={'leave.submit':'student.admin_service.create','ticket.submit':'service_ticket.create',
    'reminder.set':'student.reminder.manage_own','leave.query':'student.admin_service.read_own',
    'ticket.query':'service_ticket.read_own','academic.query':'student.academic.read_own',
    'progress.query':'student.progress.read_own','reminders.query':'student.reminder.manage_own',
    'notifications.query':'student.notification.read_own',
    'courses.query':'student.course.read_own','scores.query':'student.score.read_own'}
ALLOWED={'leave':{'none','leave.submit','leave.query'},'mental':{'none'},
    'feedback':{'none','ticket.submit','ticket.query'},'academic':{'none','academic.query','reminder.set','reminders.query','courses.query','scores.query'},
    'progress':{'none','progress.query'},'life':{'none'},'upgrade':{'none'}}

class StudentChatService:
    def __init__(self,service,dify,query):
        self.service,self.dify,self.query=service,dify,query
        self.db=service.db
    def history_list(self, actor, limit=20, offset=0):
        from sqlalchemy import func
        from app.services.student.student_service import public_row
        self.service.student(actor)
        where = sessions.c.student_id == actor.actor_id
        rows = self.db.execute(select(sessions).where(where).order_by(sessions.c.updated_at.desc(), sessions.c.session_id).limit(limit).offset(offset)).mappings().all()
        items = []
        for row in rows:
            first = self.db.scalar(select(turns.c.message).where(turns.c.session_id == row['session_id'], turns.c.student_id == actor.actor_id).order_by(turns.c.id).limit(1))
            items.append({**public_row(row), 'title': (first or '新会话')[:60]})
        return {'items': items, 'total': self.db.scalar(select(func.count()).select_from(sessions).where(where)), 'limit': limit, 'offset': offset}

    def history_detail(self, actor, session_id, limit=20, offset=0):
        from sqlalchemy import func
        from app.services.student.student_service import public_row
        self.service.student(actor)
        row = self.db.execute(select(sessions).where(sessions.c.session_id == session_id, sessions.c.student_id == actor.actor_id)).mappings().first()
        if not row:
            raise BusinessException('会话不存在', 404)
        where = (turns.c.session_id == session_id, turns.c.student_id == actor.actor_id)
        pending = bool(self.db.scalar(select(turns.c.id).where(*where, turns.c.result.is_(None)).limit(1)))
        # 倒序分页，页内按对话顺序返回；历史预览不重新签发办理凭证。
        rows = self.db.execute(select(turns).where(*where).order_by(turns.c.id.desc()).limit(limit).offset(offset)).mappings().all()
        items = []
        for turn in reversed(rows):
            result = turn['result']
            items.append(public_row({'id': turn['id'], 'message': turn['message'], 'created_at': turn['created_at'],
                'answer': result.get('answer') if result else None, 'pending': result is None,
                'data': result.get('data') if result else None, 'sources': result.get('sources', []) if result else [],
                'had_action': bool(result and result.get('pending_action'))}))
        token = None if pending else sign_token({'subject': actor.key, 'session_id': session_id, 'version': row['version']}, 'student-conversation', 86400)
        return {'session_id': session_id, 'items': items, 'total': self.db.scalar(select(func.count()).select_from(turns).where(*where)),
                'limit': limit, 'offset': offset, 'blocked': pending, 'conversation_token': token}

    def _permission(self,actor,action):
        required=ACTION_PERMISSIONS.get(action)
        if required and required not in actor.scopes:
            raise BusinessException('当前账号没有办理此业务的权限',403)

    def monitor(self,actor,key,body):
        """直接评估也先持久化占位；超时后仅核实，不自动重复请求模型。"""
        from app.models import common as shared
        self.service.student(actor)
        op=shared.operation_log
        opkey=digest([actor.key,'mental.model',key])
        signature=digest(body.model_dump(mode='json'))
        row=self.db.execute(select(op).where(op.c.operation_key==opkey)).mappings().first()
        if row:
            if row['parameters_hash']!=signature:
                raise BusinessException('同一请求键不能更换评估内容',409)
            if row['operation_status']=='succeeded':
                return row['result_reference']
            raise BusinessException('评估执行中或结果待核实，不会自动重复调用',409)
        self.db.rollback()
        try:
            self.db.execute(insert(op).values(operation_key=opkey,student_id=actor.actor_id,action_code='mental.model',entity_type='mental',request_key=key,parameters_hash=signature,operation_status='pending_external',row_version=1,created_at=utcnow(),updated_at=utcnow()))
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise BusinessException('评估已被另一请求受理',409) from None
        assessment=self.dify.mental(body.chat_content,actor)
        try:
            self.service.defer_commit=True
            self.service.student(actor)
            result=self.service.record_mental(actor,'monitor:'+digest(key),body.chat_content,assessment)
            self.db.execute(update(op).where(op.c.operation_key==opkey,op.c.operation_status=='pending_external').values(operation_status='succeeded',result_reference=result,finished_at=utcnow(),updated_at=utcnow()))
            self.db.commit()
            return result
        except Exception:
            self.db.rollback()
            raise
        finally:
            self.service.defer_commit=False
    def _replay(self,actor,key,parameters_hash):
        row=self.db.execute(select(turns).where(turns.c.student_id==actor.actor_id,turns.c.request_key==digest(key))).mappings().first()
        if row and row['parameters_hash']!=parameters_hash:
            raise BusinessException('同一请求键不能用于不同消息',409)
        if row and row['result'] is None:
            raise BusinessException('请求已受理，模型执行中或结果待核实；不会自动重复调用',409)
        return row['result'] if row else None
    def chat(self,actor,key,body):
        self.service.student(actor)
        signature=digest(body.model_dump(mode='json'))
        replay=self._replay(actor,key,signature)
        if replay is not None:
            self.db.rollback()
            return replay
        sid=digest([actor.key,key])[:48]
        version=0
        if body.conversation_token:
            claims=verify_token(body.conversation_token,'student-conversation')
            if claims.get('subject')!=actor.key:
                raise BusinessException('会话不属于当前学生',403)
            sid=claims.get('session_id')
            version=claims.get('version')
            if not isinstance(sid,str) or type(version) is not int:
                raise BusinessException('会话凭证无效',400)
            session=self.db.execute(select(sessions).where(sessions.c.session_id==sid,sessions.c.student_id==actor.actor_id)).mappings().first()
            if not session:
                raise BusinessException('会话不存在',404)
            if session['version']!=version:
                raise BusinessException('会话已更新，请使用最新回复中的会话凭证',409)
        # 先占用会话版本及请求键，再释放事务调用模型。NULL 回执是持久化占位。
        # 模型超时/进程中断时保留占位，重试不可自动再次调用外部模型。
        from app.models.student.student_types import utcnow
        try:
            if version == 0:
                self.db.execute(insert(sessions).values(session_id=sid,student_id=actor.actor_id,version=1,created_at=utcnow(),updated_at=utcnow()))
            else:
                pending=self.db.execute(select(turns.c.id).where(turns.c.session_id==sid,turns.c.result.is_(None))).first()
                if pending:
                    raise BusinessException('当前会话已有执行中或待核实轮次',409)
                changed=self.db.execute(update(sessions).where(sessions.c.session_id==sid,sessions.c.student_id==actor.actor_id,sessions.c.version==version).values(version=version+1,updated_at=utcnow()))
                if changed.rowcount != 1:
                    raise BusinessException('会话已更新，请使用最新会话凭证',409)
            self.db.execute(insert(turns).values(session_id=sid,student_id=actor.actor_id,request_key=digest(key),parameters_hash=signature,message=body.message,result=None,created_at=utcnow()))
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            replay=self._replay(actor,key,signature)
            if replay is not None:
                return replay
            raise BusinessException('会话并发冲突，请刷新后核实',409) from None
        except Exception:
            self.db.rollback()
            raise
        rows=self.db.execute(select(turns.c.message,turns.c.result).where(turns.c.session_id==sid,turns.c.student_id==actor.actor_id,turns.c.result.is_not(None)).order_by(turns.c.id.desc()).limit(8)).mappings().all()
        history=[{'user':r['message'][:1500],'assistant':r['result']['answer'][:1500]} for r in reversed(rows)]
        context={}
        for action,scene in READ_ACTIONS.items():
            if ACTION_PERMISSIONS[action] in actor.scopes:
                try:
                    context[scene]=self.query.query(actor,scene,limit=5)
                except BusinessException as exc:
                    if exc.code != 503:
                        raise
                    context[scene]={'available':False,'message':'该事实来源未就绪'}
        knowledge=retrieve(body.message,db=self.db if 'course_project.read' in actor.scopes else None)
        self.db.rollback()  # 外部模型调用期间不持有数据库事务。
        decision,run_id=self.dify.run(body.message,actor,history=history,context=context,knowledge=knowledge)
        if decision.action not in ALLOWED[decision.intent]:
            raise BusinessException('AI动作与场景不一致',503)
        self._permission(actor,decision.action)
        pending=None
        data=None
        if decision.action in WRITE_ACTIONS:
            try:
                if decision.action == 'reminder.set':
                    from app.services.student.student_service import events,reminders
                    event=self.service._load(events,decision.parameters.get('academic_event_id'),actor,lock=False)
                    setting=self.db.execute(select(reminders).where(reminders.c.student_id==actor.actor_id,reminders.c.academic_event_id==event['id'],reminders.c.lead_minutes==decision.parameters.get('lead_minutes'))).mappings().first()
                    from app.services.student.student_service import public_time
                    decision.parameters.update(expected_event_version=event['event_version'],expected_updated_at=public_time(setting['updated_at']) if setting else None)
                if decision.action == 'leave.submit':
                    decision.parameters['generate_ai_summary']=False
                params=WRITE_ACTIONS[decision.action].model_validate(decision.parameters).model_dump(mode='json')
            except ValidationError:
                raise BusinessException('办理信息不完整，请补充后重试',400) from None
            claims={'subject':actor.key,'action':decision.action,'parameters':params,
                'summary':decision.summary,'workflow_run_id':run_id,'jti':digest([actor.key,key])[:32]}
            pending={'action':decision.action,'parameters':params,
                'action_token':sign_token(claims,'student-action',settings.STUDENT_ACTION_TTL_SECONDS)}
            decision.answer='信息已整理，请核对下方内容并确认；尚未提交。'
        elif decision.action in READ_ACTIONS:
            if decision.parameters:
                raise BusinessException('查询不接受模型指定学生或其他筛选参数',503)
            data=context[READ_ACTIONS[decision.action]]
            decision.answer='以下为当前本人业务记录；请以记录中的状态和更新时间为准。'
        if decision.intent in ('life','upgrade') and not knowledge:
            decision.answer='当前资料库没有可核实的相关资料，请联系服务老师补充或确认。'
        token=sign_token({'subject':actor.key,'session_id':sid,'version':version+1},'student-conversation',86400)
        result={'session_id':sid,'intent':decision.intent,'answer':decision.answer,'data':data,'pending_action':pending,
            'conversation_token':token,'workflow_run_id':run_id,
            'sources':[{k:d[k] for k in ('id','title','source')} for d in knowledge]}
        try:
            self.service.student(actor)
            session=self.db.execute(select(sessions).where(sessions.c.session_id==sid,sessions.c.student_id==actor.actor_id).with_for_update()).mappings().one()
            if session['version'] != version+1:
                raise BusinessException('会话版本已改变，模型结果需核实',409)
            self.service.defer_commit=True
            self.service.record_mental(actor,'chat:'+digest(key),body.message,decision.mental)
            changed=self.db.execute(update(turns).where(turns.c.session_id==sid,turns.c.student_id==actor.actor_id,turns.c.request_key==digest(key),turns.c.parameters_hash==signature,turns.c.result.is_(None)).values(result=result))
            if changed.rowcount != 1:
                raise BusinessException('轮次占位已变化，结果需核实',409)
            self.db.commit()
            return result
        except IntegrityError:
            self.db.rollback()
            replay=self._replay(actor,key,signature)
            if replay is not None:
                self.db.rollback()
                return replay
            raise BusinessException('会话正在更新，请重试',409) from None
        except Exception:
            self.db.rollback()
            raise
        finally:
            self.service.defer_commit=False
    def confirm(self,actor,token,request_key):
        from app.models import common as shared
        self.service.student(actor)
        claims=verify_token(token,'student-action',allow_expired=True)
        if claims.get('subject')!=actor.key:
            raise BusinessException('操作凭证不属于当前学生',403)
        action=claims.get('action')
        if action not in WRITE_ACTIONS or not isinstance(claims.get('jti'),str) or len(claims['jti'])!=32:
            raise BusinessException('不支持的办理动作',400)
        self._permission(actor,action)
        try:
            params=WRITE_ACTIONS[action].model_validate(claims['parameters'])
        except (ValidationError,KeyError):
            raise BusinessException('操作参数无效',400) from None
        key='confirm:'+claims['jti']
        op=shared.operation_log
        confirm_key=digest([actor.key,'confirmation.request',request_key])
        signature=digest(token)
        previous=self.db.execute(select(op).where(op.c.operation_key==confirm_key)).mappings().first()
        if previous and previous['parameters_hash']!=signature:
            raise BusinessException('同一确认请求键不能更换操作凭证',409)
        if previous and previous['operation_status']=='succeeded':
            return previous['result_reference']
        # 已成功业务允许过期后查回执；过期凭证不能产生新业务。
        completed=self.db.execute(select(op).where(op.c.student_id==actor.actor_id,op.c.request_key==key,op.c.operation_status=='succeeded')).mappings().first()
        if not completed:
            verify_token(token,'student-action')
        self.db.rollback()
        if not previous:
            try:
                self.db.execute(insert(op).values(operation_key=confirm_key,student_id=actor.actor_id,action_code='confirmation.request',entity_type='confirmation',request_key=request_key,parameters_hash=signature,operation_status='processing',row_version=1,created_at=utcnow(),updated_at=utcnow()))
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                current=self.db.execute(select(op).where(op.c.operation_key==confirm_key)).mappings().one()
                if current['parameters_hash']!=signature:
                    raise BusinessException('同一确认请求键不能更换操作凭证',409) from None
                if current['operation_status']=='succeeded':
                    return current['result_reference']
                self.db.rollback()
        if completed:
            result=completed['result_reference']
        elif action=='leave.submit':
            result=self.service.submit_leave(actor,key,params.model_copy(update={'generate_ai_summary':False}))
        elif action=='reminder.set':
            result=self.service.set_reminder(actor,key,params)
        else:
            summary=TicketSummary(summary=claims['summary'],category='other',workflow_run_id=claims['workflow_run_id']) if claims.get('summary') else None
            result=self.service.submit_ticket(actor,key,params,summary,allow_ai=False)
        self.db.execute(update(op).where(op.c.operation_key==confirm_key,op.c.parameters_hash==signature).values(operation_status='succeeded',result_reference=result,finished_at=utcnow(),updated_at=utcnow()))
        self.db.commit()
        return result
