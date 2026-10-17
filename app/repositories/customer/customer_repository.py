"""研判数据访问：来源 / 字段 / 规则 / 产品 / 结果。

统一锁序（source -> info -> product -> rule -> result）；单条 / 批量均按业务
幂等键复用既有结果。
"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer.customer_info import CustomerInfo
from app.models.customer.customer_source import CustomerSource
from app.models.customer.product import Product
from app.models.customer.research_result import ResearchResult
from app.models.customer.research_rule import ResearchRule


# ---- 来源 ----
def get_source(db: Session, source_id: int) -> Optional[CustomerSource]:
    return db.get(CustomerSource, source_id)


def create_source(db: Session, **kwargs) -> CustomerSource:
    src = CustomerSource(**kwargs)
    db.add(src)
    return src


# ---- 客户关键字段 ----
def get_info(db: Session, info_id: int) -> Optional[CustomerInfo]:
    return db.get(CustomerInfo, info_id)


def create_info(db: Session, **kwargs) -> CustomerInfo:
    info = CustomerInfo(**kwargs)
    db.add(info)
    return info


def list_info_by_source(db: Session, source_id: int) -> List[CustomerInfo]:
    return list(db.scalars(select(CustomerInfo).where(CustomerInfo.source_id == source_id)).all())


# ---- 产品 ----
def get_product_by_code(db: Session, code: str) -> Optional[Product]:
    return db.scalar(select(Product).where(Product.product_code == code))


def get_product(db: Session, product_id: int) -> Optional[Product]:
    return db.get(Product, product_id)


def create_product(db: Session, **kwargs) -> Product:
    p = Product(**kwargs)
    db.add(p)
    return p


def list_products(db: Session) -> List[Product]:
    return list(db.scalars(select(Product).order_by(Product.id)).all())


# ---- 规则 ----
def get_active_rule(db: Session, product_id: int) -> Optional[ResearchRule]:
    """取产品当前生效版本（is_active 且 active_slot 占用）。"""
    return db.scalar(
        select(ResearchRule).where(
            ResearchRule.product_id == product_id,
            ResearchRule.is_active.is_(True),
        ).order_by(ResearchRule.id.desc())
    )


def get_rule(db: Session, product_id: int, rule_version: str) -> Optional[ResearchRule]:
    return db.scalar(
        select(ResearchRule).where(
            ResearchRule.product_id == product_id,
            ResearchRule.rule_version == rule_version,
        )
    )


def list_rules(db: Session, product_id: Optional[int] = None) -> List[ResearchRule]:
    stmt = select(ResearchRule).order_by(ResearchRule.id)
    if product_id is not None:
        stmt = stmt.where(ResearchRule.product_id == product_id)
    return list(db.scalars(stmt).all())


def create_rule(db: Session, **kwargs) -> ResearchRule:
    rule = ResearchRule(**kwargs)
    db.add(rule)
    return rule


def deactivate_rules(db: Session, product_id: int) -> None:
    """停用产品当前所有生效版本（规则发布事务内调用）。"""
    for r in db.scalars(select(ResearchRule).where(
        ResearchRule.product_id == product_id,
        ResearchRule.is_active.is_(True),
    )).all():
        r.is_active = False
        r.active_slot = None


# ---- 结果 ----
def get_result(db: Session, info_id: int, product_id: int, rule_version: str) -> Optional[ResearchResult]:
    return db.scalar(
        select(ResearchResult).where(
            ResearchResult.customer_info_id == info_id,
            ResearchResult.product_id == product_id,
            ResearchResult.rule_version == rule_version,
        ).order_by(ResearchResult.id.desc())
    )


def create_result(db: Session, **kwargs) -> ResearchResult:
    result = ResearchResult(**kwargs)
    db.add(result)
    return result


def get_result_by_id(db: Session, result_id: int) -> Optional[ResearchResult]:
    return db.get(ResearchResult, result_id)


def list_results(
    db: Session,
    product_id: Optional[int] = None,
    matched: Optional[bool] = None,
    offset: int = 0,
    limit: int = 20,
) -> List[ResearchResult]:
    stmt = select(ResearchResult).order_by(ResearchResult.id.desc())
    if product_id is not None:
        stmt = stmt.where(ResearchResult.product_id == product_id)
    if matched is not None:
        stmt = stmt.where(ResearchResult.matched.is_(matched))
    return list(db.scalars(stmt.offset(offset).limit(limit)).all())


def count_results(
    db: Session,
    product_id: Optional[int] = None,
    matched: Optional[bool] = None,
) -> int:
    from sqlalchemy import func

    stmt = select(func.count(ResearchResult.id))
    if product_id is not None:
        stmt = stmt.where(ResearchResult.product_id == product_id)
    if matched is not None:
        stmt = stmt.where(ResearchResult.matched.is_(matched))
    return db.scalar(stmt) or 0
