"""The local recognizer must use the REMOTE session and never write business data."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.enterprise.local_voice import create_app, MAX_AUDIO
import httpx
from fastapi.testclient import TestClient


class VoiceBridgeTest(unittest.TestCase):
    def setUp(self):
        self.auth_requests = []
        self.engine_calls = []
        self.remote = {'code': 0, 'data': {'permissions': ['enterprise.command']}}
        self.remote_status = 200

        def authorize(request):
            self.auth_requests.append((request.method, str(request.url), request.headers.get('authorization')))
            return httpx.Response(self.remote_status, json=self.remote)

        def engine(content, filename):
            self.engine_calls.append((len(content), filename))
            return {'text': '怎么请假', 'requires_user_review': True, 'business_written': False}

        self.client = TestClient(create_app(backend_url='http://remote.test:8000', transcriber=engine, transport=httpx.MockTransport(authorize)))
        self.headers = {'Authorization': 'Bearer remote-session-only'}

    def upload(self, content=b'audio'):
        return self.client.post('/api/v1/enterprise/voice/transcribe', headers=self.headers, files={'file': ('voice.webm', content, 'audio/webm')}).json()

    def test_authenticates_remote_session_on_each_request(self):
        for _ in range(2):
            response = self.upload()
            self.assertEqual(response['code'], 0)
            self.assertFalse(response['data']['business_written'])
        self.assertEqual(self.auth_requests, [('GET', 'http://remote.test:8000/api/v1/enterprise/me/permissions', 'Bearer remote-session-only')] * 2)
        self.assertEqual(len(self.engine_calls), 2)

    def test_no_session_no_recognition(self):
        self.headers = {}
        self.assertEqual(self.upload()['code'], 401)
        self.assertFalse(self.auth_requests)
        self.assertFalse(self.engine_calls)

    def test_expired_session_and_revoked_permission(self):
        self.remote = {'code': 401}
        self.assertEqual(self.upload()['code'], 401)
        self.remote = {'code': 0, 'data': {'is_admin': True, 'permissions': []}}
        self.assertEqual(self.upload()['code'], 403)
        self.remote_status = 403
        self.assertEqual(self.upload()['code'], 403)
        self.assertFalse(self.engine_calls)

    def test_remote_failure_does_not_use_local_identity(self):
        self.remote_status = 503
        self.assertEqual(self.upload()['code'], 503)
        self.assertFalse(self.engine_calls)

    def test_invalid_and_oversized_audio(self):
        self.assertEqual(self.upload(b'')['code'], 400)
        self.assertEqual(self.upload(b'x' * (MAX_AUDIO + 1))['code'], 400)
        self.assertEqual(self.upload(b'x' * (MAX_AUDIO + 65537))['code'], 400)
        self.assertFalse(self.engine_calls)


if __name__ == '__main__':
    unittest.main()
