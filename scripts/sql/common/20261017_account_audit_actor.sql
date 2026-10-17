-- 公共账号初始化所需增量（操作文档第007项）。
-- 仅增加真实平台账号操作者分支，不删除表或数据。
-- 通过 scripts/common/check_shared_schema.py --apply-account-audit 受控执行。
ALTER TABLE operation_log
  ADD COLUMN actor_account_id BIGINT NULL COMMENT '真实平台管理员账号；公共账号开通审计',
  DROP CHECK ck_operation_actor,
  ADD CONSTRAINT ck_operation_actor CHECK (
    ((employee_id IS NOT NULL) + (student_id IS NOT NULL) +
     (service_code IS NOT NULL) + (actor_account_id IS NOT NULL)) = 1
  ),
  ADD CONSTRAINT fk_operation_actor_account FOREIGN KEY (actor_account_id)
    REFERENCES user_account(user_id) ON DELETE RESTRICT ON UPDATE RESTRICT;
