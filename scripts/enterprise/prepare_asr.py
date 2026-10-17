"""下载本地small语音模型；运行时不访问云端转写。"""
from pathlib import Path
import sys,json,os
os.environ.setdefault('HF_HUB_DISABLE_XET','1')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.config import BASE_DIR
from huggingface_hub import snapshot_download
from dotenv import set_key

def main():
    folder=BASE_DIR/'.runtime/models/faster-whisper-small'
    snapshot_download('Systran/faster-whisper-small',local_dir=str(folder),allow_patterns=['model.bin','config.json','tokenizer.json','vocabulary.txt','preprocessor_config.json'])
    set_key(str(BASE_DIR/'.env.enterprise.local'),'ASR_MODEL_PATH',str(folder))
    print(json.dumps({'model':'small','local_path':str(folder),'ready':True}))
if __name__=='__main__':main()
