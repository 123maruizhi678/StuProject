"""业务操作审计与幂等回执；与调用业务使用同一事务。"""
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.models.common import operation_log as operations


class OperationLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_key(self, operation_key: str, *, lock=False):
        query = select(operations).where(operations.c.operation_key == operation_key)
        if lock:
            query = query.with_for_update()
        return self.db.execute(query).mappings().first()

    def create(self, values: dict):
        actors = [values.get(name) for name in ("employee_id", "student_id", "service_code")]
        if sum(value is not None for value in actors) != 1:
            raise ValueError("审计记录必须且只能有一个真实操作者")
        result = self.db.execute(insert(operations).values(**values))
        return result.inserted_primary_key[0]

    def complete(self, operation_key: str, values: dict):
        result = self.db.execute(update(operations).where(
            operations.c.operation_key == operation_key,
            operations.c.operation_status == "processing",
        ).values(**{**values, "row_version": operations.c.row_version + 1}))
        return result.rowcount == 1
