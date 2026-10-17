"""在已有本地Dify API容器内执行，只创建／更新StuProject四个企业应用。"""
from pathlib import Path
import json,sys
sys.path.insert(0,'/app/api')
from app_factory import create_app
flask_app=create_app()
with flask_app.app_context():
    from extensions.ext_database import db
    from models.account import Account,Tenant,TenantAccountJoin
    from models.model import App,ApiToken
    from services.app_dsl_service import AppDslService
    from services.workflow_service import WorkflowService
    tenants=db.session.query(Tenant).all()
    if len(tenants)!=1:raise RuntimeError('须明确唯一目标工作区，拒绝猜测')
    tenant=tenants[0]
    membership=db.session.query(TenantAccountJoin).filter(TenantAccountJoin.tenant_id==tenant.id,TenantAccountJoin.role=='owner').first()
    if membership is None:raise RuntimeError('工作区缺少合法所有者')
    account=db.session.get(Account,membership.account_id);account.current_tenant=tenant
    keys={'extract':'ENTERPRISE_EXTRACT_DIFY_API_KEY','query':'ENTERPRISE_NL2SQL_DIFY_API_KEY','knowledge':'ENTERPRISE_KNOWLEDGE_DIFY_API_KEY','summary':'ENTERPRISE_SUMMARY_DIFY_API_KEY'}
    filenames={'extract':'enterprise_extract.yml','query':'enterprise_nl2sql_readonly.yml','knowledge':'enterprise_knowledge.yml','summary':'enterprise_daily_summary.yml'}
    result={'config':{},'apps':[]}
    for scene,filename in filenames.items():
        name='StuProject-企业-'+scene
        existing=db.session.query(App).filter_by(tenant_id=tenant.id,name=name).one_or_none()
        imported=AppDslService(db.session).import_app(account=account,import_mode='yaml-content',yaml_content=(Path('/tmp/stuproject-enterprise')/filename).read_text(),app_id=existing.id if existing else None)
        if not imported.app_id or imported.status not in ('completed','completed-with-warnings'):raise RuntimeError('企业DSL导入失败: '+str(imported.error))
        app=db.session.get(App,imported.app_id)
        workflow=WorkflowService().publish_workflow(session=db.session,app_model=app,account=account,marked_name='enterprise-v1',marked_comment='StuProject本地企业管理发布')
        db.session.flush();app.workflow_id=workflow.id;app.enable_api=True
        token=db.session.query(ApiToken).filter_by(app_id=app.id,type='app').first()
        if token is None:
            token=ApiToken(app_id=app.id,tenant_id=tenant.id,type='app',token=ApiToken.generate_api_key('app-',32));db.session.add(token)
        db.session.commit()
        result['config'][keys[scene]]=token.token
        result['apps'].append({'scene':scene,'app_id':app.id,'workflow_id':workflow.id,'status':'published'})
    target=Path('/tmp/stuproject-enterprise.runtime.json');target.write_text(json.dumps(result,ensure_ascii=False))
    print('DEPLOYMENT_JSON='+json.dumps({'apps':result['apps'],'secrets_written_to_runtime_file':True},ensure_ascii=False))
