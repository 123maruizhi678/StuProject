"""从管理员维护的资料检索相关片段；缺少来源时不生成生活/升学事实。"""
import json
import re
from app.config import settings as student_settings
from app.core.common.response import BusinessException

def retrieve(message,limit=5,db=None):
    path=student_settings.STUDENT_KNOWLEDGE_FILE
    try:
        if path.is_file() and path.stat().st_size>5*1024*1024:
            raise ValueError()
        documents=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []
        if not isinstance(documents,list):
            raise ValueError()
        if db is not None:
            documents=documents+program_documents(db)
        words=re.findall(r'[a-z0-9]{2,}|[\u4e00-\u9fff]+',message.lower())
        tokens=set()
        for word in words:
            if re.fullmatch(r'[\u4e00-\u9fff]+',word):
                tokens.update(word[i:i+2] for i in range(max(0,len(word)-1)))
            else:
                tokens.add(word)
        ranked=[]
        for doc in documents:
            if not isinstance(doc,dict) or doc.get('active') is not True:
                continue
            if any(not isinstance(doc.get(k),str) or not doc[k].strip() for k in ('id','title','source','content')):
                continue
            hay=(doc['title']+' '+doc['content']).lower()
            score=sum((3 if token in doc['title'].lower() else 1) for token in tokens if token in hay)
            if score:
                ranked.append((score,{**{k:doc[k] for k in ('id','title','source')},'content':doc['content'][:3500]}))
        ranked.sort(key=lambda x:(-x[0],x[1]['id']))
        return [item for _,item in ranked[:limit]]
    except (OSError,ValueError,TypeError):
        raise BusinessException('学生资料库格式不可用，请联系维护人员',503) from None


def program_documents(db):
    """机构已上架项目作为正式推荐来源；只读固定字段，不接受AI生成SQL。"""
    from sqlalchemy import inspect,MetaData,Table,Column,BigInteger,String,Text,DateTime,select
    if not inspect(db.get_bind()).has_table('course_project'):
        return []
    table=Table('course_project',MetaData(),Column('id',BigInteger),Column('course_name',String),
        Column('category',String),Column('target_audience',String),Column('description',Text),
        Column('location',String),Column('signup_method',String),Column('status',String),Column('updated_at',DateTime))
    rows=db.execute(select(table).where(table.c.status=='上架').order_by(table.c.updated_at.desc(),table.c.id.desc()).limit(100)).mappings()
    return [{'id':'program-'+str(r['id']),'title':r['course_name'],'source':'机构在售项目目录，更新于 '+str(r['updated_at']),
        'content':'；'.join(str(r[k] or '') for k in ('category','target_audience','description','location','signup_method')),'active':True} for r in rows]
