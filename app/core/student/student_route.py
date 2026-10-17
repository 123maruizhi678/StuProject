"""学生 HTTP 错误信封；仅供学生路由复用，不定义业务接口。"""
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from app.repositories.student.student_schema import StudentSchemaError
from app.core.common.response import BusinessException

class StudentRoute(APIRoute):
    """仅学生路由适配统一错误信封，不修改其他组员的异常处理行为。"""

    def get_route_handler(self):
        original = super().get_route_handler()

        async def handle(request):
            try:
                return await original(request)
            except RequestValidationError as exc:
                details = [
                    {"loc": list(e["loc"]), "type": e["type"]} for e in exc.errors()
                ]
                return JSONResponse(status_code=200, content=
                    {"code": 400, "message": "请求参数不符合要求", "data": details}
                )
            except BusinessException as exc:
                return JSONResponse(status_code=200,content={'code':exc.code,'message':exc.message,'data':None})
            except HTTPException as exc:
                return JSONResponse(status_code=200, content={"code":exc.status_code,"message":"身份或权限不可用","data":None})
            except StudentSchemaError as exc:
                return JSONResponse(status_code=200,content={"code":503,"message":exc.message,"data":None})
            except SQLAlchemyError:
                # 不记录SQL参数和连接异常原文，防止心理原文、密码进入日志。
                return JSONResponse(status_code=200, content=
                    {"code": 503, "message": "学生数据服务暂不可用", "data": None}
                )

            except Exception:
                return JSONResponse(status_code=200, content={"code":500,"message":"学生服务内部错误","data":None})

        return handle
