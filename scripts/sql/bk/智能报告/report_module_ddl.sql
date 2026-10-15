-- ============================================================================
-- 智能教育服务 Agent 平台 · 智能报告模块 建表脚本
-- 目标数据库：education_agent（utf8mb4 / InnoDB）
-- 适用：MySQL 8.0.16+（依赖 CHECK 约束），不适用于 MySQL 5.7
-- 参考：https://dev.mysql.com/doc/refman/8.0/en/create-table-check-constraints.html
--
-- 说明：
--   1. 本脚本为智能报告模块三张核心表（report_config / report_record / report_metric）。
--   2. 已对齐项目统一规范：DATETIME(3)+UTC、utf8mb4_0900_ai_ci、编码/身份键 utf8mb4_bin、
--      CHECK 约束、真实外键、乐观锁 row_version。
--   3. 首次初始化使用：目标库内这三张表应尚不存在；本脚本不删除已有库/表、不创建数据库用户或
--      配置密码；仅写入 report_config 五类报告配置种子数据（非业务数据）。
--   4. 报告依赖的上游表（customer_profile / customer_followup / employee_daily_report /
--      mental_health_profile / mental_warning / service_ticket）由企业、学生模块建表，
--      报告模块只读聚合，不在本脚本重复建表（见文末附录）。
-- 执行方式：mysql -uroot -p12345 < report_module_ddl.sql
-- ============================================================================

SET NAMES utf8mb4;
SET SESSION time_zone = '+00:00';
SET SESSION sql_mode = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

CREATE DATABASE IF NOT EXISTS `education_agent`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
USE `education_agent`;

