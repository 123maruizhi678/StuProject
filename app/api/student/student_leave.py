"""最小单元兼容工厂；生产统一路由只注册一次。"""
from fastapi import APIRouter, Depends, Header
from app.api.student.student import StudentRoute
from app.schemas.student.student_leave import LeaveInput
from app.services.student.student_leave_service import StudentLeaveService, LeaveError
from app.clients.student.student_assistant_dify import get_leave_workflow
from app.core.common.response import BusinessException,success

def create_router(account_dependency, db_dependency, workflow_dependency=get_leave_workflow):
    router=APIRouter(prefix='/student',route_class=StudentRoute)
    @router.post('/leave')
    def submit_leave(payload:LeaveInput,request_key:str=Header(alias='Idempotency-Key',min_length=8,max_length=128,pattern=r'^[!-~]{8,128}$'),account=Depends(account_dependency),db=Depends(db_dependency),workflow=Depends(workflow_dependency)):
        try:
            return success(StudentLeaveService(db,workflow).submit(account,request_key,payload))
        except LeaveError as exc:
            raise BusinessException(exc.message,exc.status) from None
    return router
