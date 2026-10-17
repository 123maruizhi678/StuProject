"""研判规则表（不可变规则版本、active_slot、唯一约束及发布目标）。"""

from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, Integer, SmallInteger, String, Text

from app.database import Base
from app.models.customer._mixins import TimestampMixin


class ResearchRule(Base, TimestampMixin):
    __tablename__ = "research_rule"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    product_id = Column(BigInteger, nullable=False)
    rule_version = Column(String(32), nullable=False)
    rule_content = Column(JSON, nullable=False)
    rule_description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=False)
    active_slot = Column(SmallInteger, nullable=True)
    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)
    created_by = Column(BigInteger, nullable=True)
    row_version = Column(Integer, nullable=False, default=1)
