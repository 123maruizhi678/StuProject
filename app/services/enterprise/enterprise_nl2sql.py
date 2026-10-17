"""后端构造授权关系，再以只读连接执行受限SQL。"""
from datetime import datetime
from sqlalchemy import select,text,create_engine
from sqlalchemy.engine import URL
from app.config import settings
from app.core.enterprise.enterprise_authorization import scope,error
from app.core.enterprise.enterprise_sql_guard import validate_query
from app.repositories.enterprise.enterprise_repository import RESOURCES,public
from app.clients.enterprise.enterprise_nl2sql_dify import generate

DOMAINS={'customers':('customer','customer.read',['customer_id','full_name','education_level','target_country_code','status','created_at']),
 'followups':('followup','customer.read',['followup_id','customer_id','followup_at','content','followup_status']),
 'daily_reports':('daily','daily.read',['daily_report_id','employee_id','report_date','submitted_content','ai_summary']),
 'scores':('score','score.read',['student_id','course_code','term_code','score_value','max_score']),
 'tickets':('ticket','ticket.read',['ticket_id','student_id','category_code','status','created_at','resolved_at','closed_at'])}

def run_query(repo,question,filters,client=None):
    repo.ctx.require('query');normalized={}
    for key,value in filters.items():
        if key=='status' and isinstance(value,str) and len(value)<=32:normalized[key]=value
        elif key in ('customer_id','student_id') and isinstance(value,int) and not isinstance(value,bool) and value>0:normalized[key]=value
        elif key in ('start_time','end_time') and isinstance(value,str):
            try:
                from app.services.enterprise.enterprise_customer import utc
                normalized[key]=utc(datetime.fromisoformat(value.replace('Z','+00:00')))
            except ValueError:error(400,'查询时间无效')
        else:error(400,'筛选项或值类型不在白名单')
    relations,ctes,server_values=scoped_relations(repo)
    if not relations:error(403,'没有可查询的数据域')
    candidate=generate({'question':question,'schema_context':relations,'dialect':'mysql','query_constraints':{'select_only':True,'max_rows':100},'bound_filters':{k:str(v) for k,v in normalized.items()},'schema_version':'enterprise-query-v1','contract_version':settings.ENTERPRISE_DIFY_CONTRACT_VERSION},repo.ctx.user_id,client)
    # 模型调用期间可能发生离职、调部门或撤权；执行前重新构建所有受限关系。
    from app.core.enterprise.enterprise_authorization import context_for
    from app.models.common import UserAccount
    repo.db.rollback()
    account=repo.db.get(UserAccount,repo.ctx.user_id,populate_existing=True)
    if account is None:error(401,'账号已失效')
    repo.ctx=context_for(repo.db,account);repo.ctx.require('query')
    relations,ctes,server_values=scoped_relations(repo)
    if candidate.get('schema_version')!='enterprise-query-v1':error(503,'查询Schema版本不匹配')
    sql,values=validate_query(candidate.get('sql_template'),candidate.get('params'),normalized,relations)
    return execute_readonly(sql,values,ctes,server_values)

def scoped_relations(repo):
    relations={};ctes=[];server_values={}
    for name,(resource,action,columns) in DOMAINS.items():
        if not repo.ctx.can(action):continue
        table,_=RESOURCES[resource];query=select(*[table.c[col] for col in columns]).where(scope(repo.ctx,resource,table))
        if resource=='daily':query=query.where(table.c.status=='submitted')
        compiled=query.compile(compile_kwargs={'render_postcompile':True})
        # 每个受限关系拥有独立参数命名空间，禁止覆盖授权绑定值。
        source=str(compiled)
        for k in sorted(compiled.params,key=len,reverse=True):
            import re
            new='scope_'+name+'_'+k
            source=re.sub(r':'+re.escape(k)+r'\b',':'+new,source);server_values[new]=compiled.params[k]
        ctes.append(name+' AS ('+source+')');relations[name]=columns
    return relations,ctes,server_values

def execute_readonly(sql,values,ctes,server_values):
    if not settings.ENTERPRISE_READ_DB_USER or not settings.ENTERPRISE_READ_DB_PASSWORD:error(503,'受限只读连接未配置')
    readonly=create_engine(URL.create('mysql+pymysql',username=settings.ENTERPRISE_READ_DB_USER,password=settings.ENTERPRISE_READ_DB_PASSWORD,host=settings.DB_HOST,port=settings.DB_PORT,database=settings.DB_NAME,query={'charset':'utf8mb4'}),connect_args={'connect_timeout':5,'read_timeout':5},pool_pre_ping=True,hide_parameters=True)
    try:
        with readonly.connect() as conn:
            conn.exec_driver_sql("SET time_zone='+00:00'")
            conn.exec_driver_sql(f'SET SESSION MAX_EXECUTION_TIME={settings.ENTERPRISE_QUERY_TIMEOUT_MS}')
            conn.exec_driver_sql('START TRANSACTION READ ONLY')
            rows=conn.execute(text('WITH '+','.join(ctes)+' '+sql),{**server_values,**values}).mappings().all()
            conn.rollback()
            return {'rows':[public(r) for r in rows],'row_count':len(rows),'limit':100,'schema_version':'enterprise-query-v1'}
    finally:readonly.dispose()
