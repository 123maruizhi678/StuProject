from datetime import datetime, timedelta, timezone
from sqlalchemy import select, insert, update, func
from app.models import common as t
from app.core.student.student_auth import Principal
from app.core.student.student_permissions import employee_permissions


def post(unit,path,body,key='student-test-0001'):
    response=unit.client.post('/api/v1/'+path,json=body,headers={'Idempotency-Key':key})
    assert response.status_code==200
    return response.json()


def leave_body():
    return {'leave_content':'事假','leave_type':'personal','leave_start_at':'2027-01-20T09:00:00+08:00','leave_end_at':'2027-01-20T18:00:00+08:00'}


def employee(unit,eid):
    with unit.sessions() as db:
        perms=employee_permissions(db,eid)
    unit.state.actor=Principal('employee',eid,scopes=tuple(perms))


def test_leave_submit_replay_and_unique_shared_mapping(unit):
    first=post(unit,'student/leave',leave_body())
    assert first['code']==0,first
    assert first['data']['reviewer_id']==11
    assert post(unit,'student/leave',leave_body())==first
    assert post(unit,'student/leave',{**leave_body(),'leave_content':'另一条'})['code']==409
    with unit.sessions() as db:
        for table in (t.student_admin_service,t.operation_log,t.business_notification):
            assert db.scalar(select(func.count()).select_from(table))==1
        from app.database import Base
        assert Base.metadata.tables["student_profile"] is t.student_profile


def test_leave_approval_uses_real_columns_and_operator(unit):
    first=post(unit,'student/leave',leave_body())['data']
    employee(unit,11)
    path=f'internal/student/leave/{first["apply_id"]}/decision'
    result=post(unit,path,{'decision':'approved','comment':'同意','expected_version':1},'decision-0001')
    assert result['code']==0,result
    assert post(unit,path,{'decision':'approved','comment':'同意','expected_version':1},'decision-0001')==result
    with unit.sessions() as db:
        row=db.execute(select(t.student_admin_service)).mappings().one()
        assert row['reviewed_at'] and row['approval_comment']=='同意'
        audit=db.execute(select(t.operation_log).where(t.operation_log.c.action_code=='leave.decide')).mappings().one()
        assert audit['employee_id']==11


def test_leave_cancel_and_foreign_ownership(unit):
    first=post(unit,'student/leave',leave_body())['data']
    path=f'/api/v1/student/leave/{first["apply_id"]}'
    response=unit.client.request('DELETE',path,json={'expected_version':1},headers={'Idempotency-Key':'cancel-0001'})
    assert response.json()['data']['approval_status']=='cancelled'
    unit.state.actor=Principal('student',8,scopes=unit.state.actor.scopes)
    assert unit.client.get(path).json()['code']==404


def test_complaint_minimal_unit_and_pagination(unit):
    first=post(unit,'student/complaint',{'content':'希望调整课程安排','ticket_type':'suggestion'})
    assert first['code']==0,first
    assert post(unit,'student/complaint',{'content':'希望调整课程安排','ticket_type':'suggestion'})==first
    rows=unit.client.get('/api/v1/student/tickets?limit=1&offset=0').json()
    assert rows['code']==0,rows
    assert rows['data']['total']==1
    tid=first['data']['ticket_id']
    records=unit.client.get(f'/api/v1/student/tickets/{tid}/records').json()['data']['items']
    assert len(records)==1 and records[0]['visibility']=='student_visible'


def test_validation_and_auth_envelope(unit):
    assert post(unit,'student/leave',{**leave_body(),'student_id':8})['code']==400
    result=unit.client.post('/api/v1/student/leave',json=leave_body(),headers={'Idempotency-Key':'short'})
    assert result.status_code==200 and result.json()['code']==400
    from app.core.student.student_auth import get_principal
    unit.app.dependency_overrides.pop(get_principal)
    result=unit.client.get('/api/v1/student/leave')
    assert result.status_code==200 and result.json()['code']==401


def test_actual_application_has_unique_student_operations():
    from app.main import app
    methods={'get','post','put','delete','patch'}
    operations=[(path,method) for path,value in app.openapi()['paths'].items() for method in value if method in methods and path.startswith(('/api/v1/student/','/api/v1/internal/student/'))]
    assert len(operations)==len(set(operations))
    assert sum(p.startswith('/api/v1/student/') for p,m in operations)==24
    assert sum(p.startswith('/api/v1/internal/student/') for p,m in operations)==19
