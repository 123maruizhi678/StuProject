"""客户关键字段表（解析批次 / 稳定行键 / 组合引用及受控归并目标）。"""

from sqlalchemy import JSON, BigInteger, Column, Integer, LargeBinary, String

from app.database import Base
from app.models.customer._mixins import TimestampMixin


class CustomerInfo(Base, TimestampMixin):
    __tablename__ = "customer_info"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_id = Column(BigInteger, nullable=False)
    parse_batch_id = Column(BigInteger, nullable=True)
    source_row_key = Column(String(128), nullable=True)
    customer_id = Column(BigInteger, nullable=True)  # 归并后回填
    full_name = Column(String(100), nullable=True)
    gender = Column(String(16), nullable=True)
    age = Column(Integer, nullable=True)
    education_level = Column(String(32), nullable=True)
    major = Column(String(100), nullable=True)
    work_years = Column(Integer, nullable=True)
    industry = Column(String(64), nullable=True)
    position_title = Column(String(100), nullable=True)
    city = Column(String(64), nullable=True)
    income_level = Column(String(32), nullable=True)
    target_product_code = Column(String(32), nullable=True)
    phone_ciphertext = Column(LargeBinary(512), nullable=True)
    phone_lookup_token = Column(String(64), nullable=True)
    contact_email = Column(String(254), nullable=True)  # 本期仅受控掩码或 NULL
    raw_fields = Column(JSON, nullable=True)
    row_version = Column(Integer, nullable=False, default=1)
