"""工单时限配置与不可覆盖的轮次快照；不替学生关闭、重开工单。"""
from datetime import timedelta
from functools import lru_cache
import yaml
from sqlalchemy import select,insert
from fastapi.encoders import jsonable_encoder
from app.config import BASE_DIR
from app.models import common as t
from app.core.enterprise.enterprise_authorization import error
from app.repositories.enterprise.enterprise_repository import digest

@lru_cache(maxsize=1)
def policy():return yaml.safe_load((BASE_DIR/'app/enterprise_policy.yaml').read_text(encoding='utf-8'))

def new_cycle_snapshot(row,start):
    config=policy();rule=config['ticket_sla'].get(row['ticket_type'],{}).get(row['priority'])
    if rule is None:error(503,'工单类型及优先级未配置时限策略')
    return jsonable_encoder({'policy_version':config['version'],'cycle_no':row['reopen_count']+1,'started_at':start,'response_due_at':row['response_due_at'] if row['reopen_count'] else start+timedelta(hours=rule['response_hours']),'resolution_due_at':start+timedelta(hours=rule['resolution_hours']),'hours':rule,'clock':'continuous'})

def existing_cycle_snapshot(db,row):
    record=t.service_ticket_record;cycle=row['reopen_count']+1
    existing=db.execute(select(record.c.sla_snapshot).where(record.c.ticket_id==row['ticket_id'],record.c.cycle_no==cycle,record.c.record_type=='sla_cycle')).scalar_one_or_none()
    if existing:return existing
    # 既有事实只冻结已知期限，不能拿今天的默认策略回填未知历史。
    started=row['created_at'] if cycle==1 else db.scalar(select(record.c.created_at).where(record.c.ticket_id==row['ticket_id'],record.c.cycle_no==cycle,record.c.record_type=='reopen').order_by(record.c.ticket_record_id).limit(1))
    snapshot=jsonable_encoder({'policy_version':'legacy-unverified','cycle_no':cycle,'started_at':started,'response_due_at':row['response_due_at'],'resolution_due_at':row['resolution_due_at'],'first_response_at':row['first_response_at'],'clock':'continuous'})
    db.execute(insert(record).values(ticket_id=row['ticket_id'],record_type='sla_cycle',service_code='enterprise.ticket.policy',cycle_no=cycle,record_key=digest(['ticket-cycle',row['ticket_id'],cycle]),visibility='internal',sla_snapshot=snapshot,content='冻结既有轮次事实；未核实历史策略不参与策略达标统计'))
    return snapshot
