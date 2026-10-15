-- =====================================================================
-- 01. 课程项目表 course_project
-- 用途：存储课程/项目信息，供"课程与项目推荐"场景查询与推荐条件筛选
-- 执行顺序：1（无外键依赖）
-- =====================================================================

DROP TABLE IF EXISTS `course_project`;

CREATE TABLE `course_project` (
    `id`              BIGINT       NOT NULL AUTO_INCREMENT          COMMENT '主键，自增',
    `course_name`     VARCHAR(128) NOT NULL                         COMMENT '课程名称',
    `category`        VARCHAR(32)  NOT NULL                         COMMENT '类别：留学申请/背景提升/语言培训',
    `target_audience` VARCHAR(128) NOT NULL DEFAULT ''              COMMENT '适用人群（学历/意向国家等）',
    `description`     TEXT         NOT NULL                         COMMENT '课程简介',
    `location`        VARCHAR(128) NOT NULL DEFAULT ''              COMMENT '上课地点',
    `signup_method`   VARCHAR(128) NOT NULL DEFAULT ''              COMMENT '报名方式',
    `status`          VARCHAR(16)  NOT NULL DEFAULT '上架'           COMMENT '状态：上架/下架',
    `created_at`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                          ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_category_status` (`category`, `status`),
    KEY `idx_status_time`     (`status`,    `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='课程项目表';
