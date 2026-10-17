"""公共登录签发的 JWT 直接访问学生接口；使用隔离库和虚构课程。"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.student.student import router
from app.models.common import student_profile
from tests.common.support import AuthCase


class StudentAuthLinkageTests(AuthCase):
    def setUp(self):
        super().setUp()
        self.app.include_router(router)
        self.catalog_dir = TemporaryDirectory()
        self.addCleanup(self.catalog_dir.cleanup)
        catalog = Path(self.catalog_dir.name) / 'courses.json'
        catalog.write_text(json.dumps({
            'courses': [
                {'course_code': 'OWN', 'course_name': 'Own course'},
                {'course_code': 'OTHER', 'course_name': 'Other student course'},
            ],
            'enrollments': [
                {'student_id': 30, 'course_code': 'OWN', 'term_code': '2026'},
                {'student_id': 31, 'course_code': 'OTHER', 'term_code': '2026'},
            ],
        }), encoding='utf-8')
        self.catalog_patch = patch('app.config.settings.STUDENT_COURSES_FILE', catalog)
        self.catalog_patch.start()
        self.addCleanup(self.catalog_patch.stop)

    def login_headers(self, username='student'):
        response = self.client.post('/api/v1/auth/login', json={
            'username': username, 'password': 'test-password-123',
        })
        self.assertEqual(response.status_code, 200)
        token = response.json()['data']['access_token']
        return {'Authorization': 'Bearer ' + token}

    def test_public_login_token_accesses_own_student_courses(self):
        headers = self.login_headers()
        access = self.client.get('/api/v1/auth/me/access', headers=headers)
        self.assertEqual(access.json()['data']['identity_type'], 'student')
        self.assertIn('student.chat', access.json()['data']['permissions'])
        response = self.client.get('/api/v1/student/courses', headers=headers)
        self.assertEqual(response.json()['code'], 0)
        self.assertEqual(response.json()['data']['total'], 1)
        self.assertEqual(response.json()['data']['items'][0]['course_code'], 'OWN')

    def test_query_cannot_select_another_student(self):
        response = self.client.get('/api/v1/student/courses?student_id=31',
                                   headers=self.login_headers())
        self.assertEqual(response.json()['code'], 0)
        self.assertEqual(response.json()['data']['items'][0]['course_code'], 'OWN')

    def test_student_endpoint_rejects_missing_or_invalid_login(self):
        for headers in ({}, {'Authorization': 'Bearer invalid'}):
            with self.subTest(headers_present=bool(headers)):
                response = self.client.get('/api/v1/student/courses', headers=headers)
                self.assertEqual(response.json()['code'], 401)

    def test_other_public_identities_cannot_use_student_endpoint(self):
        for username in ('admin', 'customer'):
            with self.subTest(username=username):
                response = self.client.get('/api/v1/student/courses',
                                           headers=self.login_headers(username))
                self.assertEqual(response.json()['code'], 403)

    def test_archived_student_is_rejected_with_existing_token(self):
        headers = self.login_headers()
        with Session(self.engine) as db:
            db.execute(update(student_profile).where(
                student_profile.c.student_id == 30).values(is_archived=True))
            db.commit()
        response = self.client.get('/api/v1/student/courses', headers=headers)
        self.assertEqual(response.json()['code'], 403)
