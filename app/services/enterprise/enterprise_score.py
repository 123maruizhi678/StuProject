"""教务成绩写入必须有精确课程授权。"""
from datetime import datetime
from sqlalchemy import select,insert
from app.config import settings
from app.models import common as t
from app.core.enterprise.enterprise_authorization import error,valid_binding
from app.repositories.enterprise.enterprise_repository import public

class ScoreService:
    def __init__(self,repo):self.repo=repo
    def authorized(self,student_id,course_code):
        ctx=self.repo.ctx
        if ctx.is_admin:
            if not self.repo.db.scalar(select(t.student_profile.c.student_id).where(t.student_profile.c.student_id==student_id,t.student_profile.c.is_archived==False,t.student_profile.c.status=='active')):error(400,'学生不存在、已停用或已归档')
            return
        if 'academic' not in ctx.roles:error(403,'成绩写入需要教务角色')
        student=t.student_profile
        exists=self.repo.db.scalar(select(student.c.student_id).where(student.c.student_id==student_id,student.c.is_archived==False,valid_binding(ctx,['score_editor'],student.c.student_id,course_code)))
        if not exists:error(403,'没有该学生及课程的明确写入授权')
    def mutate(self,verb,key,params,score_id=None):
        action='score.void' if verb=='void' else 'score.write';self.repo.ctx.require(action)
        if settings.ENTERPRISE_SCORE_AUTHORITY!='local':error(409,'当前教务权威来源不允许本地写入')
        def check(lock=False):
            row=self.repo.one('score',score_id,lock=lock);self.authorized(row['student_id'],row['course_code']);return row
        def work():
            now=datetime.utcnow()
            if verb=='create':
                self.authorized(params['student_id'],params['course_code'])
                if params['score_value']>params['max_score']:error(400,'成绩超过满分')
                values={**params,'employee_id':self.repo.ctx.employee_id,'status':'valid','row_version':1,'created_at':now,'updated_at':now,'recorded_at':now}
                # 字段以实际共享模型为准。
                values={k:v for k,v in values.items() if k in t.student_score.c}
                sid=self.repo.db.execute(insert(t.student_score).values(**values)).inserted_primary_key[0]
                return public({**values,'score_id':sid}),None,'student_score',sid
            row=check(True)
            if row['status']!='valid':error(409,'作废成绩不可直接更正')
            if not params.get('reason'):error(400,'更正／作废原因必填')
            if verb=='void':values={'status':'void'}
            else:
                if params['score_value']>params['max_score']:error(400,'成绩超过满分')
                values={'score_value':params['score_value'],'max_score':params['max_score'],'employee_id':self.repo.ctx.employee_id}
            result=self.repo.version_update('score',row,params.get('expected_version'),values)
            return public(result),row,'student_score',score_id
        return self.repo.operation('enterprise.'+action,key,{'verb':verb,'id':score_id,**params},work,lambda:check() if score_id else self.authorized(params['student_id'],params['course_code']))
