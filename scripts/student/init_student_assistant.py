"""默认只读预检，--ddl只输出学生DDL；不重建公共表，不执行旧表数据迁移。"""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))


def check(connection):
    from sqlalchemy import inspect
    from app.repositories.student.student_schema import check_student_schema
    from app.models.student.student import STUDENT_TABLES
    from app.models.student.student_conversation import sessions,turns
    inspector=inspect(connection)
    report={'shared':[check_student_schema(connection,f) for f in ('leave','ticket')],
            'missing':[],'incompatible':[],'legacy_tables':[]}
    for name in ('student_leave_request','student_notification'):
        if inspector.has_table(name):
            report['legacy_tables'].append(name)
    for table in [*STUDENT_TABLES,sessions,turns]:
        if not inspector.has_table(table.name):
            report['missing'].append(table.name)
            continue
        columns={c['name']:c for c in inspector.get_columns(table.name)}
        report['incompatible'] += [table.name+'.'+c.name+':missing' for c in table.c if c.name not in columns]
        if table.name in ('student_academic_event','student_application_progress') and not columns.get('synced_at',{}).get('nullable',False):
            report['incompatible'].append(table.name+'.synced_at:local_authority_requires_nullable')
        if table is turns and not columns.get('result',{}).get('nullable',False):
            report['incompatible'].append(table.name+'.result:must_allow_null_reservation')
        if table.name=='student_academic_reminder':
            col=columns.get('updated_at',{})
            if 'ON UPDATE' in str(col.get('default','')).upper():
                report['incompatible'].append(table.name+'.updated_at:must_not_auto_update')
            precision=getattr(col.get('type'),'fsp',None)
            if connection.dialect.name=='mysql' and precision!=6:
                report['incompatible'].append(table.name+'.updated_at:requires_microseconds')
        actual={(tuple(f['constrained_columns']),f['referred_table'],tuple(f['referred_columns'])) for f in inspector.get_foreign_keys(table.name)}
        for fk in table.foreign_key_constraints:
            expected=(tuple(e.parent.name for e in fk.elements),fk.elements[0].column.table.name,tuple(e.column.name for e in fk.elements))
            if expected not in actual:
                report['incompatible'].append(table.name+':foreign_key:'+','.join(expected[0]))
    report['compatible']=all(r['compatible'] for r in report['shared']) and not report['missing'] and not report['incompatible'] and not report['legacy_tables']
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ddl',action='store_true')
    parser.add_argument('--dry-run',action='store_true',help='只读核验实际数据库，不执行DDL')
    args=parser.parse_args()
    if args.ddl:
        print((ROOT/'scripts/sql/student/20261017_student_tables.sql').read_text(encoding='utf-8'))
    else:
        from app.database import engine
        try:
            with engine.connect() as connection:
                report=check(connection)
            print(json.dumps(report,ensure_ascii=False))
            raise SystemExit(0 if report['compatible'] else 1)
        except __import__('sqlalchemy').exc.SQLAlchemyError:
            print(json.dumps({'compatible':False,'error':'DATABASE_UNAVAILABLE','message':'数据库连接或认证失败，请核对启动环境变量及.env配置；未执行任何DDL。'},ensure_ascii=False))
            raise SystemExit(2)
        finally:
            engine.dispose()
