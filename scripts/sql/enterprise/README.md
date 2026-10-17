# 企业模块 SQL

以 `scripts/sql/all.sql` 为既有结构基线，先核对实际数据库，再按缺失对象执行增量。本次仅迁入文件，没有执行 SQL、初始化数据库或写入演示数据。

- `001_local_education.sql`：企业课程、学生选课表。
- `002_shared_runtime_fields.sql`：工单 SLA 快照、学业来源同步时间可空、申请进度并发版本。
- `migration_plan.json`：原企业模块增量计划。
- `../../enterprise/migrate_enterprise.py`：原有本地数据库增量脚本，执行前人工核对结构。

`student_profile.crm_student_id` 及其唯一键已经在基线 SQL 尾部的 ALTER 中定义，本次补入唯一共享映射。历史建表与测试数据保留在 `scripts/sql/bk/企业智能助手/`，不作为日常升级入口。
