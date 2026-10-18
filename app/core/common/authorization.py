"""访问策略加载与权限计算：读取 YAML 角色权限、筛选页面/模块，并提供路由权限依赖。"""
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Callable

import yaml
from fastapi import Depends, HTTPException, status

from app.config import settings
from app.models.common.user_account import UserAccount


@lru_cache(maxsize=1)
def load_access_control() -> dict:
    """Load and minimally validate the access policy once per process."""
    path: Path = settings.ACCESS_CONTROL_FILE
    if not path.is_file():
        raise RuntimeError(f"Access-control file not found: {path}")

    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)

    if not isinstance(data, dict) or not isinstance(data.get("roles"), dict):
        raise RuntimeError("Access-control file must define a roles mapping")

    for section in ("pages", "modules"):
        value = data.setdefault(section, {})
        if not isinstance(value, dict):
            raise RuntimeError(f"Access-control {section} must be a mapping")

    for identity, role in data["roles"].items():
        if not isinstance(role, dict) or not isinstance(role.get("permissions", []), list):
            raise RuntimeError(f"Invalid permissions for identity: {identity}")

    return data


def permissions_for(identity_type: str, role_codes: list[str] | None = None) -> set[str]:
    """根据身份类型取得 YAML 中配置的权限标识集合。"""
    policy = load_access_control()
    role = policy["roles"].get(identity_type)
    permissions = set(role.get("permissions", [])) if role else set()
    if identity_type == "employee":
        for code in role_codes or []:
            permissions.update(policy.get("employee_roles", {}).get(code, {}).get("permissions", []))
    return permissions


def require_permission(permission: str) -> Callable:
    """FastAPI dependency that protects an endpoint with one permission."""
    from app.core.common.auth import get_current_account

    def dependency(
        account: Annotated[UserAccount, Depends(get_current_account)],
    ) -> UserAccount:
        """检查当前账号是否具有路由要求的权限。"""
        if permission not in permissions_for(account.identity_type):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )
        return account

    return dependency


def _page_is_allowed(page: dict, permissions: set[str]) -> bool:
    """根据公开标记、登录要求和权限条件判断页面可见性。"""
    if page.get("public", False) or not page.get("requires_auth", True):
        return True

    permission = page.get("permission")
    permission_any = set(page.get("permission_any", []))
    if permission:
        return permission in permissions
    if permission_any:
        return bool(permission_any.intersection(permissions))
    return True


def _module_is_allowed(module: dict, permissions: set[str]) -> bool:
    """根据 required_any 与 required_all 条件判断模块可见性。"""
    required_any = set(module.get("required_any", []))
    required_all = set(module.get("required_all", []))
    return (
        (not required_any or bool(required_any.intersection(permissions)))
        and required_all.issubset(permissions)
    )


def public_access() -> dict:
    """Return public pages/modules for clients before login."""
    policy = load_access_control()
    pages = {
        page_id: page
        for page_id, page in policy["pages"].items()
        if page.get("public", False) or not page.get("requires_auth", True)
    }
    modules = {
        module_id: module
        for module_id, module in policy["modules"].items()
        if not module.get("required_any") and not module.get("required_all")
    }
    return {"pages": pages, "modules": modules}


def access_for(identity_type: str, user_id: int) -> dict:
    """Return the pages and modules visible to one authenticated account."""
    policy = load_access_control()
    role = policy["roles"].get(identity_type)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Identity has no access policy",
        )

    permissions = set(role.get("permissions", []))
    pages = {
        page_id: page
        for page_id, page in policy["pages"].items()
        if _page_is_allowed(page, permissions)
    }
    modules = {
        module_id: module
        for module_id, module in policy["modules"].items()
        if _module_is_allowed(module, permissions)
    }

    return {
        "user_id": user_id,
        "identity_type": identity_type,
        "permissions": sorted(permissions),
        "pages": pages,
        "modules": modules,
    }
