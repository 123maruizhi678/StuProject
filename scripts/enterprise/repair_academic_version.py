"""清理本轮实施新加的冗余列：仅限本机空节点表，保留原event_version。"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sqlalchemy import inspect,text
from app.database import engine
from app.config import settings
if settings.DB_HOST not in ('localhost','127.0.0.1'):raise RuntimeError('仅允许本地库')
with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
    columns={c['name'] for c in inspect(conn).get_columns('student_academic_event')}
    count=conn.scalar(text('SELECT COUNT(*) FROM student_academic_event'))
    if 'row_version' in columns:
        if count:raise RuntimeError('已有节点事实，拒绝自动移除列')
        conn.exec_driver_sql('ALTER TABLE student_academic_event DROP COLUMN row_version')
    print('Academic events use original event_version; verified empty table; no business rows removed.')
