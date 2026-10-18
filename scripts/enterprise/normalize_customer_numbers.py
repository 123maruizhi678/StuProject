"""客户业务编号规范化。默认只预览；--apply 备份映射并在同一事务内更新、审计。"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.runtime' / 'backend-deps'))

from sqlalchemy import insert, select, update, text
from sqlalchemy.orm import Session
from app.database import engine
from app.config import settings
from app.models.common import customer_profile, operation_log
from app.repositories.enterprise.enterprise_repository import digest
from app.services.common.customer_number import customer_number


def normalize_customer_numbers(db, before_apply=None):
    rows = db.execute(select(customer_profile.c.customer_id, customer_profile.c.customer_no,
        customer_profile.c.row_version, customer_profile.c.updated_at).order_by(customer_profile.c.customer_id).with_for_update()).mappings().all()
    changes = [{**dict(row), 'new_customer_no': customer_number(row['customer_id'])} for row in rows
        if row['customer_no'] != customer_number(row['customer_id'])]
    if not changes:
        return []
    if before_apply:
        before_apply(changes)
    batch = uuid4().hex
    now = datetime.utcnow()
    # 先腾出本批客户的旧编号，支持历史编号互换而不触发唯一约束。
    for row in changes:
        db.execute(update(customer_profile).where(customer_profile.c.customer_id == row['customer_id']).values(customer_no='MIG' + uuid4().hex[:29]))
    for row in changes:
        customer_id = row['customer_id']
        result = db.execute(update(customer_profile).where(customer_profile.c.customer_id == customer_id,
            customer_profile.c.row_version == row['row_version']).values(customer_no=row['new_customer_no'], row_version=row['row_version'] + 1, updated_at=now))
        if result.rowcount != 1:
            raise RuntimeError('客户记录已变化，整批编号更新已取消')
        before = {'customer_id': customer_id, 'customer_no': row['customer_no'], 'row_version': row['row_version']}
        after = {'customer_id': customer_id, 'customer_no': row['new_customer_no'], 'row_version': row['row_version'] + 1}
        key = f'customer-number-{batch}-{customer_id}'
        db.execute(insert(operation_log).values(operation_key=digest(key), service_code='maintenance.customer_number',
            action_code='enterprise.customer.number_format', entity_type='customer_profile', entity_id=customer_id,
            request_key=key, parameters_hash=digest(after), before_data=before, after_data=after, result_reference=after,
            change_reason='按用户要求统一客户业务编号为 KH-客户序号（至少六位）', operation_status='succeeded',
            finished_at=now, created_at=now, updated_at=now, row_version=1))
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if settings.DB_HOST not in ('127.0.0.1', 'localhost', '::1'):
        raise RuntimeError('此维护脚本仅用于当前本机数据库')
    with Session(engine) as db:
        references = db.execute(text("SELECT TABLE_NAME,COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE REFERENCED_TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME='customer_profile' "
            "AND REFERENCED_COLUMN_NAME='customer_no'")).all()
        if references:
            raise RuntimeError('业务编号存在外键引用，未执行更新')
        db.rollback()
        backup_path = None

        def backup(changes):
            nonlocal backup_path
            directory = ROOT / '.runtime' / 'customer-number-backups'
            directory.mkdir(parents=True, exist_ok=True)
            backup_path = directory / (datetime.utcnow().strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8] + '.json')
            backup_path.write_text(json.dumps({'database': settings.DB_NAME, 'changes': changes}, ensure_ascii=False,
                indent=2, default=str), encoding='utf-8')

        with db.begin():
            if args.apply:
                changes = normalize_customer_numbers(db, before_apply=backup)
            else:
                rows = db.execute(select(customer_profile.c.customer_id, customer_profile.c.customer_no)).mappings().all()
                changes = [{'customer_id': row['customer_id'], 'customer_no': row['customer_no'],
                    'new_customer_no': customer_number(row['customer_id'])} for row in rows if row['customer_no'] != customer_number(row['customer_id'])]
        print(json.dumps({'applied': args.apply, 'changed_count': len(changes), 'backup': str(backup_path) if backup_path else None,
            'mappings': [{key: row[key] for key in ('customer_id', 'customer_no', 'new_customer_no')} for row in changes]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
