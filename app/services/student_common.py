"""学生业务公共规则：身份归属、规范化摘要和成功回执重放。"""
from datetime import timezone
import hashlib
import json

class StudentBusinessError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


def digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def utc_naive(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class StudentBusinessService:
    def _student(self, account, *, lock=False):
        if account.identity_type != "student" or not account.student_id:
            raise StudentBusinessError(403, "此功能仅限学生本人")
        row = self.repository.get_student(account.student_id, lock=lock)
        if not row or row["is_archived"] or row["status"] in (
            "disabled", "inactive", "withdrawn", "suspended"
        ):
            raise StudentBusinessError(403, "学生档案不可用")
        return account.student_id

    def _replay(self, operation_key, parameters_hash):
        row = self.repository.find_operation(operation_key)
        if row is None:
            return None
        if row["parameters_hash"] != parameters_hash:
            raise StudentBusinessError(409, "同一幂等键不能提交不同的业务内容")
        if row["operation_status"] != "succeeded":
            raise StudentBusinessError(409, "请求正在处理，请稍后核实")
        return row["result_reference"]
