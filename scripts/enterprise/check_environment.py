"""只输出运行状态和结构，不打印环境密钥。"""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sqlalchemy import inspect,text
from app.database import engine
from app.config import settings
def main():
    with engine.connect() as conn:
        i=inspect(conn)
        result={'database':settings.DB_NAME,'version':conn.scalar(text('SELECT VERSION()')),'tables':i.get_table_names(),
                'config_present':{k:bool(getattr(settings,k,'')) for k in ['AUTH_SECRET_KEY','REPORT_DIFY_API_KEY']}}
        result['columns']={n:[c['name'] for c in i.get_columns(n)] for n in ['business_notification','customer_followup','service_ticket_record','mental_warning'] if i.has_table(n)}
        print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__': main()
