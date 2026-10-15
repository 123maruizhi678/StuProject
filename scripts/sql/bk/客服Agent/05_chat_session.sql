-- =====================================================================
-- 05. 客服会话表 chat_session
-- 用途：存储客服对话的会话元信息（每次访客进入产生一条 session）
-- 执行顺序：5（无依赖，但被 chat_message 引用）
-- =====================================================================

DROP TABLE IF EXISTS `chat_session`;

CREATE TABLE `chat_session` (
    `id`         BIGINT       NOT NULL AUTO_INCREMENT            COMMENT '主键，自增',
    `session_id` VARCHAR(64)  NOT NULL                           COMMENT '会话唯一标识（UUID）',
    `user_id`    VARCHAR(64)  NOT NULL DEFAULT ''                COMMENT '访客标识（匿名或留资后）',
    `channel`    VARCHAR(32)  NOT NULL DEFAULT 'web'             COMMENT '渠道（web 等）',
    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                       ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_session_id` (`session_id`),
    KEY `idx_user_id`    (`user_id`),
    KEY `idx_updated_at` (`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客服会话表';