-- ----------------------------------------------------------------------------
-- 1. 报告配置表 report_config
-- ----------------------------------------------------------------------------
CREATE TABLE `report_config` (
  `report_config_id` BIGINT       NOT NULL AUTO_INCREMENT COMMENT '报告配置主键 ID。 主键（PK）。',
  `report_code`      VARCHAR(64)  COLLATE utf8mb4_bin NOT NULL COMMENT '报告代码（五类枚举，见 CHECK）。',
  `report_name`      VARCHAR(128) NOT NULL COMMENT '报告名称。',
  `report_period`    VARCHAR(16)  COLLATE utf8mb4_bin NOT NULL DEFAULT 'week' COMMENT '报告周期：day/week/month。',
  `cron_expr`        VARCHAR(64)  DEFAULT NULL COMMENT '定时表达式（cron，按东八区配置）。',
  `enabled`          BOOLEAN      NOT NULL DEFAULT 1 COMMENT '是否启用：1 启用、0 停用。',
  `created_at`       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC。',
  `updated_at`       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '记录最近更新时间，UTC。',
  `row_version`      INT          NOT NULL DEFAULT 1 COMMENT '并发版本号，每次业务修改递增。',
  PRIMARY KEY (`report_config_id`),
  UNIQUE KEY `uq_report_config_code` (`report_code`),
  CONSTRAINT `ck_report_config_code` CHECK (`report_code` IN ('customer_overview','daily_report','weekly_report','mental_weekly','complaint_weekly')),
  CONSTRAINT `ck_report_config_period` CHECK (`report_period` IN ('day','week','month')),
  CONSTRAINT `ck_report_config_enabled` CHECK (`enabled` IN (0,1)),
  CONSTRAINT `ck_report_config_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='报告配置表';

-- 初始化五类报告配置
INSERT INTO `report_config` (`report_code`, `report_name`, `report_period`, `cron_expr`, `enabled`) VALUES
('customer_overview', '全域客户经营分析报告', 'week',  '0 0 9 * * 5', 1),
('daily_report',     '员工日报汇总报告（日）', 'day',  '0 30 18 * * *', 1),
('weekly_report',    '员工日报汇总报告（周）', 'week', '0 0 9 * * 5', 1),
('mental_weekly',    '学生心理健康周报',       'week', '0 0 9 * * 5', 1),
('complaint_weekly', '投诉处理周报',           'week', '0 0 9 * * 5', 1);

-- ----------------------------------------------------------------------------
-- 2. 报告生成记录表 report_record
-- ----------------------------------------------------------------------------
CREATE TABLE `report_record` (
  `report_record_id`    BIGINT       NOT NULL AUTO_INCREMENT COMMENT '报告生成记录主键 ID。 主键（PK）。',
  `report_config_id`    BIGINT       NOT NULL COMMENT '报告配置 ID。 外键（FK）关联 report_config.report_config_id。',
  `report_code`         VARCHAR(64)  COLLATE utf8mb4_bin NOT NULL COMMENT '报告代码（冗余，便于按类型检索）。',
  `idempotency_key`     VARCHAR(128) COLLATE utf8mb4_bin NOT NULL COMMENT '幂等键：report_code+时间窗+版本。',
  `start_time`          DATETIME(3)  NOT NULL COMMENT '统计起始时间（UTC）。',
  `end_time`            DATETIME(3)  NOT NULL COMMENT '统计截止时间（UTC），必须晚于起始。',
  `timezone`            VARCHAR(32)  NOT NULL DEFAULT 'UTC' COMMENT '统计口径时区。',
  `data_snapshot_at`    DATETIME(3)  DEFAULT NULL COMMENT '数据快照时间，用于指标可复算。',
  `report_version`      VARCHAR(32)  COLLATE utf8mb4_bin NOT NULL DEFAULT 'v1' COMMENT '报告生成版本，参与幂等键。',
  `source_record_count` INT          NOT NULL DEFAULT 0 COMMENT '来源记录数，用于追溯与识别数据不足。',
  `report_content`      LONGTEXT     DEFAULT NULL COMMENT '报告正文（AI 生成的结构化文本）。',
  `metric_json`         JSON         DEFAULT NULL COMMENT '可复算指标快照（JSON）。',
  `status`              VARCHAR(16)  COLLATE utf8mb4_bin NOT NULL DEFAULT 'pending' COMMENT '状态：pending/running/success/failed。',
  `fail_reason`         TEXT         DEFAULT NULL COMMENT '失败原因。',
  `generated_at`        DATETIME(3)  DEFAULT NULL COMMENT '生成完成时间（UTC）。',
  `created_at`          DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC。',
  `updated_at`          DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '记录最近更新时间，UTC。',
  `row_version`         INT          NOT NULL DEFAULT 1 COMMENT '并发版本号。',
  PRIMARY KEY (`report_record_id`),
  UNIQUE KEY `uq_report_record_idempotency` (`idempotency_key`),
  KEY `idx_report_record_config` (`report_config_id`),
  KEY `idx_report_record_code_time` (`report_code`, `start_time`, `end_time`),
  KEY `idx_report_record_status` (`status`),
  CONSTRAINT `fk_report_record_config_id` FOREIGN KEY (`report_config_id`) REFERENCES `report_config` (`report_config_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_report_record_period` CHECK (`end_time` > `start_time`),
  CONSTRAINT `ck_report_record_status` CHECK (`status` IN ('pending','running','success','failed')),
  CONSTRAINT `ck_report_record_count` CHECK (`source_record_count` >= 0),
  CONSTRAINT `ck_report_record_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='报告生成记录表';

-- ----------------------------------------------------------------------------
-- 3. 报告指标明细表 report_metric（支撑"指标可复算"）
-- ----------------------------------------------------------------------------
CREATE TABLE `report_metric` (
  `report_metric_id`  BIGINT        NOT NULL AUTO_INCREMENT COMMENT '报告指标明细主键 ID。 主键（PK）。',
  `report_record_id`  BIGINT        NOT NULL COMMENT '所属报告记录 ID。 外键（FK）关联 report_record.report_record_id。',
  `metric_code`       VARCHAR(64)   COLLATE utf8mb4_bin NOT NULL COMMENT '指标代码。',
  `metric_name`       VARCHAR(128)  NOT NULL COMMENT '指标名称。',
  `metric_value`      DECIMAL(20,4) DEFAULT NULL COMMENT '指标数值（数值型指标）。',
  `metric_text`       TEXT          DEFAULT NULL COMMENT '指标文本值（非数值型指标）。',
  `metric_unit`       VARCHAR(32)   DEFAULT NULL COMMENT '单位。',
  `calc_rule`         TEXT          DEFAULT NULL COMMENT '计算口径/规则说明，用于指标复算。',
  `period_type`       VARCHAR(16)   COLLATE utf8mb4_bin DEFAULT NULL COMMENT '周期类型：day/week/month。',
  `created_at`        DATETIME(3)   NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC。',
  PRIMARY KEY (`report_metric_id`),
  KEY `idx_report_metric_record` (`report_record_id`),
  KEY `idx_report_metric_code` (`metric_code`),
  CONSTRAINT `fk_report_metric_record_id` FOREIGN KEY (`report_record_id`) REFERENCES `report_record` (`report_record_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_report_metric_value` CHECK (`metric_value` IS NOT NULL OR `metric_text` IS NOT NULL),
  CONSTRAINT `ck_report_metric_period` CHECK (`period_type` IS NULL OR `period_type` IN ('day','week','month'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='报告指标明细表';

-- ============================================================================
-- 附录：报告依赖的上游数据表（由企业/学生模块建表，报告模块只读聚合）
-- 说明：经与 scripts/sql 下各模块建表方案交叉核对，上游表已由对应模块落地，
--       报告模块不重复建表，仅在此说明数据来源与事实源约定。
-- ============================================================================
-- 1) 全域客户经营分析报告：
--    - 意向/成交/流失客户：企业模块 customer_profile（status 含 new/contacting/qualified/signed/lost，
--      lost_reason、status_changed_at、last_followup_at 均已具备）。
--    - 客户跟进/转化路径：企业模块 customer_followup（followup_at/channel/content/summary）。
--    - 研判参考：客户研判模块 customer_judgement（scripts/sql/all.sql 尚未落地该表，
--      待客户研判模块补建后再接入；当前报告不预设其字段）。
-- 2) 员工日报汇总报告（日/周）：
--    - 企业模块 employee_daily_report（report_date/submitted_content/ai_summary/status/department_id_at_submit）。
-- 3) 学生心理健康周报：
--    - 学生模块 mental_health_profile（emotion_tag/emotion_score/risk_level/observed_at，一行一次评估）。
--    - 学生模块 mental_warning（risk_level/follower_status/follower_id/acknowledged_at/closed_at）。
-- 4) 投诉处理周报：
--    - 统一工单事实源采用 service_ticket（scripts/sql/all.sql 已选定为企业端+学生端共用统一工单，
--      after_sales_ticket 为已排除的重复模型，不在统一建表脚本中重复建表）。
--    - service_ticket 已含投诉分类（ticket_type/category_code）、首次响应（first_response_at）、
--      解决/关闭（resolved_at/closed_at）、满意度（satisfaction_score）等周报所需字段。
-- ============================================================================
