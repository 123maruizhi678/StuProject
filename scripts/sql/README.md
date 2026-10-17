# SQL 执行范围

仅保留公共模块SQL，业务模块初始化、种子和备份SQL已从代码目录移除。开发文档中的原始完整建表文件保留作为已执行基线。

现有本地数据库已建立36表，不重跑 common/001_common_schema.sql。

- common/001_common_schema.sql：仅用于专用空库，创建账号、组织、员工、客户、学生和审计6表及必要外键。
- common/20261017_account_audit_actor.sql：公共账号开通的真实平台账号操作者增量。新增 actor_account_id 与外键，将既有操作者 CHECK 扩为四者恰一。

增量经 scripts/common/check_shared_schema.py --apply-account-audit 检查后执行；已存在时跳过。MySQL DDL 不依赖事务整体回滚。原有表、记录和业务外键不删除，不关闭外键检查。
