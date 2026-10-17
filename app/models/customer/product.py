"""甲方产品表。"""

from sqlalchemy import BigInteger, Column, Integer, String, Text

from app.database import Base
from app.models.common import TimestampMixin


class Product(Base, TimestampMixin):
    __tablename__ = "product"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    product_code = Column(String(32), nullable=False, unique=True)  # 创建后不可修改
    product_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    target_profile_summary = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="active")  # active/disabled
    row_version = Column(Integer, nullable=False, default=1)
