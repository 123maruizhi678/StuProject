from datetime import datetime,timedelta,timezone
from sqlalchemy import insert,select,update,func
from app.models import common as t
from app.services.student.student_service import events,reminders,warnings,public_time
from app.tasks.student.student_tasks import StudentTasks
from app.core.student.student_auth import Principal
from .test_minimal_units import post,employee,leave_body


def seed_event(unit,student_id=7,lead_minutes=10):
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    with unit.sessions.begin() as db:
        event_id=db.execute(insert(events).values(student_id=student_id,source_system='local',external_event_id='local:event',event_type='exam',title='真实考试节点',due_at=now+timedelta(days=2),source_timezone='Asia/Shanghai',event_status='active',event_version=1,source_updated_at=now,synced_at=None,created_at=now,updated_at=now)).inserted_primary_key[0]
    return event_id


def test_reminder_generation_replan_publish_and_unread(unit):
    eid=seed_event(unit)
    body={'academic_event_id':eid,'lead_minutes':10,'expected_event_version':1}
    first=post(unit,'student/reminders',body)
    assert first['code']==0,first
    assert post(unit,'student/reminders',body)==first
    rid=first['data']['reminder_id']
    old_generation=first['data']['updated_at']
    assert len(old_generation.split('.')[1].rstrip('Z'))==6
    from app.services.student.student_sync import StudentSyncService
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    with unit.sessions.begin() as db:
        db.execute(update(events).where(events.c.id==eid).values(due_at=now+timedelta(minutes=5),event_version=2))
        StudentSyncService(db)._replan(eid,now+timedelta(minutes=5),'active',2)
    worker=StudentTasks(unit.sessions)
    assert worker.prepare()==1
    with unit.sessions() as db:
        row=db.execute(select(reminders)).mappings().one()
        generation=row['updated_at']
        assert generation!=datetime.fromisoformat(old_generation.rstrip('Z'))
    assert worker.dispatch()['sent']==1
    assert worker.dispatch()['sent']==0
    with unit.sessions() as db:
        row=db.execute(select(reminders)).mappings().one()
        assert row['status']=='sent' and row['updated_at']==generation
    listing=unit.client.get('/api/v1/student/notifications?unread=true').json()['data']
    assert listing['total']==listing['unread_count']==1
    nid=listing['items'][0]['notification_id']
    assert unit.client.get(f'/api/v1/student/notifications/{nid}').json()['code']==0
    assert post(unit,f'student/notifications/{nid}/read',{})['code']==0
    assert unit.client.get('/api/v1/student/notifications').json()['data']['unread_count']==0
    # 旧代次取消不能影响新的设置或已发布历史。
    cancel=unit.client.request('DELETE',f'/api/v1/student/reminders/{rid}',json={'expected_event_version':1,'expected_updated_at':old_generation},headers={'Idempotency-Key':'cancel-stale-0001'})
    assert cancel.json()['code']==409


def test_cancel_after_queue_prevents_old_publication(unit):
    eid=seed_event(unit)
    first=post(unit,'student/reminders',{'academic_event_id':eid,'lead_minutes':1,'expected_event_version':1})['data']
    with unit.sessions.begin() as db:
        db.execute(update(reminders).where(reminders.c.id==first['reminder_id']).values(notify_at=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(minutes=1),updated_at=datetime.fromisoformat(first['updated_at'].rstrip('Z'))))
    worker=StudentTasks(unit.sessions)
    assert worker.prepare()==1
    cancel=unit.client.request('DELETE',f'/api/v1/student/reminders/{first["reminder_id"]}',json={'expected_event_version':1,'expected_updated_at':first['updated_at']},headers={'Idempotency-Key':'cancel-before-publish'})
    assert cancel.json()['code']==0,cancel.text
    assert worker.dispatch()['sent']==0


