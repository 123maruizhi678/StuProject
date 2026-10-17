"""核对企业路由唯一性、基线逐字段／外键目标和实际中文注释。"""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import sqlglot
from sqlglot import exp
from sqlalchemy import inspect
from app.database import engine
from app.config import BASE_DIR,settings
from app.main import app

def main():
    paths=app.openapi()['paths'];operations=[]
    for path,methods in paths.items():
        if path.startswith('/api/v1/enterprise/'):
            for method,detail in methods.items():
                if method in {'get','post','put','delete','patch'}:operations.append({'method':method.upper(),'path':path,'operation_id':detail['operationId']})
    assert len({r['operation_id'] for r in operations})==len(operations),'重复操作ID'
    ddl=sqlglot.parse((BASE_DIR/'开发文档/操作文档_数据库建表语句.sql').read_text(encoding='utf-8-sig'),read='mysql')
    i=inspect(engine);tables=i.get_table_names();baseline=[];foreign_keys=[]
    for statement in ddl:
        if isinstance(statement,exp.Create):
            table=statement.this.this.name;expected={c.name for c in statement.this.expressions if isinstance(c,exp.ColumnDef)}
            columns=i.get_columns(table);actual={c['name'] for c in columns}
            assert expected<=actual,f'基线字段缺失:{table}'
            baseline.append({'table':table,'baseline_columns':len(expected),'actual_columns':len(actual)})
        if isinstance(statement,exp.Alter):
            table=statement.this.name;constraint=next(statement.find_all(exp.Constraint));name=constraint.this.name
            fk=next(constraint.find_all(exp.ForeignKey));reference=fk.args['reference'].this
            actual=next((f for f in i.get_foreign_keys(table) if f['name']==name),None)
            assert actual and actual['constrained_columns']==[c.name for c in fk.expressions] and actual['referred_table']==reference.this.name and actual['referred_columns']==[c.name for c in reference.expressions],f'外键目标不一致:{name}'
            foreign_keys.append(name)
    for table in tables:
        assert i.get_table_comment(table)['text'],f'表注释缺失:{table}'
        assert all(c['comment'] for c in i.get_columns(table)),f'字段注释缺失:{table}'
    report={'database':settings.DB_NAME,'baseline_tables':len(baseline),'baseline_fields':sum(t['baseline_columns'] for t in baseline),'verified_baseline_foreign_keys':len(foreign_keys),'actual_tables':len(tables),'actual_foreign_keys':sum(len(i.get_foreign_keys(t)) for t in tables),'chinese_comments_present':True,'enterprise_operations':len(operations),'tables':baseline}
    folder=BASE_DIR/'.runtime';folder.mkdir(exist_ok=True)
    (folder/'enterprise-contracts.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    header='# 企业管理接口清单\n\n由`scripts/enterprise/check_enterprise_contracts.py`按实际OpenAPI生成；增量教务／CRM接口纳入同一企业路由。所有企业接口要求有效员工JWT，写接口按固定Schema及细粒度动作授权，除已读外携带Idempotency-Key；更新要求expected_version。\n\n| 方法 | 路径 | 操作标识 |\n| --- | --- | --- |\n'
    content=header+'\n'.join('| '+r['method']+' | `'+r['path']+'` | `'+r['operation_id']+'` |' for r in operations)+'\n'
    (BASE_DIR/'开发文档/企业管理模块_接口清单.md').write_text(content,encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='tables'},ensure_ascii=False))
if __name__=='__main__':main()
