-- =============================================================
-- 客服 Agent 六表独立建表脚本（测试/独立库用）
-- 提取自：开发文档/操作文档_数据库建表语句.sql 的 006—011 段
-- 含两条客服外键：fk_signup_event（event_signup→lecture_event）、
--               fk_message_session（chat_message→chat_session）
-- 用法：CREATE DATABASE 后 USE 新库，再执行本文件；
--       面向空库，不包含 DROP/TRUNCATE；重复执行会因表已存在报错。
-- =============================================================

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;
SET SESSION time_zone = '+00:00';

-- 006. course_project：招生课程／项目资料及推荐数据；共10个字段。
CREATE TABLE `course_project` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `course_name` VARCHAR(128) NOT NULL COMMENT '课程名称',
  `category` VARCHAR(32) NOT NULL COMMENT '类别：留学申请/背景提升/语言培训',
  `target_audience` VARCHAR(128) NOT NULL DEFAULT '' COMMENT '适用人群（学历/意向国家等）',
  `description` TEXT NOT NULL COMMENT '课程简介',
  `location` VARCHAR(128) NOT NULL DEFAULT '' COMMENT '上课地点',
  `signup_method` VARCHAR(128) NOT NULL DEFAULT '' COMMENT '报名方式',
  `status` VARCHAR(32) NOT NULL DEFAULT '上架' COMMENT '状态：上架/下架（仅上架对访客可见）',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_category_status` (`category`, `status`),
  KEY `idx_status_time` (`status`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='招生课程／项目资料及推荐数据';

-- 007. lecture_event：讲座／活动资料、报名状态及名额；共11个字段。
CREATE TABLE `lecture_event` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `event_name` VARCHAR(128) NOT NULL COMMENT '活动名称',
  `event_type` VARCHAR(16) NOT NULL COMMENT '线上/线下',
  `start_time` DATETIME NOT NULL COMMENT '开始时间',
  `location` VARCHAR(128) NOT NULL DEFAULT '' COMMENT '地点',
  `signup_method` VARCHAR(128) NOT NULL DEFAULT '' COMMENT '报名方式',
  `quota` INT NOT NULL DEFAULT 0 COMMENT '名额（0 表示不限）',
  `signed_count` INT NOT NULL DEFAULT 0 COMMENT '已报名人数',
  `status` VARCHAR(32) NOT NULL DEFAULT '报名中' COMMENT '状态：报名中/已满/已结束',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_status_start` (`status`, `start_time`),
  KEY `idx_start_time` (`start_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='讲座／活动资料、报名状态及名额';

-- 008. event_signup：活动报名记录、留资及有效／取消状态；共9个字段。
-- 采用状态式判重，不建(event_id,customer_phone)永久唯一键。
CREATE TABLE `event_signup` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `event_id` BIGINT NOT NULL COMMENT '活动ID（外键 → `lecture_event.id`）',
  `customer_name` VARCHAR(64) NOT NULL COMMENT '客户姓名',
  `customer_phone` VARCHAR(32) NOT NULL COMMENT '客户手机号（判重依据）',
  `customer_info` JSON NULL DEFAULT NULL COMMENT '客户扩展信息（意向国家、学历等）',
  `signup_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '报名时间',
  `source` VARCHAR(32) NOT NULL DEFAULT '客服对话' COMMENT '来源渠道',
  `status` VARCHAR(32) NOT NULL DEFAULT '有效' COMMENT '状态：有效/取消',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_event_status` (`event_id`, `status`),
  KEY `idx_signup_time` (`signup_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='活动报名记录、留资及有效／取消状态';

-- 009. faq：高频标准问答及数据库兜底；共5个字段。
CREATE TABLE `faq` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `question` TEXT NOT NULL COMMENT '问题',
  `answer` TEXT NOT NULL COMMENT '答案',
  `category` VARCHAR(32) NOT NULL DEFAULT '' COMMENT '分类',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='高频标准问答及数据库兜底';

-- 010. chat_session：访客客服会话；共6个字段。
CREATE TABLE `chat_session` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `session_id` VARCHAR(64) NOT NULL COMMENT '会话唯一标识（UUID），唯一索引 uk_session_id',
  `user_id` VARCHAR(64) NOT NULL DEFAULT '' COMMENT '访客标识（匿名或留资后）',
  `channel` VARCHAR(32) NOT NULL DEFAULT 'web' COMMENT '渠道（web 等）',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_session_id` (`session_id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_updated_at` (`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='访客客服会话';

-- 011. chat_message：客服用户／助手消息、意图及对话历史；共6个字段。
CREATE TABLE `chat_message` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `session_id` VARCHAR(64) NOT NULL COMMENT '关联会话（外键 → `chat_session.session_id`）',
  `role` VARCHAR(16) NOT NULL COMMENT '消息角色：user表示用户，assistant表示助手',
  `intent` VARCHAR(32) NOT NULL DEFAULT '' COMMENT '意图标签（由 Dify 返回；兜底时为空）',
  `content` TEXT NOT NULL COMMENT '消息内容',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_session_time` (`session_id`, `created_at`),
  KEY `idx_intent` (`intent`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='客服用户／助手消息、意图及对话历史';

-- ---------- 客服外键（全部 RESTRICT，不级联删除业务历史） ----------
ALTER TABLE `event_signup` ADD CONSTRAINT `fk_signup_event` FOREIGN KEY (`event_id`) REFERENCES `lecture_event` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `chat_message` ADD CONSTRAINT `fk_message_session` FOREIGN KEY (`session_id`) REFERENCES `chat_session` (`session_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
