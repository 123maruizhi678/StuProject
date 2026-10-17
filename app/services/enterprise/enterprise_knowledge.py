"""内部知识发布与授权检索；先筛选受众再把片段交模型。"""
from datetime import datetime
import re
from sqlalchemy import insert,select,or_
from app.models.enterprise import knowledge_entry as table
from app.core.enterprise.enterprise_authorization import error,scope
from app.repositories.enterprise.enterprise_repository import public
from app.services.enterprise.enterprise_customer import utc
from app.clients.enterprise.enterprise_dify import EnterpriseDifyClient

class KnowledgeService:
    def published(self):
        now=datetime.utcnow()
        return (table.c.status=='published')&(table.c.index_status=='ready')&(table.c.effective_from<=now)&or_(table.c.expires_at.is_(None),table.c.expires_at>now)
    def __init__(self,repo,client=None):self.repo,self.client=repo,client or EnterpriseDifyClient()
    def manage_row(self,kid,lock=False):
        self.repo.ctx.require('knowledge.manage')
        q=select(table).where(table.c.knowledge_id==kid)
        if lock:q=q.with_for_update()
        row=self.repo.db.execute(q).mappings().first()
        if not row:error(404,'知识条目不存在')
        return dict(row)
    def mutate(self,verb,key,params,knowledge_id=None):
        action='knowledge.publish' if verb=='publish' else 'knowledge.manage';self.repo.ctx.require(action)
        def work():
            now=datetime.utcnow();ctx=self.repo.ctx;values=dict(params);expected=values.pop('expected_version',None);values.pop('reason',None)
            if verb=='create':
                values.update(employee_id=ctx.employee_id,category_code='internal',status='draft',index_status='pending',version_no=1,row_version=1,created_at=now,updated_at=now)
                self.content(values)
                kid=self.repo.db.execute(insert(table).values(**values)).inserted_primary_key[0]
                return public({**values,'knowledge_id':kid}),None,'knowledge_entry',kid
            row=self.manage_row(knowledge_id,True)
            if verb=='disable':
                if not params.get('reason'):error(400,'停用原因必填')
                values={'status':'disabled','index_status':'pending'}
            elif verb=='publish':
                self.content(row)
                start=utc(values['effective_from']);end=utc(values.get('expires_at'))
                if end and end<=start:error(400,'有效期结束须晚于开始')
                # 此版本RAG直接检索已授权关系库正文，事务切换即为索引准备完成，无远端私密索引副本。
                values={'effective_from':start,'expires_at':end,'reviewer_employee_id':ctx.employee_id,'reviewed_at':now,'status':'published','index_status':'ready'}
            else:
                self.content({**row,**values})
                values.update(status='draft',index_status='pending',version_no=row['version_no']+1,reviewer_employee_id=None,reviewed_at=None)
            result=self.repo.version_update('knowledge',row,expected,values)
            return public(result),row,'knowledge_entry',knowledge_id
        return self.repo.operation('enterprise.'+action,key,{'verb':verb,'id':knowledge_id,**params},work,lambda:self.manage_row(knowledge_id) if knowledge_id else None)
    @staticmethod
    def content(values):
        if values['entry_type']=='faq' and (not values.get('question') or not values.get('answer')):error(400,'FAQ须有标准问题和答案')
        if values['entry_type']=='document' and not values.get('content_text'):error(400,'发布本地文档须提供可检索正文')
    def ask(self,question):
        self.repo.ctx.require('knowledge.read')
        tokens=[s for s in re.split(r'[\s，。！？、,.!?]+',question) if s]
        words=list(dict.fromkeys(tokens+[s[i:i+2] for s in re.findall(r'[\u4e00-\u9fff]+',question) for i in range(max(0,len(s)-1))]))[:24]
        if not words:error(400,'问题不能为空')
        predicate=or_(*[table.c.title.contains(word,autoescape=True)|table.c.question.contains(word,autoescape=True)|table.c.content_text.contains(word,autoescape=True) for word in words])
        rows=self.repo.db.execute(select(table).where(scope(self.repo.ctx,'knowledge',table),self.published(),predicate).order_by(table.c.version_no.desc(),table.c.knowledge_id).limit(5)).mappings().all()
        if not rows:return {'answer':'未找到当前授权范围内可核实的制度依据。','citations':[],'mode':'no_source'}
        sources=[{'id':r['knowledge_id'],'version':r['version_no'],'title':r['title'],'content':(r['answer'] if r['entry_type']=='faq' else r['content_text'])[:12000]} for r in rows]
        result=self.client.run('knowledge',{'question':question,'mode':'qa' if all(r['entry_type']=='faq' for r in rows) else 'rag','candidates':sources,'contract_version':'enterprise-v1'},self.repo.ctx.user_id)
        citations=result.get('citations')
        allowed={(s['id'],s['version']) for s in sources}
        if not isinstance(result.get('answer'),str) or not isinstance(citations,list) or not citations or any(not isinstance(c,dict) or (c.get('id'),c.get('version')) not in allowed for c in citations):error(503,'知识答案缺少可信来源引用')
        # 调用期间知识可能停用或权限变化，返回前再次核验有效版本。
        self.repo.db.rollback()
        from app.models.common import UserAccount
        from app.core.enterprise.enterprise_authorization import context_for
        account=self.repo.db.get(UserAccount,self.repo.ctx.user_id,populate_existing=True)
        if account is None:error(401,'账号已失效')
        self.repo.ctx=context_for(self.repo.db,account)
        for c in citations:
            if not self.repo.db.scalar(select(table.c.knowledge_id).where(table.c.knowledge_id==c['id'],table.c.version_no==c['version'],self.published(),scope(self.repo.ctx,'knowledge',table))):error(409,'知识版本或访问权限已变化，请重新查询')
        return result
