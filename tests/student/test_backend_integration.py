"""Regressions for mounting, shared education facts, and unconfigured AI preflight."""
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import insert, select, func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import common as t
from app.models.enterprise import enterprise_course, enterprise_student_course
from app.models.student.student import StudentAcademicEvent, StudentAcademicReminder, StudentApplicationProgress
from app.core.student.student_auth import Principal
from app.services.student.student_local_query import LocalStudentQueryClient
from app.services.common.auth_service import create_access_token
from tests.common.support import make_engine, seed_people, TEST_SECRET


def test_student_and_enterprise_use_same_education_tables():
    assert StudentAcademicEvent.__table__ is t.student_academic_event
    assert StudentAcademicReminder.__table__ is t.student_academic_reminder
    assert StudentApplicationProgress.__table__ is t.student_application_progress


def test_student_reads_only_own_active_database_enrollments():
    engine=make_engine()
    try:
        enterprise_course.create(engine)
        enterprise_student_course.create(engine)
        with Session(engine) as db:
            seed_people(db)
            db.execute(insert(t.student_profile).values(student_id=2,student_no='OTHER',full_name='另一学生',department_id=7,status='active'))
            for code,status in [('VISIBLE','active'),('HIDDEN','disabled')]:
                db.execute(insert(enterprise_course).values(course_code=code,course_name=code,status=status))
            for student,course,status in [(1,'VISIBLE','active'),(2,'VISIBLE','active'),(1,'HIDDEN','active'),(1,'VISIBLE','disabled')]:
                db.execute(insert(enterprise_student_course).values(student_id=student,course_code=course,term_code='T'+status,status=status))
            db.commit()
            data=LocalStudentQueryClient(db).query(Principal('student',1),'courses')
            assert data['total']==1
            assert [row['course_code'] for row in data['items']]==['VISIBLE']
    finally:engine.dispose()


def test_missing_student_workflow_does_not_reserve_unknown_model_operation():
    engine=make_engine()
    original=app.dependency_overrides.copy()
    def database():
        with Session(engine) as db:yield db
    try:
        with Session(engine) as db:seed_people(db,accounts=True)
        app.dependency_overrides[get_db]=database
        with patch.object(settings,'AUTH_SECRET_KEY',TEST_SECRET),patch.object(settings,'STUDENT_DIFY_KEY',SecretStr('')):
            with Session(engine) as db:token=create_access_token(db.get(t.UserAccount,103))[0]
            with TestClient(app) as client:
                response=client.post('/api/v1/student/mental/monitor',json={'chat_content':'测试缺少配置'},
                    headers={'Authorization':'Bearer '+token,'Idempotency-Key':'missing-config-test'})
                assert response.json()['code']==503
            with Session(engine) as db:
                assert db.scalar(select(func.count()).select_from(t.operation_log))==0
    finally:
        app.dependency_overrides.clear();app.dependency_overrides.update(original);engine.dispose()
