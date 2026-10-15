-- =====================================================================
-- 02. 讲座活动表 lecture_event
-- 用途：存储近期线上/线下讲座与招生官见面会，是"活动与讲座报名"场景的主表
-- 执行顺序：2（无外键依赖，但被 event_signup 引用）
-- =====================================================================

DROP TABLE IF EXISTS `lecture_event`;

CREATE TABLE `lecture_event` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT            COMMENT '主键，自增',
    `event_name`    VARCHAR(128) NOT NULL                           COMMENT '活动名称',
    `event_type`    VARCHAR(16)  NOT NULL                           COMMENT '线上/线下',
    `start_time`    DATETIME     NOT NULL                           COMMENT '开始时间',
    `location`      VARCHAR(128) NOT NULL DEFAULT ''                COMMENT '地点',
    `signup_method` VARCHAR(128) NOT NULL DEFAULT ''                COMMENT '报名方式',
    `quota`         INT          NOT NULL DEFAULT 0                 COMMENT '名额（0 表示不限）',
    `signed_count`  INT          NOT NULL DEFAULT 0                 COMMENT '已报名人数',
    `status`        VARCHAR(16)  NOT NULL DEFAULT '报名中'           COMMENT '状态：报名中/已满/已结束',
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                        ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_status_start` (`status`, `start_time`),
    KEY `idx_start_time`   (`start_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='讲座活动表';
