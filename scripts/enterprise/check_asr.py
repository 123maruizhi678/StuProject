"""本地语音真实加载及转写验收，不写任何业务事实。"""
from pathlib import Path
import os
os.environ.setdefault('MKL_THREADING_LAYER','SEQUENTIAL')
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.config import BASE_DIR
from app.clients.enterprise.enterprise_asr import transcribe_audio
audio=BASE_DIR/'.runtime/asr-sample.wav'
result=transcribe_audio(audio.read_bytes(),audio.name)
assert result['requires_user_review'] and not result['business_written']
assert result['text'].strip(),'语音测试样本未转写出文字'
print(json.dumps(result,ensure_ascii=True))
assert '日报' in result['text'] or '日報' in result['text'],'语音测试样本转写未包含已知词'
(BASE_DIR/'.runtime/enterprise-asr-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
