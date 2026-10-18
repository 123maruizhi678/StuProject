"""复用既有会话表保存心情反馈与公开关怀建议，不暴露内部预警记录。"""
from sqlalchemy import select, insert, update, func
from sqlalchemy.exc import IntegrityError
from app.core.common.response import BusinessException
from app.models.student.student_conversation import sessions, turns
from app.models.student.student_types import utcnow
from app.services.student.student_service import digest, public_time
from app.services.student.student_chat import StudentChatService


class StudentCareService:
    def __init__(self, service, dify=None):
        self.service, self.db, self.dify = service, service.db, dify

    def _public(self, row):
        result = row['result'] or {}
        return {'id': row['id'], 'content': row['message'],
            'created_at': public_time(row['created_at']),
            'status': 'completed' if row['result'] is not None else 'pending',
            'reply': result.get('answer'), 'reply_source': result.get('reply_source')}

    def history(self, actor, limit=20, offset=0):
        self.service.student(actor)
        where = (turns.c.student_id == actor.actor_id, turns.c.session_id.like('care-%'))
        rows = self.db.execute(select(turns).where(*where).order_by(
            turns.c.created_at.desc(), turns.c.id.desc()).limit(limit).offset(offset)).mappings().all()
        total = self.db.scalar(select(func.count()).select_from(turns).where(*where))
        return {'items': [self._public(row) for row in rows], 'total': total, 'limit': limit, 'offset': offset}

    def submit(self, actor, key, body):
        self.service.student(actor)
        if not body.chat_content.strip():
            raise BusinessException('请填写心情反馈。', 400)
        sid = 'care-' + digest([actor.key, key])[:48]
        signature = digest(body.model_dump(mode='json'))
        row = self.db.execute(select(turns).where(turns.c.session_id == sid,
            turns.c.student_id == actor.actor_id)).mappings().first()
        if row and row['parameters_hash'] != signature:
            raise BusinessException('同一请求不能更换反馈内容。', 409)
        if row and row['result'] is not None:
            return self._public(row)
        self.db.rollback()
        if not row:
            now = utcnow()
            try:
                self.db.execute(insert(sessions).values(session_id=sid, student_id=actor.actor_id,
                    version=1, created_at=now, updated_at=now))
                self.db.execute(insert(turns).values(session_id=sid, student_id=actor.actor_id,
                    request_key=digest(['care', key]), parameters_hash=signature,
                    message=body.chat_content, result=None, created_at=now))
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                row = self.db.execute(select(turns).where(turns.c.session_id == sid,
                    turns.c.student_id == actor.actor_id)).mappings().first()
                if not row or row['parameters_hash'] != signature:
                    raise BusinessException('反馈请求已变化，请刷新核对。', 409) from None
                if row['result'] is not None:
                    return self._public(row)
                self.db.rollback()
        # 模型失败时保留待核实原文，原有 monitor 幂等机制禁止重复调用。
        receipt = StudentChatService(self.service, self.dify, None).monitor(actor, 'care:' + digest(key), body)
        support = receipt.get('support_required', False)
        answer = ('谢谢你愿意说出自己的感受。先给自己一点时间休息，也可以联系信任的人或负责老师，一起寻找支持。'
            if support else '谢谢你愿意记录自己的感受。可以先停下来休息一会儿，做一件让自己放松的小事；想继续说说时，助手也在这里。')
        result = {'answer': answer, 'reply_source': '通用关怀建议', 'kind': 'care_feedback'}
        self.service.student(actor)
        self.db.execute(update(turns).where(turns.c.session_id == sid, turns.c.student_id == actor.actor_id,
            turns.c.parameters_hash == signature, turns.c.result.is_(None)).values(result=result))
        self.db.execute(update(sessions).where(sessions.c.session_id == sid,
            sessions.c.student_id == actor.actor_id).values(updated_at=utcnow()))
        self.db.commit()
        row = self.db.execute(select(turns).where(turns.c.session_id == sid,
            turns.c.student_id == actor.actor_id)).mappings().one()
        return self._public(row)
