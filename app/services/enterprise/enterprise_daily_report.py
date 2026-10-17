"""首次日期和部门快照冻结；修订／作废不移动归属。"""
from datetime import datetime,date
from zoneinfo import ZoneInfo
from sqlalchemy import insert
from app.models.enterprise import employee_daily_report as table
from app.core.enterprise.enterprise_authorization import error
from app.repositories.enterprise.enterprise_repository import public

class DailyReportService:
    def __init__(self,repo):self.repo=repo
    def mutate(self,verb,key,params,report_id=None):
        self.repo.ctx.require('daily.write_own')
        def own(lock=False):
            row=self.repo.one('daily',report_id,lock=lock)
            if row['employee_id']!=self.repo.ctx.employee_id and not self.repo.ctx.is_admin:error(403,'仅作者可以修改本人日报')
            return row
        def work():
            ctx=self.repo.ctx;now=datetime.utcnow()
            if verb=='create':
                if params['report_date']>datetime.now(ZoneInfo('Asia/Shanghai')).date():error(400,'不能提交未来日期日报')
                values={**params,'employee_id':ctx.employee_id,'department_id_at_submit':ctx.department_id,'submitted_at':now,'status':'submitted','row_version':1,'created_at':now,'updated_at':now}
                rid=self.repo.db.execute(insert(table).values(**values)).inserted_primary_key[0]
                return public({**values,'daily_report_id':rid}),None,'employee_daily_report',rid
            row=own(True)
            if row['status']!='submitted':error(409,'作废日报不可直接恢复或修订')
            if verb=='void' and not params.get('reason'):error(400,'作废原因必填')
            values={'status':'void'} if verb=='void' else {'submitted_content':params['submitted_content'],'ai_summary':None}
            result=self.repo.version_update('daily',row,params.get('expected_version'),values)
            return public(result),row,'employee_daily_report',report_id
        return self.repo.operation('enterprise.daily.write_own',key,{'verb':verb,'id':report_id,**params},work,lambda:own() if report_id else None)
