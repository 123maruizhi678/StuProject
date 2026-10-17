"""在本机Dify API容器内运行，只输出版本与可用模型元数据。"""
import json,sys
sys.path.insert(0,'/app/api')
from app_factory import create_app
app=create_app()
with app.app_context():
    from extensions.ext_database import db
    from models import Account
    from models.account import Tenant,TenantAccountJoin
    from models.provider import TenantDefaultModel
    from models.model import App
    tenants=db.session.query(Tenant).all()
    result={'workspaces':[]}
    for tenant in tenants:
        defaults=db.session.query(TenantDefaultModel).filter_by(tenant_id=tenant.id).all()
        result['workspaces'].append({'id':tenant.id,'models':[{'provider':m.provider_name,'model':m.model_name,'type':m.model_type} for m in defaults],
          'enterprise_apps':[{'id':a.id,'name':a.name} for a in db.session.query(App).filter(App.tenant_id==tenant.id,App.name.like('StuProject-企业-%')).all()]})
    print('INVENTORY_JSON='+json.dumps(result,ensure_ascii=False))
