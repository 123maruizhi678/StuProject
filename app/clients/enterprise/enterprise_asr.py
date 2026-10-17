"""本地音频解码／资源限制与faster-whisper转写，不代替业务确认。"""
from pathlib import Path
import tempfile,threading,os
from app.config import settings
from app.core.enterprise.enterprise_authorization import error

_gate=threading.Lock();_model=None
def transcribe_audio(content,filename):
    if not content or len(content)>20*1024*1024:error(400,'音频须在20MiB以内')
    suffix=Path(filename).suffix.lower()
    if suffix not in {'.wav','.mp3','.m4a','.ogg','.flac','.webm'}:error(400,'不支持此音频文件类型')
    if not _gate.acquire(blocking=False):error(409,'本机转写繁忙，请稍后重试')
    path=None
    try:
        # 本地Anaconda的MKL与CTranslate2使用各自OpenMP运行库；顺序MKL避免重复初始化。
        os.environ.setdefault('MKL_THREADING_LAYER','SEQUENTIAL')
        try:
            import av
            import numpy as np
            from faster_whisper import WhisperModel
        except ImportError:error(503,'本地语音依赖未安装')
        fd,path=tempfile.mkstemp(suffix=suffix,prefix='enterprise-audio-');os.close(fd)
        Path(path).write_bytes(content)
        try:
            with av.open(path) as audio:
                streams=[s for s in audio.streams if s.type=='audio']
                if not streams:error(400,'文件中没有可解码音轨')
                duration=audio.duration/av.time_base if audio.duration else (float(streams[0].duration*streams[0].time_base) if streams[0].duration else None)
                if duration is None or duration<=0 or duration>300:error(400,'音频须为可验证的5分钟以内有效文件')
                samples=0;pcm=[];resampler=av.AudioResampler(format='fltp',layout='mono',rate=16000)
                for frame in audio.decode(streams[0]):
                    if not frame.sample_rate:error(400,'音频采样率无效')
                    samples+=frame.samples/frame.sample_rate
                    if samples>300:error(400,'实际解码音频超过5分钟')
                    for converted in resampler.resample(frame):pcm.append(converted.to_ndarray().reshape(-1))
                for converted in resampler.resample(None):pcm.append(converted.to_ndarray().reshape(-1))
                if samples<=0:error(400,'音频没有有效采样')
                duration=samples
        except Exception as exc:
            from app.core.response import BusinessException
            if isinstance(exc,BusinessException):raise
            error(400,'音频解码失败')
        global _model
        if not settings.ASR_MODEL_PATH or not Path(settings.ASR_MODEL_PATH).is_dir():error(503,'本地语音模型目录未准备')
        try:
            if _model is None:_model=WhisperModel(settings.ASR_MODEL_PATH,device=settings.ASR_DEVICE,compute_type=settings.ASR_COMPUTE_TYPE,local_files_only=True)
            # 统一解码为16kHz单声道PCM，避免重复解码及不同PyAV版本的文件接口差异。
            segments,info=_model.transcribe(np.concatenate(pcm).astype(np.float32),language='zh',vad_filter=True,beam_size=5)
            text=''.join(s.text for s in segments).strip()
        except Exception:error(503,'本地语音模型加载或转写失败')
        return {'text':text,'duration_seconds':duration,'language':info.language,'requires_user_review':True,'business_written':False}
    finally:
        if path:
            try:Path(path).unlink(missing_ok=True)
            except OSError:pass
        _gate.release()
