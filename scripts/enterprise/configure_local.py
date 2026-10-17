"""本机凭据初始化与独立只读授权；不输出真实值，不覆盖已有公共密钥。"""
from pathlib import Path
import sys,json,secrets,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from dotenv import dotenv_values,set_key
from cryptography.fernet import Fernet
from app.config import BASE_DIR,settings
from app.database import engine

def main():
    path=BASE_DIR/'.env.enterprise.local';current={**dotenv_values(BASE_DIR/'.env'),**dotenv_values(path)}
    incoming=json.loads((BASE_DIR/'.env.enterprise-runtime').read_text(encoding='utf-8'))['config']
    generated={}
    for key in ['AUTH_SECRET_KEY','ENTERPRISE_CONFIRM_SECRET','ENTERPRISE_PHONE_LOOKUP_SECRET']:
        if not current.get(key):generated[key]=secrets.token_urlsafe(48)
    if not current.get('ENTERPRISE_PHONE_ENCRYPTION_KEY'):generated['ENTERPRISE_PHONE_ENCRYPTION_KEY']=Fernet.generate_key().decode()
    user=current.get('ENTERPRISE_READ_DB_USER') or 'stu_enterprise_read_'+hashlib.sha256(str(BASE_DIR).encode()).hexdigest()[:6]
    password=current.get('ENTERPRISE_READ_DB_PASSWORD') or secrets.token_urlsafe(32)
    with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
        conn.exec_driver_sql('CREATE USER IF NOT EXISTS %s@\'localhost\' IDENTIFIED BY %s',(user,password))
        columns={
          'customer_profile':['customer_id','full_name','education_level','target_country_code','status','created_at','employee_id','department_id'],
          'customer_followup':['followup_id','customer_id','followup_at','content','followup_status'],
          'employee_daily_report':['daily_report_id','employee_id','report_date','submitted_content','ai_summary','status','department_id_at_submit'],
          'student_score':['student_id','course_code','term_code','score_value','max_score'],
          'service_ticket':['ticket_id','student_id','category_code','status','created_at','resolved_at','closed_at','employee_id','handling_department_id'],
          'student_staff_binding':['binding_id','student_id','employee_id','relation_type','course_scope_code','status','valid_from','valid_to']}
        for table,fields in columns.items():
            conn.exec_driver_sql('GRANT SELECT ('+','.join('`'+f+'`' for f in fields)+') ON `'+settings.DB_NAME+'`.`'+table+'` TO %s@\'localhost\'',(user,))
    generated.update(incoming,ENTERPRISE_READ_DB_USER=user,ENTERPRISE_READ_DB_PASSWORD=password)
    # 本机已有Dify在80端口。只更新API公共地址及本次新应用Key。
    generated['DIFY_API_BASE']='http://127.0.0.1/v1'
    for key,value in generated.items():set_key(str(path),key,value,quote_mode='always')
    print(json.dumps({'configured_names':sorted(generated),'readonly_user':user,'secrets_printed':False}))
if __name__=='__main__':main()
