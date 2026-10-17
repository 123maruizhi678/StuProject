"""共享映射的跨方言类型与 UTC 时间默认值。"""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement

identifier = BigInteger().with_variant(Integer, "sqlite")


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class utc_timestamp(FunctionElement):
    type = DateTime()
    inherit_cache = True


@compiles(utc_timestamp)
def _timestamp(element, compiler, **kwargs):
    return "CURRENT_TIMESTAMP"


@compiles(utc_timestamp, "mysql")
def _mysql_timestamp(element, compiler, **kwargs):
    return "CURRENT_TIMESTAMP(3)"
