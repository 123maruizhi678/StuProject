"""公共导航汇总既有业务授权；不替代业务接口及其数据范围校验。"""
from app.core.common.authorization import access_for, load_access_control


def navigation_for(permissions: set[str], identity_type: str | None) -> dict:
    catalog = load_access_control().get("navigation", {})
    routes = {}
    for page in catalog.get("pages", []):
        if page.get("identities") and identity_type not in page["identities"]:
            continue
        if page.get("authenticated", True) and identity_type is None:
            continue
        if page.get("any_permissions") and not permissions.intersection(page["any_permissions"]):
            continue
        routes[page["route"]] = {key: value for key, value in page.items()
                                 if key in ("title", "module", "menu")}
    modules = []
    for module in catalog.get("modules", []):
        pages = [{"route": route, **page} for route, page in routes.items()
                 if page.get("module") == module["id"] and page.get("menu", True)]
        if pages:
            modules.append({**module, "entry": pages[0]["route"], "pages": pages})
    return {"modules": modules, "routes": routes}


def account_access(db, account) -> dict:
    # 从数据库和业务现有授权器读取岗位，不信任客户端提交的角色。
    roles, extra = [], set()
    if account.identity_type in ("admin", "employee"):
        from app.core.enterprise.enterprise_authorization import context_for
        context = context_for(db, account)
        roles = sorted(context.roles)
        extra.update(context.permissions())
        if account.identity_type == "employee":
            from app.core.student.student_permissions import employee_permissions
            extra.update(employee_permissions(db, account.employee_id))
        from app.core.common.system_admin import is_system_admin
        if is_system_admin(db, account):
            extra.add("common.accounts.manage")
        if account.identity_type == "employee" and "manager" in context.roles:
            from app.core.common.research_access import RESEARCH_READ
            from app.core.report.report_auth import resolve_report_access
            extra.update(RESEARCH_READ)
            extra.update(resolve_report_access(db, account).actions)
    access = access_for(account.identity_type, account.user_id, roles, extra)
    access["roles"] = roles
    access["navigation"] = navigation_for(set(access["permissions"]), account.identity_type)
    return access
