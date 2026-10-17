"""只读核验学生模块共享表；不改数据库。"""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.database import engine
from app.repositories.student.student_schema import check_student_schema
if __name__=='__main__':
    try:
        with engine.connect() as connection:
            result=[check_student_schema(connection,feature) for feature in ('leave','ticket')]
        print(json.dumps(result,ensure_ascii=False))
        raise SystemExit(0 if all(r['compatible'] for r in result) else 1)
    finally:
        engine.dispose()
