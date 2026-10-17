-- 企业模块迁入时需要的共享表增量；执行前核对现有结构，不自动执行。
-- student_profile.crm_student_id 已在 scripts/sql/all.sql 的 ALTER 中定义。
ALTER TABLE service_ticket_record
 ADD COLUMN sla_snapshot JSON NULL COMMENT '每轮时限策略与处理事件快照';
ALTER TABLE student_academic_event
 MODIFY COLUMN synced_at DATETIME(6) NULL COMMENT '最后真实外部同步时间，local来源为空';
ALTER TABLE student_application_progress
 ADD COLUMN row_version INTEGER NOT NULL DEFAULT 1 COMMENT '并发修改版本号';
ALTER TABLE student_application_progress
 MODIFY COLUMN synced_at DATETIME(6) NULL COMMENT '最后真实外部同步时间，local来源为空';
