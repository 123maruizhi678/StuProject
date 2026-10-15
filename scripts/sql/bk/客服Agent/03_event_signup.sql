-- =====================================================================
-- 03. 活动报名表 event_signup
-- 用途：存储客户对活动的报名记录，强约束防重复报名
-- 执行顺序：3（依赖 lecture_event）
-- 前置：必须先执行 02_lecture_event.sql
-- =====================================================================

DROP TABLE IF EXISTS `event_signup`;

CREATE TABLE `event_signup` (
    `id`             BIGINT       NOT NULL AUTO_INCREMENT             COMMENT '主键，自增',
    `event_id`       BIGINT       NOT NULL                            COMMENT '活动ID',
    `customer_name`  VARCHAR(64)  NOT NULL                            COMMENT '客户姓名',
    `customer_phone` VARCHAR(32)  NOT NULL                            COMMENT '客户手机号',
    `customer_info`  JSON         NULL                                COMMENT '客户扩展信息（意向国家、学历等）',
    `signup_time`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '报名时间',
    `source`         VARCHAR(32)  NOT NULL DEFAULT '客服对话'          COMMENT '来源渠道',
    `status`         VARCHAR(16)  NOT NULL DEFAULT '有效'             COMMENT '状态：有效/取消',
    `created_at`     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_event_phone` (`event_id`, `customer_phone`) COMMENT '防重复报名',
    KEY `idx_event_status`  (`event_id`, `status`),
    KEY `idx_signup_time`   (`signup_time`),
    CONSTRAINT `fk_signup_event` FOREIGN KEY (`event_id`) REFERENCES `lecture_event` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='活动报名表';
