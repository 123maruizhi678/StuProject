-- =====================================================================
-- 06. 客服消息表 chat_message
-- 用途：存储客服对话中每一条 user / assistant 消息，用于回放与审计
-- 执行顺序：6（依赖 chat_session.session_id）
-- 前置：必须先执行 05_chat_session.sql
-- =====================================================================

DROP TABLE IF EXISTS `chat_message`;

CREATE TABLE `chat_message` (
    `id`         BIGINT       NOT NULL AUTO_INCREMENT            COMMENT '主键，自增',
    `session_id` VARCHAR(64)  NOT NULL                           COMMENT '关联会话（FK → chat_session.session_id）',
    `role`       VARCHAR(16)  NOT NULL                           COMMENT 'user / assistant',
    `intent`     VARCHAR(32)  NOT NULL DEFAULT ''                COMMENT '意图标签（由 Dify 返回）',
    `content`    TEXT         NOT NULL                           COMMENT '消息内容',
    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_session_time` (`session_id`, `created_at`),
    KEY `idx_intent`       (`intent`),
    CONSTRAINT `fk_message_session` FOREIGN KEY (`session_id`) REFERENCES `chat_session` (`session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客服消息表';
