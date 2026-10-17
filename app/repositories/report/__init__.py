"""智能报告模块数据访问包（参数化查询与条件更新）。"""

from app.repositories.report.report_repository import (
    claim_record,
    find_record_by_key,
    get_config_by_code,
    get_record,
    insert_record,
    list_configs,
    list_records,
    load_employee_scope,
    mark_failed,
    publish_record,
    record_visible_in_scope,
    report_task_table_exists,
    save_frozen_input,
    update_config,
)

__all__ = [
    "claim_record",
    "find_record_by_key",
    "get_config_by_code",
    "get_record",
    "insert_record",
    "list_configs",
    "list_records",
    "load_employee_scope",
    "mark_failed",
    "publish_record",
    "record_visible_in_scope",
    "report_task_table_exists",
    "save_frozen_input",
    "update_config",
]
