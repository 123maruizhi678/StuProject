"""真实隔离数据库事务；测试替身只替换外部模型，不替换业务服务。"""
from datetime import datetime, timedelta, date, timezone
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, insert
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.models import common as t
from app.models.student.student import STUDENT_TABLES
from app.models.student.student_conversation import sessions, turns
from app.core.student.student_auth import Principal, get_principal
from app.core.common.authorization import permissions_for
from app.config import settings
from app.api.student.student import router, internal_router


@pytest.fixture
def unit(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "student.sqlite"}')
    @event.listens_for(engine, 'connect')
    def foreign_keys(conn, _):
        conn.execute('PRAGMA foreign_keys=ON')
        conn.create_function('JSON_LENGTH', 1, lambda x: len(__import__('json').loads(x)))
        conn.create_function('CHAR_LENGTH', 1, lambda x:len(x) if x is not None else None)
    # MySQL JSON_TYPE 返回 ARRAY；SQLite json_type 返回 array。
    @event.listens_for(engine, 'connect')
    def json_type(conn, _):
        conn.create_function('JSON_TYPE',1,lambda x:'ARRAY' if isinstance(__import__('json').loads(x),list) else 'OBJECT')
    tables = [t.UserAccount.__table__] + [getattr(t,n) for n in t.__all__ if n!='UserAccount'] + list(STUDENT_TABLES) + [sessions,turns]
    Base.metadata.create_all(engine,tables=tables)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    with factory.begin() as db:
        for d in (5,6):
            db.execute(insert(t.org_department).values(department_id=d,department_code=f'd{d}',department_name=f'部门{d}'))
        for sid in (7,8):
            db.execute(insert(t.student_profile).values(student_id=sid,student_no=f's{sid}',full_name=f'学生{sid}',department_id=5,status='active'))
        for eid,roles in [(11,['teacher']),(12,['manager']),(13,['teacher']),(14,['teacher']),(15,['academic']),(16,['consultant'])]:
            db.execute(insert(t.employee).values(employee_id=eid,employee_no=f'e{eid}',full_name=f'员工{eid}',department_id=6 if eid==14 else 5,login_provider='test',login_subject=str(eid),role_codes=roles,joined_date=date(2020,1,1)))
        db.execute(insert(t.student_staff_binding).values(binding_id=1,student_id=7,employee_id=11,relation_type='class_teacher',is_primary=True,valid_from=now-timedelta(days=1)))
    monkeypatch.setattr(settings,'STUDENT_DIFY_KEY',__import__('pydantic').SecretStr(''))
    monkeypatch.setattr(settings,'STUDENT_ACTION_SECRET','test-only-action-secret-'*3)
    monkeypatch.setattr(settings,'STUDENT_KNOWLEDGE_FILE',tmp_path/'no-knowledge.json')
    monkeypatch.setattr(settings,'STUDENT_COURSES_FILE',tmp_path/'no-courses.json')
    app=FastAPI()
    app.include_router(router)
    app.include_router(internal_router)
    state=SimpleNamespace(actor=Principal('student',7,scopes=tuple(permissions_for('student'))))
    def database():
        with factory() as db:
            try:
                yield db
            finally:
                db.rollback()
    app.dependency_overrides[get_db]=database
    app.dependency_overrides[get_principal]=lambda:state.actor
    with TestClient(app,raise_server_exceptions=True) as client:
        yield SimpleNamespace(app=app,client=client,sessions=factory,engine=engine,state=state)
    engine.dispose()
