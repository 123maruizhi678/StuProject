-- ============================================================================
-- 智能教育服务 Agent 平台 · 智能报告模块 建表脚本
-- 目标数据库：education_agent（utf8mb4 / InnoDB）
-- 说明：基于《业务文档/05数据库设计》第六章，并按交叉比对结论扩展：
--       ① 报告类型用 report_code 枚举替代原 daily/weekly，覆盖五类报告；
--       ② report_record 补充统计时间窗、数据快照、幂等键、失败原因等字段；
--       ③ 新增 report_metric 支撑"指标可复算"验收。
-- 执行方式：mysql -uroot -p12345 education_agent < report_module_ddl.sql
-- ============================================================================

SET NAMES utf8mb4;

-- ----------------------------------------------------------------------------
-- 1. 报告配置表 report_config
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `report_config`;
CREATE TABLE `report_config` (
  `id`            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  `report_code`   VARCHAR(64)  NOT NULL COMMENT '报告代码：customer_overview/daily_report/weekly_report/mental_weekly/complaint_weekly',
  `report_name`   VARCHAR(128) NOT NULL COMMENT '报告名称',
  `report_period` VARCHAR(16)  NOT NULL DEFAULT 'week' COMMENT '报告周期：day/week/month',
  `cron_expr`     VARCHAR(64)  DEFAULT NULL COMMENT '定时表达式（cron，按东八区）',
  `enabled`       TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '是否启用：1启用 0停用',
  `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_report_code` (`report_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报告配置表';

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
DROP TABLE IF EXISTS `report_record`;
CREATE TABLE `report_record` (
  `id`                  BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  `report_config_id`    BIGINT       NOT NULL COMMENT '报告配置ID',
  `report_code`         VARCHAR(64)  NOT NULL COMMENT '报告代码',
  `idempotency_key`     VARCHAR(128) NOT NULL COMMENT '幂等键：report_code+时间窗+版本',
  `start_time`          DATETIME     NOT NULL COMMENT '统计起始时间（UTC）',
  `end_time`            DATETIME     NOT NULL COMMENT '统计截止时间（UTC）',
  `timezone`            VARCHAR(32)  NOT NULL DEFAULT 'UTC' COMMENT '统计时区',
  `data_snapshot_at`    DATETIME     DEFAULT NULL COMMENT '数据快照时间',
  `version`             VARCHAR(32)  NOT NULL DEFAULT 'v1' COMMENT '生成版本',
  `source_record_count` INT          NOT NULL DEFAULT 0 COMMENT '来源记录数',
  `report_content`      LONGTEXT     DEFAULT NULL COMMENT '报告正文（结构化文本）',
  `metric_json`         JSON         DEFAULT NULL COMMENT '可复算指标快照（JSON）',
  `status`              VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT '状态：pending/running/success/failed',
  `fail_reason`         TEXT         DEFAULT NULL COMMENT '失败原因',
  `generated_at`        DATETIME     DEFAULT NULL COMMENT '生成完成时间',
  `created_at`          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_idempotency_key` (`idempotency_key`),
  KEY `idx_report_code_time` (`report_code`, `start_time`, `end_time`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报告生成记录表';

-- ----------------------------------------------------------------------------
-- 3. 报告指标明细表 report_metric（支撑"指标可复算"）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `report_metric`;
CREATE TABLE `report_metric` (
  `id`               BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  `report_record_id` BIGINT        NOT NULL COMMENT '报告记录ID',
  `metric_code`      VARCHAR(64)   NOT NULL COMMENT '指标代码',
  `metric_name`      VARCHAR(128)  NOT NULL COMMENT '指标名称',
  `metric_value`     DECIMAL(20,4) DEFAULT NULL COMMENT '指标数值（数值型）',
  `metric_text`      TEXT          DEFAULT NULL COMMENT '指标文本值（非数值型）',
  `metric_unit`      VARCHAR(32)   DEFAULT NULL COMMENT '单位',
  `calc_rule`        TEXT          DEFAULT NULL COMMENT '计算口径/规则说明',
  `period_type`      VARCHAR(16)   DEFAULT NULL COMMENT '周期类型：day/week/month',
  `created_at`       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_report_record_id` (`report_record_id`),
  KEY `idx_metric_code` (`metric_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报告指标明细表';

-- ============================================================================
-- 附录：报告依赖的上游数据表补充建议（属于企业/学生助手模块，报告模块只读）
-- 说明：以下字段当前表结构缺失，会导致"全域客户经营分析""投诉处理周报"
--       指标无法精确计算，需在对应模块建表时补齐，报告模块不重复建表。
-- ============================================================================
-- 1) intention_customer（意向客户表）补充成交/流失字段：
--    ALTER TABLE `intention_customer`
--      ADD COLUMN `deal_amount`  DECIMAL(20,2) DEFAULT NULL COMMENT '成交金额',
--      ADD COLUMN `deal_at`      DATETIME      DEFAULT NULL COMMENT '成交时间',
--      ADD COLUMN `lost_at`      DATETIME      DEFAULT NULL COMMENT '流失时间',
--      ADD COLUMN `lost_reason`  VARCHAR(255)  DEFAULT NULL COMMENT '流失原因';
-- 2) 新增独立跟进记录表 customer_follow_up（支持转化路径/历史查询）：
--    CREATE TABLE `customer_follow_up` (
--      `id`          BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键',
--      `customer_id` BIGINT      NOT NULL COMMENT '意向客户ID',
--      `follow_at`   DATETIME    NOT NULL COMMENT '跟进时间',
--      `content`     TEXT        DEFAULT NULL COMMENT '跟进内容',
--      `created_at`  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
--      PRIMARY KEY (`id`),
--      KEY `idx_customer_id` (`customer_id`)
--    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客户跟进记录表';
-- 3) 统一投诉工单事实源（complaint_feedback 与 after_sales_ticket 二选一），
--    补充首响/结案/满意度字段：
--    ALTER TABLE `after_sales_ticket`
--      ADD COLUMN `first_response_at` DATETIME     DEFAULT NULL COMMENT '首次响应时间',
--      ADD COLUMN `closed_at`         DATETIME     DEFAULT NULL COMMENT '结案时间',
--      ADD COLUMN `satisfaction`      TINYINT      DEFAULT NULL COMMENT '满意度(1-5)',
--      ADD COLUMN `category`          VARCHAR(64)  DEFAULT NULL COMMENT '投诉分类';
-- ============================================================================
