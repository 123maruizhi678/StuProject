"""唯一策略加载、当前权限计算及逐接口依赖；对象范围由业务服务复核。"""
from functools import lru_cache
from typing import Annotated, Callable, Literal

import yaml
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import settings
from app.models.common.user_account import UserAccount

EMPLOYEE_ROLES = {"employee", "consultant", "manager", "teacher", "academic", "admin", "analyst", "reviewer"}


class _PolicyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _Role(_PolicyModel):
    permissions: list[str]


class _Page(_PolicyModel):
    title: str
    route: str
    public: bool = False
    requires_auth: bool = True
    permission: str | None = None
    permission_any: list[str] = Field(default_factory=list)


class _Module(_PolicyModel):
    title: str
    public: bool = False
    required_any: list[str] = Field(default_factory=list)
    required_all: list[str] = Field(default_factory=list)
    pages: list[str] = Field(default_factory=list)


class _Policy(_PolicyModel):
    version: Literal[1]
    roles: dict[str, _Role]
    employee_roles: dict[str, _Role]
    pages: dict[str, _Page]
    modules: dict[str, _Module]


class _UniqueLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError("访问策略包含重复配置项")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


@lru_cache(maxsize=1)
def load_access_control() -> dict:
    """策略启动时严格校验；配置更新后重启，员工角色变更无需重新登录。"""
    try:
        raw = yaml.load(settings.ACCESS_CONTROL_FILE.read_text(encoding="utf-8-sig"), Loader=_UniqueLoader)
        policy = _Policy.model_validate(raw).model_dump()
        if set(policy["roles"]) != {"admin", "employee", "customer", "student"}:
            raise ValueError("公共身份必须为既有四种")
        if set(policy["employee_roles"]) != EMPLOYEE_ROLES:
            raise ValueError("员工角色字典必须完整保留八种受控角色")
        known = set()
        for role in (*policy["roles"].values(), *policy["employee_roles"].values()):
            for permission in role["permissions"]:
                if not permission or "*" in permission or permission != permission.strip():
                    raise ValueError("只支持精确权限标识")
                known.add(permission)
        for page in policy["pages"].values():
            required = set(page["permission_any"])
            if page["permission"]:
                required.add(page["permission"])
            if not required.issubset(known):
                raise ValueError("页面引用未定义权限")
            if page["public"] and (required or page["requires_auth"]):
                raise ValueError("公开页面不得附带认证条件")
            if not page["public"] and not page["requires_auth"]:
                raise ValueError("匿名页面必须显式声明 public")
            if not page["route"].startswith("/") or page["route"].startswith("//"):
                raise ValueError("页面地址须为站内绝对路径")
        for module in policy["modules"].values():
            required = set(module["required_any"]) | set(module["required_all"])
            if not required.issubset(known) or not set(module["pages"]).issubset(policy["pages"]):
                raise ValueError("模块引用未定义权限或页面")
            if module["public"] and (required or any(not policy["pages"][p]["public"] for p in module["pages"])):
                raise ValueError("公开模块不能包含受保护页面")
        return policy
    except (OSError, ValueError, TypeError, yaml.YAMLError, ValidationError) as exc:
        raise RuntimeError("访问策略配置无效，请检查 app/access_control.yaml") from exc


def permissions_for(identity_type: str, role_codes=()) -> set[str]:
    policy = load_access_control()
    role = policy["roles"].get(identity_type)
    permissions = set(role["permissions"]) if role else set()
    if identity_type == "employee":
        for code in role_codes:
            entry = policy["employee_roles"].get(code)
            if entry:
                permissions.update(entry["permissions"])
    return permissions


def require_permission(permission: str) -> Callable:
    """公共身份 → 当前动作；返回同一账号，调用方继续校验对象/部门/关系。"""
    if not isinstance(permission, str) or not permission or "*" in permission:
        raise ValueError("必须声明精确接口权限")
    from app.core.common.auth import get_current_account

    def dependency(account: Annotated[UserAccount, Depends(get_current_account)]) -> UserAccount:
        context = account.access_context
        if permission not in permissions_for(account.identity_type, context.role_codes):
            raise HTTPException(status_code=403, detail="Permission denied")
        return account

    return dependency


def _page_allowed(page: dict, permissions: set[str]) -> bool:
    return (
        page["public"] or (
            (not page["permission"] or page["permission"] in permissions)
            and (not page["permission_any"] or bool(set(page["permission_any"]) & permissions))
        )
    )


def _module_allowed(module: dict, permissions: set[str]) -> bool:
    return (
        (not module["required_any"] or bool(set(module["required_any"]) & permissions))
        and set(module["required_all"]).issubset(permissions)
    )


def public_access() -> dict:
    policy = load_access_control()
    return {
        "pages": {key: value for key, value in policy["pages"].items() if value["public"]},
        "modules": {key: value for key, value in policy["modules"].items() if value["public"]},
    }


def access_for(identity_type: str, user_id: int, *, role_codes=()) -> dict:
    policy = load_access_control()
    if identity_type not in policy["roles"]:
        raise HTTPException(status_code=403, detail="Identity has no access policy")
    permissions = permissions_for(identity_type, role_codes)
    pages = {key: dict(value) for key, value in policy["pages"].items() if _page_allowed(value, permissions)}
    modules = {}
    for key, value in policy["modules"].items():
        if _module_allowed(value, permissions):
            modules[key] = {**value, "pages": [p for p in value["pages"] if p in pages]}
    return {
        "user_id": user_id, "identity_type": identity_type,
        "role_codes": sorted(set(role_codes)) if identity_type == "employee" else [],
        "permissions": sorted(permissions), "pages": pages, "modules": modules,
    }
