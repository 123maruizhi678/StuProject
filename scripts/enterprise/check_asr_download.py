"""诊断模型下载可达性，只输出状态与数据量，不输出签名URL。"""
import requests,json
for endpoint in ['https://huggingface.co/Systran/faster-whisper-small/resolve/main/model.bin','https://hf-mirror.com/Systran/faster-whisper-small/resolve/main/model.bin']:
    try:
        with requests.get(endpoint,stream=True,timeout=(10,20),headers={'Range':'bytes=0-1023'}) as r:
            block=next(r.iter_content(1024),b'')
            print(json.dumps({'host':endpoint.split('/')[2],'status':r.status_code,'first_chunk_bytes':len(block),'length':r.headers.get('Content-Length')}))
    except Exception as exc:print(json.dumps({'host':endpoint.split('/')[2],'error_type':type(exc).__name__}))
