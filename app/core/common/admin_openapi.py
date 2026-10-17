"""独立生成管理员OpenAPI，不将隐藏路由或Schema加入公共文档。"""
from copy import copy
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

def build_admin_openapi(app):
    from app.api.common.auth import router as auth_router
    from app.api.common.account_registration import router as registration_router
    routes=[]
    # FastAPI新版本延迟挂载include_router；从定义路由复制，避免依赖内部展开类型。
    for router in (auth_router,registration_router):
        for route in router.routes:
            if isinstance(route,APIRoute) and (route.path in ('/auth/login','/auth/me/access','/auth/register') or route.path.startswith('/admin/accounts')):
                duplicate=copy(route);duplicate.include_in_schema=True
                duplicate.path='/api/v1'+route.path;duplicate.path_format='/api/v1'+route.path_format
                routes.append(duplicate)
    schema=get_openapi(title='StuProject 管理员账户接口',version=app.version,routes=routes)
    schema['info']['description']='仅平台admin身份可访问此文档和开户接口。新账户初始密码统一为123456，数据库只保存Argon2哈希。注册时必须提供Idempotency-Key，同一请求重试保持原键。'
    return schema
