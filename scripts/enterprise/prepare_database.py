"""执行已审核的本地基线；保留已有对象，执行记录不含凭据。"""
from pathlib import Path
import sys,re,json,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import sqlglot
from sqlglot import exp
from sqlalchemy import create_engine,inspect
from sqlalchemy.engine import URL
from sqlalchemy.dialects import mysql
from app.database import engine
from app.config import settings
ROOT=Path(__file__).resolve().parents[2]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    if settings.DB_HOST not in ('localhost','127.0.0.1','::1'): raise RuntimeError('仅允许本地业务数据库')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',settings.DB_NAME): raise RuntimeError('非法目标库名')
    ddl=(ROOT/'开发文档/操作文档_数据库建表语句.sql').read_text(encoding='utf-8-sig')
    statements=[s for s in sqlglot.parse(ddl,read='mysql') if isinstance(s,(exp.Create,exp.Alter))]
    if not args.apply:
        print(json.dumps({'database':settings.DB_NAME,'creates':sum(isinstance(s,exp.Create) for s in statements),'alters':sum(isinstance(s,exp.Alter) for s in statements)}));return
    admin=create_engine(URL.create('mysql+pymysql',username=settings.DB_USER,password=settings.DB_PASSWORD,host=settings.DB_HOST,port=settings.DB_PORT,query={'charset':'utf8mb4'}),isolation_level='AUTOCOMMIT')
    with admin.connect() as c: c.exec_driver_sql(f'CREATE DATABASE IF NOT EXISTS `{settings.DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
    admin.dispose(); results=[]
    with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
        c.exec_driver_sql("SET time_zone = '+00:00'")
        for stmt in statements:
            i=inspect(c)
            if isinstance(stmt,exp.Create):
                name=stmt.this.this.name
                if i.has_table(name):
                    expected={col.name:col for col in stmt.this.expressions if isinstance(col,exp.ColumnDef)}
                    actual={col['name']:col for col in i.get_columns(name)}
                    plan=json.loads((ROOT/'scripts/sql/enterprise/migration_plan.json').read_text(encoding='utf-8'))
                    approved={definition.split()[0] for definition in plan['shared_changes'].get(name,[]) if not definition.startswith('synced_at')}
                    if not set(expected)<=set(actual) or set(actual)-set(expected)-approved:raise RuntimeError(f'{name}已有未登记字段差异')
                    for field,definition in expected.items():
                        desired=definition.kind.sql(dialect='mysql').upper()
                        if desired=='BOOLEAN':desired='TINYINT(1)'
                        present=re.split(r'\s+(?:COLLATE|CHARACTER SET)\s+',actual[field]['type'].compile(dialect=mysql.dialect()).upper())[0]
                        present=sqlglot.parse_one(present,into=exp.DataType,read='mysql').sql(dialect='mysql').upper()
                        nullable=not any(isinstance(c.kind,exp.NotNullColumnConstraint) and not c.kind.args.get('allow_null',False) for c in definition.constraints)
                        nullable_override=field=='synced_at' and name in ('student_academic_event','student_application_progress')
                        if desired!=present or (actual[field]['nullable']!=nullable and not nullable_override):raise RuntimeError(f'{name}.{field}已有类型或可空差异: expected={desired}/{nullable}, actual={present}/{actual[field]["nullable"]}')
                    results.append({'table':name,'status':'existing'});continue
            else:
                name=stmt.this.name
                constraint=next(stmt.find_all(exp.Constraint)).this.name
                if any(k.get('name')==constraint for k in i.get_foreign_keys(name)): continue
            c.exec_driver_sql(stmt.sql(dialect='mysql'))
            results.append({'table':name,'status':'created' if isinstance(stmt,exp.Create) else 'foreign_key_added'})
    print(json.dumps({'database':settings.DB_NAME,'results':results},ensure_ascii=False))
if __name__=='__main__': main()
