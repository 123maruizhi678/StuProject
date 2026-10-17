"""以开发文档最终DDL/附录契约校验，不依赖业务文档。"""
from pathlib import Path
import re
from datetime import datetime,timedelta,timezone
from sqlalchemy import insert,select,update
from app.models import common as t
from app.models.student.student import STUDENT_TABLES
from app.models.student.student_conversation import sessions,turns
from app.services.student.student_service import warnings
from .test_minimal_units import post,employee,leave_body

ROOT=Path(__file__).resolve().parents[2]


def test_personal_and_shared_columns_match_final_ddl():
    sql=(ROOT/'开发文档/操作文档_数据库建表语句.sql').read_text(encoding='utf-8')
    tables=[getattr(t,name).__table__ if name=='UserAccount' else getattr(t,name) for name in t.__all__]+list(STUDENT_TABLES)+[sessions,turns]
    for table in tables:
        ddl=re.search(r'CREATE TABLE `'+table.name+r'` \((.*?)\) ENGINE',sql,re.S).group(1)
        fields={m.group(1):m.group(2) for m in re.finditer(r'^  `([^`]+)` (.*)$',ddl,re.M)}
        if table.name=="operation_log":
            fields["actor_account_id"]="BIGINT NULL"  # 公共账号审计增量字段。
        assert set(table.c.keys())==set(fields),table.name
        for col in table.c:
            # 操作文档048优先于源DDL：本地权威的synced_at应允许NULL。
            local_sync_exception=table.name in ('student_academic_event','student_application_progress') and col.name=='synced_at'
            assert col.nullable==(local_sync_exception or 'NOT NULL' not in fields[col.name]),(table.name,col.name)
            if table.name != "user_account":
                assert col.comment,(table.name,col.name)
        foreign_keys=[m for m in re.finditer(r'ALTER TABLE `'+table.name+r'` ADD CONSTRAINT `[^`]+` FOREIGN KEY \(([^)]+)\) REFERENCES `([^`]+)` \(([^)]+)\)',sql)]
        expected={(tuple(m[1].replace('`','').split(',')),m[2],tuple(m[3].replace('`','').split(','))) for m in foreign_keys}
        observed={(tuple(e.parent.name for e in fk.elements),fk.elements[0].column.table.name,tuple(e.column.name for e in fk.elements)) for fk in table.foreign_key_constraints}
        if table.name=="operation_log":
            expected.add((("actor_account_id",),"user_account",("user_id",)))
        assert observed==expected,table.name


def test_leave_final_whitelist_and_status_filter(unit):
    result=post(unit,'student/leave',leave_body())['data']
    aid=result['apply_id']
    detail=unit.client.get(f'/api/v1/student/leave/{aid}').json()['data']
    required={'apply_id','student_id','apply_type','apply_content','leave_type','approval_status','leave_start_at','leave_end_at','reviewer_id','reviewed_at','approval_comment','row_version','created_at','updated_at'}
    assert set(detail)==required
    assert unit.client.get('/api/v1/student/leave?approval_status=approved').json()['data']['total']==0
    employee(unit,11)
    detail2=unit.client.get(f'/api/v1/internal/student/leave/{aid}').json()['data']
    assert detail==detail2
    result=post(unit,f'internal/student/leave/{aid}/decision',{'expected_version':1,'decision':'approved','comment':'同意'},'approved-final-0001')['data']
    assert {'apply_id','approval_status','row_version','reviewed_at','reviewer_id'}==set(result)
    with unit.sessions() as db:
        reviewed=db.scalar(select(t.student_admin_service.c.reviewed_at))
        assert datetime.fromisoformat(result['reviewed_at'].rstrip('Z'))==reviewed


def test_ticket_reopen_retains_first_response_and_uses_comment(unit):
    result=post(unit,'student/complaint',{'content':'需要反馈','ticket_type':'suggestion'})['data']
    tid=result['ticket_id']
    with unit.sessions.begin() as db:
        row=db.execute(select(t.service_ticket)).mappings().one()
        first_response=row['created_at']+timedelta(minutes=1)
        original_deadline=row['response_due_at']
        assert row['response_due_at']-row['created_at']==timedelta(hours=48)
        assert row['resolution_due_at']-row['created_at']==timedelta(hours=120)
        db.execute(update(t.service_ticket).where(t.service_ticket.c.ticket_id==tid).values(status='awaiting_student',solution='人工方案',resolved_at=first_response,first_response_at=first_response))
    result=post(unit,f'student/tickets/{tid}/confirm',{'expected_version':1,'resolved':False,'comment':'尚未解决'},'reopen-final-0001')
    assert result['code']==0,result
    with unit.sessions() as db:
        row=db.execute(select(t.service_ticket)).mappings().one()
        assert row['first_response_at']==first_response and row['response_due_at']==original_deadline
        assert row['status']=='reopened' and row['reopen_count']==1
        record=db.execute(select(t.service_ticket_record).where(t.service_ticket_record.c.record_type=='reopen')).mappings().one()
        assert record['cycle_no']==2 and record['content']=='尚未解决'


def test_warning_history_uses_final_ids_and_permissions(unit):
    from app.schemas.student.student import MentalAssessment
    from app.services.student.student_service import StudentService
    with unit.sessions() as db:
        StudentService(db).record_mental(unit.state.actor,'risk-final-0001','可信入口消息',MentalAssessment(emotion_tag='低落',emotion_score=10,risk_level='high',trigger_reason='仅授权老师可见'))
        warning_id=db.scalar(select(warnings.c.id))
    employee(unit,11)
    detail=unit.client.get(f'/api/v1/internal/student/warnings/{warning_id}').json()
    assert detail['code']==0 and detail['data']['warning_id']==warning_id,detail
    assert 'id' not in detail['data'] and 'version' not in detail['data']
    for action,version in [('ack',1),('follow',2),('close',3)]:
        result=post(unit,f'internal/student/warnings/{warning_id}/{action}',{'expected_version':version,'note':'跟进记录'+action},'warning-'+action+'-0001')
        assert result['code']==0,result
    detail=unit.client.get(f'/api/v1/internal/student/warnings/{warning_id}').json()['data']
    assert [r['action_code'] for r in detail['history']]==['mental.ack','mental.follow','mental.close']


def test_public_static_resources_and_only_one_deployable_workflow():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        for page in ('/login','/student-assistant','/static/index.html'):
            response=client.get(page)
            assert response.status_code==200
            for resource in re.findall(r'(?:src|href)="(/static/[^"?]+)',response.text):
                assert client.get(resource).status_code==200,resource
    workflows=list((ROOT/'dify/student').glob('*.yml'))
    assert [p.name for p in workflows]==['student_assistant.yml']
