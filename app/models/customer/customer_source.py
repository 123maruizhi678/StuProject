"""客户信息来源表。"""

from sqlalchemy import BigInteger, Column, Integer, String, Text

from app.database import Base
from app.models.common import TimestampMixin


class CustomerSource(Base, TimestampMixin):
    __tablename__ = "customer_source"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_type = Column(String(16), nullable=False)  # text/pdf/excel
    raw_content = Column(Text, nullable=True)  # 受控原始文本，默认不返回
    file_name = Column(String(255), nullable=True)
    file_path = Column(String(255), nullable=True)  # 非公网受控定位键
    status = Column(String(32), nullable=False, default="pending")  # pending/parsed/failed
    created_by = Column(BigInteger, nullable=True)  # 提交账号 user_id
    row_version = Column(Integer, nullable=False, default=1)
    current_parse_batch_id = Column(BigInteger, nullable=True)
