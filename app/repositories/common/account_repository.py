"""参数化账号/关联主档查询；业务数据由所属模块维护。"""
from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.common import UserAccount, customer_profile, employee, org_department, student_profile


@dataclass(frozen=True)
class AccountContext:
    user_id: int
    identity_type: str
    employee_id: int | None = None
    customer_id: int | None = None
    student_id: int | None = None
    department_id: int | None = None
    role_codes: tuple[str, ...] = ()


def find_by_username(db: Session, username: str) -> UserAccount | None:
    return db.scalar(select(UserAccount).where(UserAccount.username == username))


def find_by_id(db: Session, user_id: int) -> UserAccount | None:
    return db.get(UserAccount, user_id, populate_existing=True)


def resolve_context(db: Session, account: UserAccount) -> AccountContext | None:
    """逐请求查询当前关联与有效状态，不接受客户端角色或部门。"""
    identity = account.identity_type
    links = (account.employee_id, account.customer_id, account.student_id)
    required = {"admin": (False, False, False), "employee": (True, False, False),
                "customer": (False, True, False), "student": (False, False, True)}
    if identity not in required or tuple(v is not None for v in links) != required[identity]:
        return None
    if identity == "admin":
        return AccountContext(account.user_id, identity)
    if identity == "employee":
        row = db.execute(
            select(employee.c.employee_id, employee.c.department_id, employee.c.role_codes)
            .join(org_department, employee.c.department_id == org_department.c.department_id)
            .where(employee.c.employee_id == account.employee_id,
                   employee.c.status == "active", org_department.c.status == "active")
        ).mappings().one_or_none()
        if row is None:
            return None
        roles = row["role_codes"]
        if not isinstance(roles, list) or not roles or not all(isinstance(v, str) for v in roles):
            return None
        from app.core.common.authorization import EMPLOYEE_ROLES
        if not set(roles).issubset(EMPLOYEE_ROLES):
            return None
        return AccountContext(
            account.user_id, identity, employee_id=row["employee_id"],
            department_id=row["department_id"], role_codes=tuple(sorted(set(roles))),
        )
    table = customer_profile if identity == "customer" else student_profile
    key = table.c.customer_id if identity == "customer" else table.c.student_id
    value = account.customer_id if identity == "customer" else account.student_id
    row = db.execute(select(table).where(key == value, table.c.is_archived.is_(False))).mappings().one_or_none()
    if row is None:
        return None
    if identity == "customer":
        return AccountContext(account.user_id, identity, customer_id=value, department_id=row["department_id"])
    if row["status"] in {"disabled", "inactive", "left", "archived"}:
        return None
    return AccountContext(account.user_id, identity, student_id=value, department_id=row["department_id"])
