"""公共HTTP工具仅传输，不解释工作流业务输出；使用本地mock transport。"""
import unittest
import httpx
from app.core.common.dify import DifyHttpClient


class DifyTransportTests(unittest.TestCase):
    def test_sync_transport_preserves_backend_payload(self):
        def handler(request):
            self.assertEqual(str(request.url),"http://dify.test/v1/workflows/run")
            self.assertEqual(request.headers["authorization"],"Bearer app-test")
            self.assertEqual(request.method,"POST")
            return httpx.Response(200,json={"data":{"status":"failed","outputs":{}}})
        result=DifyHttpClient("http://dify.test/v1",transport=httpx.MockTransport(handler)).post_json_sync(
            "/workflows/run",api_key="app-test",payload={"inputs":{"query":"hello"}})
        self.assertEqual(result["data"]["status"],"failed")

    def test_non_json_object_is_rejected(self):
        client=DifyHttpClient("http://dify.test/v1",transport=httpx.MockTransport(
            lambda request:httpx.Response(200,json=["unexpected"])))
        with self.assertRaises(ValueError):
            client.post_json_sync("/workflows/run",api_key="app-test",payload={})

    def test_redirect_is_not_followed(self):
        calls=[]
        def handler(request):
            calls.append(request)
            return httpx.Response(302,headers={"Location":"http://other.test/"})
        client=DifyHttpClient("http://dify.test/v1",transport=httpx.MockTransport(handler))
        with self.assertRaises(httpx.HTTPStatusError):
            client.post_json_sync("/workflows/run",api_key="app-test",payload={})
        self.assertEqual(len(calls),1)


class AsyncDifyTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_transport(self):
        client=DifyHttpClient("http://dify.test/v1",async_transport=httpx.MockTransport(
            lambda request:httpx.Response(200,json={"data":{"status":"succeeded"}})))
        result=await client.post_json("/workflows/run",api_key="app-test",payload={"inputs":{}})
        self.assertEqual(result["data"]["status"],"succeeded")
