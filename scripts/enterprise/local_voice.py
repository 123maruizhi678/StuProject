"""Local-only transcription bridge; business permissions come from the configured backend."""
import importlib.util
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
for directory in (ROOT, ROOT / '.runtime/backend-deps', ROOT / '.runtime/asr-deps'):
    sys.path.insert(0, str(directory))
os.environ.setdefault('ASR_MODEL_PATH', str(ROOT / '.runtime/models/faster-whisper-base'))
os.environ.setdefault('ASR_DEVICE', 'cpu')
os.environ.setdefault('ASR_COMPUTE_TYPE', 'int8')

import httpx
from fastapi import FastAPI, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from app.core.common.response import BusinessException, fail, success

MAX_AUDIO = 20 * 1024 * 1024


class UploadTooLarge(Exception):
    pass


class LimitUpload:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        size = 0

        async def bounded_receive():
            nonlocal size
            message = await receive()
            size += len(message.get('body', b''))
            if size > MAX_AUDIO + 65536:
                raise UploadTooLarge()
            return message

        try:
            await self.app(scope, bounded_receive, send)
        except UploadTooLarge:
            await JSONResponse(fail(400, '音频须在20MiB以内'))(scope, receive, send)


def create_app(*, backend_url=None, transcriber=None, transport=None):
    backend = (backend_url or os.getenv('STUPROJECT_BACKEND_URL', 'http://192.168.5.12:8000')).rstrip('/')
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(LimitUpload)

    @app.exception_handler(BusinessException)
    async def business_error(request, exc):
        return JSONResponse(fail(exc.code, exc.message))

    @app.get('/local-voice-health')
    async def health():
        model = Path(os.environ['ASR_MODEL_PATH'])
        ready = all((model / name).is_file() for name in ('model.bin', 'config.json', 'tokenizer.json'))
        ready = ready and any((model / name).is_file() for name in ('vocabulary.txt', 'vocabulary.json'))
        ready = ready and all(importlib.util.find_spec(name) is not None for name in ('av', 'numpy', 'faster_whisper'))
        return success({'service': 'StuProject-local-voice', 'ready': ready, 'offline': True})

    @app.post('/api/v1/enterprise/voice/transcribe')
    async def transcribe(request: Request):
        authorization = request.headers.get('authorization', '')
        if not authorization.lower().startswith('bearer ') or not authorization[7:].strip():
            return fail(401, '请先登录后使用语音输入')
        # Validate the same session against the business backend on EVERY request.
        # No local account mapping, cached permissions, or admin flag shortcuts.
        try:
            async with httpx.AsyncClient(timeout=8, trust_env=False, transport=transport) as client:
                response = await client.get(backend + '/api/v1/enterprise/me/permissions', headers={'Authorization': authorization})
            if response.status_code in (401, 403):
                return fail(response.status_code, '登录已失效或没有语音输入权限')
            response.raise_for_status()
            envelope = response.json()
            if envelope.get('code') != 0:
                code = envelope.get('code')
                return fail(code if code in (401, 403) else 503, '登录已失效或无法核实当前账号权限')
            permissions = (envelope.get('data') or {}).get('permissions', [])
            if not isinstance(permissions, list) or 'enterprise.command' not in permissions:
                return fail(403, '当前账号没有语音输入权限')
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            return fail(503, '无法连接业务后端核实账号权限，请稍后重试')

        try:
            async with request.form(max_files=1, max_fields=0) as form:
                file = form.get('file')
                if file is None or not hasattr(file, 'read'):
                    return fail(400, '请选择有效录音')
                content = await file.read(MAX_AUDIO + 1)
                if not content or len(content) > MAX_AUDIO:
                    return fail(400, '音频须在20MiB以内')
                filename = file.filename or 'audio'
        except UploadTooLarge:
            return fail(400, '音频须在20MiB以内')
        except Exception:
            return fail(400, '录音文件无效')
        engine = transcriber
        if engine is None:
            from app.clients.enterprise.enterprise_asr import transcribe_audio
            engine = transcribe_audio
        try:
            return success(await run_in_threadpool(engine, content, filename))
        except BusinessException:
            raise
        except Exception:
            return fail(503, '本地语音识别暂不可用，请稍后重试')

    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(create_app(), host='127.0.0.1', port=8011)
