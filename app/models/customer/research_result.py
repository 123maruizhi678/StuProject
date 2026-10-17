"""研判结果表（只追加结果、受保护输入快照及真实规则版本 FK 目标）。"""

from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, Numeric, String, func

from app.database import Base


class ResearchResult(Base):
    __tablename__ = "research_result"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_id = Column(BigInteger, nullable=False)
    customer_info_id = Column(BigInteger, nullable=False)
    product_id = Column(BigInteger, nullable=False)
    rule_version = Column(String(32), nullable=False)
    input_snapshot = Column(JSON, nullable=True)
    matched = Column(Boolean, nullable=False)
    matched_fields = Column(JSON, nullable=True)
    unmatched_reasons = Column(JSON, nullable=True)
    score = Column(Numeric(5, 2), nullable=True)
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
