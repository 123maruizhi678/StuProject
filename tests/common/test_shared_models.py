"""共享映射以现有 SQL 为准；不连接真实数据库。"""
import re
import unittest
from pathlib import Path

from sqlalchemy import LargeBinary
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app.database import Base
from app.models import common
from tests.common.sql_contract import columns_for

ROOT = Path(__file__).resolve().parents[2]


class SharedModelTests(unittest.TestCase):
    def test_shared_tables_have_baseline_and_increment_columns_and_nullability(self):
        for name in common.__all__:
            table = common.UserAccount.__table__ if name == "UserAccount" else getattr(common, name)
            with self.subTest(table=table.name):
                self.assertIs(table.metadata, Base.metadata)
                columns = columns_for(table.name)
                for column, (kind, nullable) in columns.items():
                    self.assertEqual(table.c[column].nullable, nullable, column)
                    if kind == "VARBINARY":
                        self.assertIsInstance(table.c[column].type, LargeBinary)
                self.assertEqual(list(table.columns.keys()), list(columns))
                str(CreateTable(table).compile(dialect=mysql.dialect()))

    def test_unique_metadata_and_all_foreign_keys_resolve(self):
        self.assertEqual(len(common.__all__), 15)
        for name in common.__all__:
            table = common.UserAccount.__table__ if name == "UserAccount" else getattr(common, name)
            self.assertIs(Base.metadata.tables[table.name], table)
            for key in table.foreign_keys:
                self.assertIs(key.column.table.metadata, Base.metadata)
