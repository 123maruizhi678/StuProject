"""共享映射以现有 SQL 为准；不连接真实数据库。"""
import re
import unittest
from pathlib import Path

from sqlalchemy import LargeBinary
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app.database import Base
from app.models import common

ROOT = Path(__file__).resolve().parents[2]


class SharedModelTests(unittest.TestCase):
    def test_all_twelve_tables_have_canonical_columns_and_nullability(self):
        source = (ROOT / "scripts/sql/all.sql").read_text(encoding="utf-8-sig")
        for name in common.__all__:
            table = common.UserAccount.__table__ if name == "UserAccount" else getattr(common, name)
            with self.subTest(table=table.name):
                self.assertIs(table.metadata, Base.metadata)
                ddl = re.search(r"CREATE TABLE `?" + table.name + r"`?\s*\(.*?;", source, re.S).group()
                columns = []
                for line in ddl.splitlines()[1:]:
                    match = re.match(r"\s*`?(\w+)`?\s+(BIGINT|INT|TINYINT|VARCHAR|CHAR|TEXT|JSON|DATETIME|DATE|DECIMAL|BOOLEAN|VARBINARY)\b(.*)", line)
                    if match:
                        column, kind, rest = match.groups()
                        columns.append(column)
                        self.assertEqual(table.c[column].nullable, "NOT NULL" not in rest, column)
                        if kind == "VARBINARY":
                            self.assertIsInstance(table.c[column].type, LargeBinary)
                self.assertEqual(list(table.columns.keys()), columns)
                str(CreateTable(table).compile(dialect=mysql.dialect()))

    def test_unique_metadata_and_all_foreign_keys_resolve(self):
        self.assertEqual(len(common.__all__), 12)
        for name in common.__all__:
            table = common.UserAccount.__table__ if name == "UserAccount" else getattr(common, name)
            self.assertIs(Base.metadata.tables[table.name], table)
            for key in table.foreign_keys:
                self.assertIs(key.column.table.metadata, Base.metadata)
