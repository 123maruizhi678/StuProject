"""只读取本地数据库各表行数，不输出账号口令或业务正文。"""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sqlalchemy import inspect,text
from app.database import engine
from app.config import settings

def main():
    with engine.connect() as conn:
        counts={table:conn.scalar(text('SELECT COUNT(*) FROM `'+table+'`')) for table in inspect(conn).get_table_names()}
    print(json.dumps({'database':settings.DB_NAME,'table_counts':counts},ensure_ascii=False))
if __name__=='__main__':main()
