"""兼容旧导入；公共表只有一份映射。"""
from app.models.common import *
from app.models.common import metadata
from sqlalchemy import BigInteger, Integer
identifier = BigInteger().with_variant(Integer, "sqlite")
