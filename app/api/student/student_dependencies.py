"""学生接口依赖与受控查询入口；业务规则由 services 承担。"""
from fastapi import Depends
from app.database import get_db
from app.core.common.response import success
from app.services.student.student_service import StudentService

def get_service(db=Depends(get_db)):
    return StudentService(db)


def read_scene(scene, actor, service, query, entity_id=None, limit=20, offset=0, approval_status=None):
    service.student(actor)
    result=query.query(actor,scene,entity_id=entity_id,limit=limit,offset=offset,approval_status=approval_status)
    return success(result['items'][0] if entity_id is not None and scene in ('leave','tickets') else result)
