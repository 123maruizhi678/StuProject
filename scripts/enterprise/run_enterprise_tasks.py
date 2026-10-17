"""运行企业任务，默认单次；--watch每5分钟扫描，可并行进程安全领取。"""
from pathlib import Path
import sys,time,argparse,json
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.database import SessionLocal
from app.tasks.enterprise.enterprise_tasks import scan,publish_one
from app.config import settings
def main():
    p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');a=p.parse_args()
    while True:
        try:
            with SessionLocal() as db:
                scanned=scan(db);published=0
                for _ in range(100):
                    if not publish_one(db):break
                    published+=1
                print(json.dumps({'scan_candidates':scanned,'publish_processed':published}),flush=True)
        except Exception as exc:
            if not a.watch:raise
            print(json.dumps({'task_error_type':type(exc).__name__,'retry_next_scan':True}),flush=True)
        if not a.watch:break
        time.sleep(settings.ENTERPRISE_TASK_INTERVAL_SECONDS)
if __name__=='__main__':main()
