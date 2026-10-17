# 公共账号与身份关联结构

新建专用空库时执行 001_common_schema.sql，再执行账号审计增量。本机现有库只应用过账号审计增量，未重建或删除36张既有表。

操作文档第007项要求真人平台管理员使用 actor_account_id，不能冒充自动服务。增量增加该列和指向 user_account.user_id 的 RESTRICT 外键，既有 employee_id、student_id、service_code 分支继续有效。具体 identity_type=admin 在账号固定服务核验。

数据库为空不表示已开通登录账号。受控开通由 scripts/common/create_account.py 完成，账号和审计同事务写入。
