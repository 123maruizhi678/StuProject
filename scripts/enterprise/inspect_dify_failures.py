"""在Dify容器中读取本次企业工作流的脱敏错误类型，不输出输入和模型正文。"""
import sys,json
sys.path.insert(0,'/app/api')
from app_factory import create_app
app=create_app()
with app.app_context():
    from extensions.ext_database import db
    from models.workflow import WorkflowRun
    rows=db.session.query(WorkflowRun).filter(WorkflowRun.app_id.in_(['66906358-488a-4116-86c3-05068185bf63','26eff5cb-b96e-4db1-b476-ebc6c710fbd5']),WorkflowRun.status=='failed').order_by(WorkflowRun.created_at.desc()).limit(3).all()
    for row in rows:print(json.dumps({'app_id':row.app_id,'error':row.error,'time':str(row.created_at)}))
