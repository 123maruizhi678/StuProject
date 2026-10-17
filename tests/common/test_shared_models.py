"""共享映射的唯一注册、数据库约束及学生结构检查；仅操作隔离 SQLite。"""
from datetime import date, datetime, timedelta
from importlib import import_module

import pytest
from sqlalchemy import BINARY, VARBINARY, Text, create_engine, event, insert, inspect
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable

from app.database import Base
from app.models import common
from app.repositories.student import student_schema
from app.repositories.student.student_schema import check_student_schema


SHARED_TABLES = (
    'student_staff_binding', 'student_score', 'student_admin_service',
    'service_ticket', 'service_ticket_record', 'business_notification',
)


@pytest.fixture
def database():
    engine = create_engine('sqlite://')

    @event.listens_for(engine, 'connect')
    def configure_sqlite(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.create_function('CHAR_LENGTH', 1, lambda value: len(value) if value is not None else None)

    tables = [getattr(common, name).__table__ if name == 'UserAccount' else getattr(common, name)
              for name in common.__all__]
    Base.metadata.create_all(engine, tables=tables)
    with engine.begin() as connection:
        connection.execute(insert(common.org_department).values(
            department_id=1, department_code='TEST', department_name='Test department'))
        connection.execute(insert(common.student_profile).values(
            student_id=1, student_no='S1', full_name='Test student', department_id=1, status='active'))
        connection.execute(insert(common.employee).values(
            employee_id=1, employee_no='E1', full_name='Test teacher', department_id=1,
            login_provider='test', login_subject='teacher', role_codes=['teacher'], joined_date=date(2026, 1, 1)))
        connection.execute(insert(common.service_ticket).values(**ticket_values()))
    try:
        yield engine
    finally:
        engine.dispose()


def ticket_values(**overrides):
    values = dict(ticket_id=1, ticket_no='TEST-1', student_id=1, category_code='teaching',
                  content='Test feedback', handling_department_id=1,
                  response_due_at=datetime(2026, 10, 19), resolution_due_at=datetime(2026, 10, 22))
    return {**values, **overrides}


def leave_values(**overrides):
    start = datetime(2026, 10, 18, 9)
    values = dict(student_id=1, apply_type='leave', apply_content='Test leave',
                  leave_start_at=start, leave_end_at=start + timedelta(hours=1),
                  request_key='test-request', request_hash='a' * 64)
    return {**values, **overrides}


@pytest.mark.parametrize('name', SHARED_TABLES)
def test_shared_table_is_exported_and_registered_once(name):
    table = getattr(common, name)
    assert name in common.__all__
    assert table is getattr(import_module('app.models.common.' + name), name)
    assert table is Base.metadata.tables[name]
    assert table.metadata is Base.metadata


def test_mysql_types_preserve_leave_precision_and_score_scale():
    dialect = mysql.dialect()
    assert common.student_admin_service.c.leave_start_at.type.compile(dialect=dialect) == 'DATETIME(6)'
    assert common.student_admin_service.c.created_at.type.compile(dialect=dialect) == 'DATETIME(3)'
    assert common.student_score.c.score_value.type.compile(dialect=dialect) == 'NUMERIC(8, 2)'
    for name in SHARED_TABLES:
        assert 'ENGINE=InnoDB' in str(CreateTable(getattr(common, name)).compile(dialect=dialect))


@pytest.mark.parametrize('feature', ('leave', 'ticket'))
def test_student_schema_check_accepts_complete_shared_models(database, feature):
    with database.connect() as connection:
        result = check_student_schema(connection, feature)
    assert result['compatible'], result['issues']


def test_student_schema_check_reports_missing_notification_table(database):
    with database.begin() as connection:
        connection.exec_driver_sql('DROP TABLE business_notification')
        result = check_student_schema(connection, 'leave')
    assert not result['compatible']
    assert 'missing_table:business_notification' in result['issues']


@pytest.mark.parametrize('reflected_type,compatible', [
    (BINARY, True), (VARBINARY, True), (Text, False),
])
def test_schema_check_handles_mysql_binary_columns(database, monkeypatch, reflected_type, compatible):
    with database.connect() as connection:
        inspector = inspect(connection)
        original_get_columns = inspector.get_columns
        ciphertext_columns = {
            ('student_profile', 'phone_ciphertext'),
            ('employee', 'work_phone_ciphertext'),
        }

        def mysql_columns(table_name, *args, **kwargs):
            columns = [dict(column) for column in original_get_columns(table_name, *args, **kwargs)]
            for column in columns:
                if (table_name, column['name']) in ciphertext_columns:
                    column['type'] = reflected_type(512)
            return columns

        monkeypatch.setattr(inspector, 'get_columns', mysql_columns)
        monkeypatch.setattr(student_schema, 'inspect', lambda _: inspector)
        for feature in ('leave', 'ticket'):
            result = check_student_schema(connection, feature)
            assert result['compatible'] is compatible, result['issues']
            if not compatible:
                expected = {'column_type:student_profile.phone_ciphertext'}
                if feature == 'leave':
                    expected.add('column_type:employee.work_phone_ciphertext')
                assert set(result['issues']) == expected


@pytest.mark.parametrize('name,values', [
    ('student_staff_binding', dict(student_id=999, employee_id=1, relation_type='class_teacher')),
    ('student_staff_binding', dict(student_id=1, employee_id=1, relation_type='unknown')),
    ('student_score', dict(student_id=1, employee_id=1, course_code='math', term_code='2026',
                          assessment_code='exam', score_value=101, max_score=100)),
    ('student_admin_service', leave_values(leave_end_at=datetime(2026, 10, 18, 8))),
    ('student_admin_service', leave_values(approval_status='approved', reviewer_id=None, reviewed_at=None)),
    ('service_ticket', ticket_values(ticket_id=2, ticket_no='TEST-2', status='closed', solution=None)),
    ('service_ticket_record', dict(ticket_id=1, record_type='reply', employee_id=1, student_id=1,
                                  record_key='invalid-actor')),
    ('business_notification', dict(entity_type='service_ticket', entity_id=1, event_code='test',
                                   employee_id=1, student_id=1, channel='in_app', title='Test',
                                   content='Test notification', dedupe_key='invalid-recipient')),
])
def test_database_rejects_invalid_shared_records(database, name, values):
    with pytest.raises(IntegrityError):
        with database.begin() as connection:
            connection.execute(insert(getattr(common, name)).values(**values))


@pytest.mark.parametrize('name,values', [
    ('student_score', dict(student_id=1, employee_id=1, course_code='math', term_code='2026',
                          assessment_code='exam', score_value=85, max_score=100)),
    ('student_admin_service', leave_values()),
    ('service_ticket_record', dict(ticket_id=1, record_type='reply', student_id=1, record_key='same-record')),
    ('business_notification', dict(entity_type='service_ticket', entity_id=1, event_code='test',
                                   student_id=1, channel='in_app', title='Test',
                                   content='Test notification', dedupe_key='same-notification')),
])
def test_database_rejects_duplicate_business_keys(database, name, values):
    table = getattr(common, name)
    with database.begin() as connection:
        connection.execute(insert(table).values(**values))
    with pytest.raises(IntegrityError):
        with database.begin() as connection:
            connection.execute(insert(table).values(**values))
