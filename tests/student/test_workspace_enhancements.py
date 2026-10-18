"""Student-only additions on the current main authentication and shared models."""
from datetime import timedelta
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, update
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.main import app
from app.models import common as t
from app.models.student.student_conversation import sessions, turns
from app.models.student.student_types import utcnow
from app.core.student.student_auth import verify_token
from app.services.common.auth_service import create_access_token
from tests.common.support import make_engine, seed_people, TEST_SECRET

@pytest.fixture
def workspace():
    engine=make_engine()
    sessions.create(engine);turns.create(engine)
    original=app.dependency_overrides.copy()
    def database():
        with Session(engine) as db:yield db
    app.dependency_overrides[get_db]=database
    with Session(engine) as db:
        seed_people(db,accounts=True)
        db.execute(insert(t.student_profile).values(student_id=2,student_no='OTHER',full_name='Other student',department_id=7,status='active'));db.commit()
    with patch.object(settings,'AUTH_SECRET_KEY',TEST_SECRET),patch.object(settings,'STUDENT_ACTION_SECRET','student-history-signature-test-'*3):
        with Session(engine) as db:token=create_access_token(db.get(t.UserAccount,103))[0]
        with TestClient(app) as client:yield client,engine,{'Authorization':'Bearer '+token}
    app.dependency_overrides.clear();app.dependency_overrides.update(original);engine.dispose()

def seed(engine,student=1,count=3,pending=False):
    now=utcnow();sid='history-'+str(student)
    with Session(engine) as db:
        db.execute(insert(sessions).values(session_id=sid,student_id=student,version=count,created_at=now,updated_at=now))
        for i in range(count):
            result=None if pending and i==count-1 else {'answer':'reply-'+str(i),'pending_action':{'action_token':'never-expose-old-action'},'conversation_token':'old-token'}
            db.execute(insert(turns).values(session_id=sid,student_id=student,request_key=f'{student}-{i}',parameters_hash='hash',message='message-'+str(i),result=result,created_at=now+timedelta(seconds=i)))
        db.commit()
    return sid

def test_history_owner_pagination_and_fresh_continuation(workspace):
    client,engine,headers=workspace;sid=seed(engine,count=25);seed(engine,student=2)
    listing=client.get('/api/v1/student/chat/sessions',headers=headers).json()['data']
    assert listing['total']==1 and listing['items'][0]['session_id']==sid
    result=client.get(f'/api/v1/student/chat/sessions/{sid}',headers=headers).json()['data']
    assert len(result['items'])==20 and result['items'][0]['message']=='message-5'
    assert 'never-expose-old-action' not in str(result) and 'old-token' not in str(result)
    claims=verify_token(result['conversation_token'],'student-conversation')
    assert claims['subject']=='student:1' and claims['version']==25
    older=client.get(f'/api/v1/student/chat/sessions/{sid}?offset=20',headers=headers).json()['data']
    assert len(older['items'])==5 and older['items'][0]['message']=='message-0'
    assert client.get('/api/v1/student/chat/sessions/history-2',headers=headers).json()['code']==404

def test_pending_history_blocks_until_result_is_known(workspace):
    client,engine,headers=workspace;sid=seed(engine,pending=True)
    result=client.get(f'/api/v1/student/chat/sessions/{sid}',headers=headers).json()['data']
    assert result['blocked'] is True and result['conversation_token'] is None
    with Session(engine) as db:
        db.execute(update(turns).where(turns.c.session_id==sid,turns.c.result.is_(None)).values(result={'answer':'verified'}));db.commit()
    result=client.get(f'/api/v1/student/chat/sessions/{sid}',headers=headers).json()['data']
    assert result['blocked'] is False and result['conversation_token']

def test_profile_uses_current_own_name_and_minimal_fields(workspace):
    client,engine,headers=workspace
    result=client.get('/api/v1/student/profile',headers=headers).json()['data']
    assert set(result)=={'student_id','student_no','full_name'} and result['student_id']==1
    with Session(engine) as db:
        db.execute(update(t.student_profile).where(t.student_profile.c.student_id==1).values(full_name='Updated name'));db.commit()
    assert client.get('/api/v1/student/profile',headers=headers).json()['data']['full_name']=='Updated name'

def test_new_routes_require_student_login_and_valid_pagination(workspace):
    client,engine,headers=workspace
    assert client.get('/api/v1/student/chat/sessions').json()['code']==401
    assert client.get('/api/v1/student/chat/sessions?limit=0',headers=headers).json()['code']==400
    with Session(engine) as db:token=create_access_token(db.get(t.UserAccount,102))[0]
    for route in ['profile','chat/sessions','chat/sessions/nonexistent']:
        assert client.get('/api/v1/student/'+route,headers={'Authorization':'Bearer '+token}).json()['code']==403