def test_assignment_scope_and_no_automatic_takeover(unit):
    # 学生8无班主任；后台只生成接管待办，绝不伪装人员分派。
    unit.state.actor=Principal('student',8,scopes=unit.state.actor.scopes)
    first=post(unit,'student/leave',leave_body())['data']
    worker=StudentTasks(unit.sessions)
    assert worker.discover_assignments()==1
    with unit.sessions() as db:
        assert db.scalar(select(t.student_admin_service.c.reviewer_id)) is None
    employee(unit,12)
    result=unit.client.get('/api/v1/internal/student/leave/assignments').json()
    assert result['code']==0 and result['data']['total']==1,result
    path=f'internal/student/leave/{first["apply_id"]}/assign'
    denied=post(unit,path,{'expected_version':1,'employee_id':14,'reason':'跨部门'},'assign-denied-0001')
    assert denied['code']==403,denied
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    with unit.sessions.begin() as db:
        db.execute(insert(t.student_staff_binding).values(student_id=8,employee_id=13,relation_type='class_teacher',is_primary=True,valid_from=now-timedelta(days=1)))
    result=post(unit,path,{'expected_version':1,'employee_id':13,'reason':'补充有效主班主任'},'assign-success-0001')
    assert result['code']==0,result
    assert post(unit,path,{'expected_version':1,'employee_id':13,'reason':'补充有效主班主任'},'assign-success-0001')==result
    employee(unit,11)
    assert post(unit,f'internal/student/leave/{first["apply_id"]}/decision',{'decision':'approved','expected_version':2},'wrong-teacher-0001')['code']==404


def test_courses_are_not_inferred_from_scores(unit,tmp_path,monkeypatch):
    from app.config import settings
    import json
    assert unit.client.get('/api/v1/student/courses').json()['code']==503
    file=tmp_path/'courses.json'
    file.write_text(json.dumps({'courses':[{'course_code':'math','course_name':'数学'}],'enrollments':[{'student_id':7,'course_code':'math','term_code':'2026-F','status':'active'},{'student_id':8,'course_code':'math','term_code':'2026-F','status':'active'}]}),encoding='utf-8')
    monkeypatch.setattr(settings,'STUDENT_COURSES_FILE',file)
    result=unit.client.get('/api/v1/student/courses').json()
    assert result['code']==0 and result['data']['total']==1,result
    with unit.sessions.begin() as db:
        for sid,status in [(7,'valid'),(7,'void'),(8,'valid')]:
            db.execute(insert(t.student_score).values(student_id=sid,course_code='math',term_code='2026-F',assessment_code=status,attempt_no=1,score_value=85,max_score=100,employee_id=11,status=status))
    result=unit.client.get('/api/v1/student/scores').json()
    assert result['code']==0 and result['data']['total']==1,result
    assert 'employee_id' not in result['data']['items'][0]


def test_local_academic_maintenance_authorization_and_versions(unit):
    employee(unit,15)
    body={'event_type':'exam','title':'教务维护考试','due_at':'2027-01-20T09:00:00+08:00','source_timezone':'Asia/Shanghai','event_status':'active'}
    first=unit.client.put('/api/v1/internal/student/academic/7',json=body,headers={'Idempotency-Key':'local-academic-0001'}).json()
    assert first['code']==403,first
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    with unit.sessions.begin() as db:
        db.execute(insert(t.student_staff_binding).values(student_id=7,employee_id=15,relation_type='score_editor',is_primary=False,valid_from=now-timedelta(days=1)))
    first=unit.client.put('/api/v1/internal/student/academic/7',json=body,headers={'Idempotency-Key':'local-academic-0001'}).json()
    assert first['code']==0,first
    eid=first['data']['id']
    update_body={**body,'id':eid,'expected_version':1,'title':'教务修订考试'}
    result=unit.client.put('/api/v1/internal/student/academic/7',json=update_body,headers={'Idempotency-Key':'local-academic-0002'}).json()
    assert result['code']==0 and result['data']['event_version']==2,result
    assert unit.client.put('/api/v1/internal/student/academic/7',json=update_body,headers={'Idempotency-Key':'local-academic-0003'}).json()['code']==409
