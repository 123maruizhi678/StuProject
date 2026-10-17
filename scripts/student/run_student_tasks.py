"""五分钟补扫；不自动启用外部同步，不重复调用未知模型请求。"""
from pathlib import Path
import argparse,sys,time,json
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--pending-models',action='store_true')
    args=parser.parse_args()
    from app.database import SessionLocal
    from app.tasks.student.student_tasks import StudentTasks
    from app.services.student.student_policy import SCAN_SECONDS
    from sqlalchemy.exc import SQLAlchemyError
    worker=StudentTasks(SessionLocal)
    if args.pending_models:
        print(json.dumps(worker.pending_model_results(),default=str,ensure_ascii=False))
        raise SystemExit(0)
    try:
        while True:
            try:
                print(json.dumps(worker.run_once(),ensure_ascii=False),flush=True)
            except SQLAlchemyError:
                print('数据库依赖未就绪，本轮未完成；未执行重建或清理。',flush=True)
                if args.once:raise SystemExit(1)
            if args.once:break
            time.sleep(SCAN_SECONDS)
    except KeyboardInterrupt:
        pass
