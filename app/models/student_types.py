"""学生表的 UTC 和可移植类型；MySQL 为正式数据库，SQLite 仅用于隔离测试。"""

from datetime import datetime, timezone
from sqlalchemy import BigInteger, Integer, DateTime, String
from sqlalchemy.dialects.mysql import DATETIME, VARCHAR

ID_TYPE = BigInteger().with_variant(Integer(), "sqlite")


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def timestamp():
    return DateTime().with_variant(DATETIME(fsp=3), "mysql")


def binary_string(length):
    return String(length).with_variant(
        VARCHAR(length, collation="utf8mb4_bin"), "mysql"
    )


# 学生库沿用组长现有DATETIME(6)，共享企业表继续使用DATETIME(3)。
def student_timestamp():
    return DateTime().with_variant(DATETIME(fsp=6), "mysql")


def ascii_string(length):
    return String(length).with_variant(
        VARCHAR(length, charset="ascii", collation="ascii_bin"), "mysql"
    )


from sqlalchemy.sql.expression import ColumnElement
from sqlalchemy.ext.compiler import compiles


class StudentCreatedDefault(ColumnElement):
    type = DateTime()
    inherit_cache = True


class StudentUpdatedDefault(ColumnElement):
    type = DateTime()
    inherit_cache = True


@compiles(StudentCreatedDefault)
@compiles(StudentUpdatedDefault)
def default_timestamp(element, compiler, **kwargs):
    return "CURRENT_TIMESTAMP"


@compiles(StudentCreatedDefault, "mysql")
def mysql_created(element, compiler, **kwargs):
    return "CURRENT_TIMESTAMP(6)"


@compiles(StudentUpdatedDefault, "mysql")
def mysql_updated(element, compiler, **kwargs):
    return "CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"
