"""将本次真实运行值迁到Git忽略的覆盖文件；保留用户其他.env改动。"""
from pathlib import Path
import sys,subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from dotenv import dotenv_values,set_key
from app.config import BASE_DIR
names={'DIFY_API_BASE','AUTH_SECRET_KEY','ENTERPRISE_CONFIRM_SECRET','ENTERPRISE_PHONE_LOOKUP_SECRET','ENTERPRISE_PHONE_ENCRYPTION_KEY','ENTERPRISE_READ_DB_USER','ENTERPRISE_READ_DB_PASSWORD','ENTERPRISE_EXTRACT_DIFY_API_KEY','ENTERPRISE_NL2SQL_DIFY_API_KEY','ENTERPRISE_KNOWLEDGE_DIFY_API_KEY','ENTERPRISE_SUMMARY_DIFY_API_KEY','ASR_MODEL_PATH'}
path=BASE_DIR/'.env';runtime=BASE_DIR/'.env.enterprise.local';current=dotenv_values(path)
original=subprocess.run(['git','show','HEAD:.env'],cwd=BASE_DIR,capture_output=True,check=True).stdout.decode('utf-8')
def name(line):return line.split('=',1)[0].strip() if '=' in line and not line.lstrip().startswith('#') else None
original_lines={name(line):line for line in original.splitlines() if name(line) in names}
for key in names:
    if current.get(key):set_key(str(runtime),key,current[key])
lines=[]
for line in path.read_text(encoding='utf-8').splitlines():
    key=name(line)
    if key not in names:lines.append(line)
    elif key in original_lines:lines.append(original_lines[key])
result='\n'.join(lines).rstrip()+'\n'
if result.rstrip()==original.rstrip():result=original
path.write_text(result,encoding='utf-8',newline='')
print('Enterprise runtime values moved to ignored .env.enterprise.local; values not printed.')
