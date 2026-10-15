-- =====================================================================
-- 04. FAQ 问答对表 faq
-- 用途：FAQ 兜底查询（主流程走 Dify 知识库问答对匹配，此表作为后端备份）
-- 执行顺序：4（无依赖）
-- =====================================================================

DROP TABLE IF EXISTS `faq`;

CREATE TABLE `faq` (
    `id`         BIGINT      NOT NULL AUTO_INCREMENT              COMMENT '主键，自增',
    `question`   TEXT        NOT NULL                             COMMENT '问题',
    `answer`     TEXT        NOT NULL                             COMMENT '答案',
    `category`   VARCHAR(32) NOT NULL DEFAULT ''                  COMMENT '分类',
    `created_at` DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP   COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='FAQ 问答对表（兜底查询）';
