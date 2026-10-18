"""客户业务编号统一为 KH-序号；序号取内部主键，至少六位且不截断。"""
from uuid import uuid4

from sqlalchemy import insert, update

from app.models.common import customer_profile


def customer_number(customer_id: int) -> str:
    if isinstance(customer_id, bool) or not isinstance(customer_id, int) or not 0 < customer_id <= 9223372036854775807:
        raise ValueError('客户内部编号必须为有效的正整数')
    return f'KH-{customer_id:06d}'


def create_customer_profile(db, values):
    """取得数据库分配的主键后写入最终编号；两步由调用方的同一事务提交。"""
    row = {**values, 'customer_no': 'TMP' + uuid4().hex[:29]}
    customer_id = db.execute(insert(customer_profile).values(**row)).inserted_primary_key[0]
    row['customer_no'] = customer_number(customer_id)
    db.execute(update(customer_profile).where(customer_profile.c.customer_id == customer_id).values(customer_no=row['customer_no']))
    return {**row, 'customer_id': customer_id}
