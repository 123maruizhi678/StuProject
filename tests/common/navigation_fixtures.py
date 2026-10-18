import json,sys
from sqlalchemy import update
from sqlalchemy.orm import Session
from app.models.common import UserAccount,employee
from app.core.common.navigation import account_access,navigation_for
from tests.common.support import make_engine,seed_people
sys.stdout.reconfigure(encoding='utf-8')
engine=make_engine()
with Session(engine) as db:
    seed_people(db,accounts=True)
    fixtures={}
    for name,uid,roles in [('admin',101,None),('teacher',102,['teacher']),('consultant',102,['consultant']),('academic',102,['academic']),('manager',102,['manager']),('counselor',102,['counselor']),('multiple',102,['teacher','consultant']),('employee_admin',102,['admin']),('student',103,None),('customer',104,None)]:
        if roles is not None:
            db.execute(update(employee).where(employee.c.employee_id==10).values(role_codes=roles)); db.commit()
        data=account_access(db,db.get(UserAccount,uid))
        data['display_name']='测试'+name
        fixtures[name]=data
    fixtures['public']={'navigation':navigation_for(set(),None)}
print(json.dumps(fixtures,ensure_ascii=False))
