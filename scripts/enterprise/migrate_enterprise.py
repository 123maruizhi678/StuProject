"""企业必要增量；存在的对象逐项跳过，执行结果只含结构元数据。"""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sqlalchemy import inspect
from app.database import engine
from app.config import BASE_DIR,settings

def main():
    if settings.DB_HOST not in ('localhost','127.0.0.1'):raise RuntimeError('仅允许本地目标')
    import sqlglot
    ddl=(BASE_DIR/'scripts/sql/enterprise/001_local_education.sql').read_text(encoding='utf-8')
    results=[]
    with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
        for statement in sqlglot.parse(ddl,read='mysql'):
            if statement is None:continue
            name=statement.this.this.name
            if not inspect(conn).has_table(name):conn.exec_driver_sql(statement.sql(dialect='mysql'));results.append('create:'+name)
        changes={
          'customer_followup':{'schedule_operation_id':"BIGINT NULL COMMENT '当前安排代次，关联成功操作审计主键'",'schedule_base_at':"DATETIME(6) NULL COMMENT '当前安排提醒基准时间，UTC'"},
          'service_ticket_record':{'sla_snapshot':"JSON NULL COMMENT '每轮时限策略版本、期限及处理事件快照'"},
          'student_application_progress':{'row_version':"INTEGER NOT NULL DEFAULT 1 COMMENT '并发修改版本号'"}}
        for table,columns in changes.items():
            existing={c['name'] for c in inspect(conn).get_columns(table)}
            for name,definition in columns.items():
                if name not in existing:conn.exec_driver_sql(f'ALTER TABLE `{table}` ADD COLUMN `{name}` {definition}');results.append('add:'+table+'.'+name)
        for table in ['student_academic_event','student_application_progress']:
            column=next(c for c in inspect(conn).get_columns(table) if c['name']=='synced_at')
            if not column['nullable']:conn.exec_driver_sql(f"ALTER TABLE `{table}` MODIFY COLUMN synced_at DATETIME(6) NULL COMMENT '最近真实外部同步时间，local来源为空'");results.append('nullable:'+table+'.synced_at')
    folder=BASE_DIR/'.runtime';folder.mkdir(exist_ok=True)
    from datetime import datetime,timezone
    with (folder/'enterprise-migration.jsonl').open('a',encoding='utf-8') as log:log.write(json.dumps({'version':'enterprise-local-v1','database':settings.DB_NAME,'executed':results,'time':datetime.now(timezone.utc).isoformat()},ensure_ascii=False)+'\n')
    print(json.dumps({'version':'enterprise-local-v1','executed':results}))
if __name__=='__main__':main()
