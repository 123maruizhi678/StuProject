"""客户业务编号、历史规范化及事务回滚；仅使用独立内存数据库。"""
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, insert, select, func
from sqlalchemy.orm import Session

from app.database import Base
from app.models import common as t
from app.services.common.customer_number import customer_number, create_customer_profile
from scripts.enterprise.normalize_customer_numbers import normalize_customer_numbers


class CustomerNumberTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        tables = [getattr(t, name).__table__ if name == 'UserAccount' else getattr(t, name) for name in t.__all__]
        Base.metadata.create_all(self.engine, tables=tables)
        self.db = Session(self.engine)
        self.db.execute(insert(t.org_department).values(department_id=1, department_code='QA', department_name='测试部门', status='active'))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def values(self, **extra):
        return {'full_name': '编号测试客户', 'department_id': 1, 'source_channel': 'test',
            'status': 'new', 'authority_source': 'local', 'row_version': 1, **extra}

    def test_readable_format_and_large_identifiers(self):
        self.assertEqual(customer_number(4), 'KH-000004')
        self.assertEqual(customer_number(999999), 'KH-999999')
        self.assertEqual(customer_number(1000000), 'KH-1000000')
        self.assertLessEqual(len(customer_number(9223372036854775807)), 32)
        for value in (True, 0, -1, '4', 9223372036854775808):
            with self.subTest(value=value), self.assertRaises(ValueError):
                customer_number(value)

    def test_creation_uses_database_identifier_without_committing(self):
        first = create_customer_profile(self.db, self.values())
        second = create_customer_profile(self.db, self.values())
        self.assertEqual(first['customer_no'], customer_number(first['customer_id']))
        self.assertNotEqual(first['customer_no'], second['customer_no'])
        stored = self.db.execute(select(t.customer_profile.c.customer_no)).scalars().all()
        self.assertEqual(stored, [first['customer_no'], second['customer_no']])
        self.db.rollback()
        self.assertEqual(self.db.scalar(select(func.count()).select_from(t.customer_profile)), 0)

    def test_number_failure_rolls_back_temporary_number(self):
        execute = self.db.execute
        def fail_update(statement, *args, **kwargs):
            if getattr(statement, 'is_update', False):
                raise RuntimeError('simulated number assignment failure')
            return execute(statement, *args, **kwargs)
        with patch.object(self.db, 'execute', side_effect=fail_update), self.assertRaises(RuntimeError):
            create_customer_profile(self.db, self.values())
        self.db.rollback()
        self.assertEqual(self.db.scalar(select(func.count()).select_from(t.customer_profile)), 0)

    def test_normalization_handles_swapped_numbers_and_is_repeatable(self):
        for customer_id, number in [(1, 'KH-000002'), (2, 'KH-000001'), (3, 'CUSlegacy')]:
            self.db.execute(insert(t.customer_profile).values(**self.values(customer_id=customer_id, customer_no=number)))
        self.db.commit()
        backups = []
        changes = normalize_customer_numbers(self.db, before_apply=lambda rows: backups.extend(rows))
        self.db.commit()
        rows = self.db.execute(select(t.customer_profile).order_by(t.customer_profile.c.customer_id)).mappings().all()
        self.assertEqual([row['customer_no'] for row in rows], ['KH-000001', 'KH-000002', 'KH-000003'])
        self.assertTrue(all(row['row_version'] == 2 for row in rows))
        self.assertEqual(len(changes), 3)
        self.assertEqual(backups[2]['customer_no'], 'CUSlegacy')
        logs = self.db.execute(select(t.operation_log)).mappings().all()
        self.assertEqual(len(logs), 3)
        self.assertEqual(logs[2]['before_data']['customer_no'], 'CUSlegacy')
        self.assertEqual(logs[2]['after_data']['customer_no'], 'KH-000003')
        self.assertEqual(normalize_customer_numbers(self.db), [])
        self.assertEqual(self.db.scalar(select(func.count()).select_from(t.operation_log)), 3)

    def test_audit_failure_rolls_back_all_number_changes(self):
        self.db.execute(insert(t.customer_profile).values(**self.values(customer_id=4, customer_no='CUSold')))
        self.db.commit()
        execute = self.db.execute
        def fail_audit(statement, *args, **kwargs):
            if getattr(statement, 'is_insert', False) and statement.table.name == 'operation_log':
                raise RuntimeError('simulated audit failure')
            return execute(statement, *args, **kwargs)
        with patch.object(self.db, 'execute', side_effect=fail_audit), self.assertRaises(RuntimeError):
            normalize_customer_numbers(self.db)
        self.db.rollback()
        row = self.db.execute(select(t.customer_profile)).mappings().one()
        self.assertEqual(row['customer_no'], 'CUSold')
        self.assertEqual(row['row_version'], 1)


if __name__ == '__main__':
    unittest.main()
