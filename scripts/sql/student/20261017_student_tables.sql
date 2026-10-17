-- 操作文档048最终口径优先：本地权威synced_at不适用时NULL，修正源建表SQL的NOT NULL差异。
-- 来自开发文档最终DDL；仅用于缺失学生表，已有表必须先比对，不执行DROP/TRUNCATE。
SET time_zone = '+00:00';

CREATE TABLE `mental_health_profile` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '记录主键；评估主键ID',
  `student_id` BIGINT NOT NULL COMMENT '所属学生编号；学生ID，关联student_profile.student_id',
  `emotion_tag` VARCHAR(50) NOT NULL COMMENT '情绪标签；本次情绪标签',
  `emotion_score` NUMERIC(5, 2) NOT NULL COMMENT '情绪平稳评分；分值0至100，越高表示情绪越平稳；不代表医学诊断',
  `history_data` JSON NULL DEFAULT NULL COMMENT '历史数据（兼容字段）；旧历史JSON兼容字段；新记录保持NULL；新记录保持空值，不作为新历史存储',
  `risk_level` VARCHAR(20) NOT NULL COMMENT '风险等级；评估风险：low/medium/high/critical',
  `observed_at` DATETIME(6) NOT NULL COMMENT '消息评估时间；源消息发生时间，UTC；区别于入库时间',
  `source_event_id` VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '源消息事件编号；可信入口生成的源事件ID，重试时复用',
  `workflow_run_id` VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NULL DEFAULT NULL COMMENT '智能体运行编号；Dify工作流运行ID，仅用于追溯',
  `analysis_version` VARCHAR(64) NOT NULL COMMENT '评估配置版本；心理分析配置版本，明确分值和风险口径',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间；创建时间，UTC',
  PRIMARY KEY (id),
  UNIQUE KEY uk_profile_source (student_id, source_event_id),
  UNIQUE KEY uk_profile_owner (id, student_id),
  KEY idx_profile_history (student_id, observed_at),
  KEY idx_profile_report (observed_at, risk_level),
  CONSTRAINT ck_profile_score CHECK (emotion_score >= 0 AND emotion_score <= 100),
  CONSTRAINT ck_profile_risk CHECK (risk_level IN ('low', 'medium', 'high', 'critical'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学生心理辅助评估历史';

CREATE TABLE `mental_warning` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '记录主键；预警主键ID',
  `student_id` BIGINT NOT NULL COMMENT '所属学生编号；学生ID，关联student_profile.student_id',
  `profile_id` BIGINT NOT NULL COMMENT '关联评估记录编号；触发评估ID，与student_id组成画像外键',
  `trigger_reason` TEXT NOT NULL COMMENT '预警触发依据；必要的触发依据，仅授权处理人可见',
  `risk_level` VARCHAR(20) NOT NULL COMMENT '风险等级；预警等级：high/critical',
  `follower_status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '人工处理状态；人工处理状态：pending/processing/closed',
  `follower_id` BIGINT NULL DEFAULT NULL COMMENT '负责处理老师编号；处理员工ID，关联employee.employee_id；未分派可空',
  `acknowledged_at` DATETIME(6) NULL DEFAULT NULL COMMENT '人工接手时间；真实人工接手时间，UTC',
  `closed_at` DATETIME(6) NULL DEFAULT NULL COMMENT '人工关闭时间；人工关闭时间，UTC',
  `handling_result` TEXT NULL DEFAULT NULL COMMENT '人工处置结果；最终人工处置结果；关闭时不能为空',
  `version` INTEGER NOT NULL DEFAULT 1 COMMENT '并发版本号；并发版本，业务更新时条件校验并递增',
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近修改时间；最近修改时间，UTC',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间；创建时间，UTC',
  PRIMARY KEY (id),
  UNIQUE KEY uk_warning_profile (profile_id),
  KEY idx_warning_student (student_id, created_at),
  KEY idx_warning_follower (follower_id, follower_status, created_at),
  CONSTRAINT ck_warning_risk CHECK (risk_level IN ('high', 'critical')),
  CONSTRAINT ck_warning_status CHECK (follower_status IN ('pending', 'processing', 'closed')),
  CONSTRAINT ck_warning_closed CHECK (follower_status <> 'closed' OR (follower_id IS NOT NULL AND acknowledged_at IS NOT NULL AND closed_at IS NOT NULL AND handling_result IS NOT NULL)),
  CONSTRAINT ck_warning_version CHECK (version >= 1),
  KEY `idx_fk_joint_41` (`profile_id`,`student_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学生心理预警、人工接手及处置';

CREATE TABLE `student_academic_event` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '记录主键；学业节点主键ID',
  `student_id` BIGINT NOT NULL COMMENT '所属学生编号；学生ID，关联student_profile.student_id',
  `source_system` VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '来源系统编码；教务来源编码，如education',
  `external_event_id` VARCHAR(128) COLLATE utf8mb4_bin NOT NULL COMMENT '外部学业节点编号；源系统节点ID，与学生和来源组成同步唯一键',
  `event_type` VARCHAR(20) NOT NULL COMMENT '学业节点类型；节点类型：ddl截止日期/exam考试',
  `title` VARCHAR(200) NOT NULL COMMENT '学业节点标题；论文或考试标题',
  `due_at` DATETIME(6) NOT NULL COMMENT '截止或考试时间；准确截止或考试时点，UTC',
  `source_timezone` VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai' COMMENT '来源时区；来源IANA时区，如Asia/Shanghai',
  `event_status` VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '学业节点状态；节点状态：active/cancelled',
  `event_version` INTEGER NOT NULL DEFAULT 1 COMMENT '学业节点版本；节点时间或有效状态改变时递增的提醒版本',
  `source_updated_at` DATETIME(6) NULL DEFAULT NULL COMMENT '源系统更新时间；源系统更新时间，UTC；防止旧消息覆盖新节点',
  `synced_at` DATETIME(6) NULL DEFAULT NULL COMMENT '最近成功同步时间；最后成功同步时间，UTC；用于展示数据新鲜度',
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近修改时间；最近修改时间，UTC',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间；创建时间，UTC',
  PRIMARY KEY (id),
  UNIQUE KEY uk_academic_source (student_id, source_system, external_event_id),
  UNIQUE KEY uk_academic_owner (id, student_id),
  KEY idx_academic_student (student_id, event_status, due_at),
  CONSTRAINT ck_academic_type CHECK (event_type IN ('ddl', 'exam')),
  CONSTRAINT ck_academic_status CHECK (event_status IN ('active', 'cancelled')),
  CONSTRAINT ck_academic_version CHECK (event_version >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学生课程相关考试／DDL等学业节点';

CREATE TABLE `student_academic_reminder` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '记录主键；提醒主键ID',
  `student_id` BIGINT NOT NULL COMMENT '所属学生编号；节点所属学生，通过组合外键关联同一学生',
  `academic_event_id` BIGINT NOT NULL COMMENT '关联学业节点编号；学业节点ID，组合关联student_academic_event',
  `lead_minutes` INTEGER NOT NULL COMMENT '提前提醒分钟数；提前分钟数；1440为一天，0为到点提醒',
  `notify_at` DATETIME(6) NOT NULL COMMENT '计划提醒时间；计划提醒时点，UTC；由节点时间减提前量计算',
  `event_version` INTEGER NOT NULL COMMENT '学业节点版本；对应节点版本，发送前须检查仍一致',
  `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '提醒执行状态；pending待执行/queued已入队/sent已投递/cancelled已取消',
  `sent_at` DATETIME(6) NULL DEFAULT NULL COMMENT '成功投递时间；当前版本实际成功发送时间，UTC',
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '提醒设置代次时间，UTC，保留六位微秒；仅设置、取消、节点重排时显式更新，投递和重试不得自动刷新',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间；创建时间，UTC',
  PRIMARY KEY (id),
  UNIQUE KEY uk_reminder_setting (student_id, academic_event_id, lead_minutes),
  KEY idx_reminder_due (status, notify_at),
  CONSTRAINT ck_reminder_lead CHECK (lead_minutes >= 0),
  CONSTRAINT ck_reminder_version CHECK (event_version >= 1),
  CONSTRAINT ck_reminder_status CHECK (status IN ('pending', 'queued', 'sent', 'cancelled')),
  CONSTRAINT ck_reminder_sent CHECK (status <> 'sent' OR sent_at IS NOT NULL),
  KEY `idx_fk_joint_42` (`academic_event_id`,`student_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学业提醒设置、取消、重排及执行状态';

CREATE TABLE `student_application_progress` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '记录主键；阶段进度主键ID',
  `student_id` BIGINT NOT NULL COMMENT '所属学生编号；学生ID，关联student_profile.student_id',
  `source_system` VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '来源系统编码；CRM或申请系统来源编码',
  `external_application_id` VARCHAR(128) COLLATE utf8mb4_bin NOT NULL COMMENT '外部申请编号；源系统申请ID，用于区分不同院校和项目',
  `application_name` VARCHAR(200) NOT NULL COMMENT '申请项目名称；院校或申请项目展示名称',
  `stage_code` VARCHAR(32) NOT NULL COMMENT '申请阶段编码；document_review文书/school_application院校/visa_process签证',
  `stage_status` VARCHAR(64) NOT NULL COMMENT '申请阶段状态；外部契约映射的阶段状态，不由AI臆造',
  `detail` VARCHAR(500) NULL DEFAULT NULL COMMENT '申请进度说明；必要进度说明，如需补充材料',
  `source_updated_at` DATETIME(6) NULL DEFAULT NULL COMMENT '源系统更新时间；源系统更新时间，UTC',
  `synced_at` DATETIME(6) NULL DEFAULT NULL COMMENT '最近成功同步时间；最后成功同步时间，UTC；失败不刷新',
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近修改时间；最近修改时间，UTC',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间；创建时间，UTC',
  PRIMARY KEY (id),
  UNIQUE KEY uk_progress_stage (student_id, source_system, external_application_id, stage_code),
  KEY idx_progress_student (student_id, synced_at),
  CONSTRAINT ck_progress_stage CHECK (stage_code IN ('document_review', 'school_application', 'visa_process'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学生留学申请阶段及最新进度';

CREATE TABLE `student_assistant_session` (
  `session_id` VARCHAR(64) COLLATE utf8mb4_bin NOT NULL COMMENT '会话编号；会话唯一标识',
  `student_id` BIGINT NOT NULL COMMENT '所属学生编号；所属学生内部主键',
  `version` INTEGER NOT NULL DEFAULT 1 COMMENT '并发版本号；会话并发版本号',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间；创建时间（UTC）',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最近修改时间；最近更新时间（UTC）',
  PRIMARY KEY (`session_id`),
  UNIQUE KEY `uq_assistant_session_owner` (`session_id`,`student_id`),
  KEY `idx_assistant_session_student` (`student_id`,`updated_at`),
  CONSTRAINT `ck_assistant_session_version` CHECK (`version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学生助手会话归属及并发版本';

CREATE TABLE `student_assistant_turn` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '记录主键；对话轮次主键',
  `session_id` VARCHAR(64) COLLATE utf8mb4_bin NOT NULL COMMENT '会话编号；会话唯一标识',
  `student_id` BIGINT NOT NULL COMMENT '所属学生编号；所属学生内部主键',
  `request_key` VARCHAR(128) NOT NULL COMMENT '请求幂等键摘要；本次请求幂等键摘要',
  `parameters_hash` VARCHAR(64) NOT NULL COMMENT '请求参数摘要；规范化请求正文摘要',
  `message` TEXT NOT NULL COMMENT '学生消息正文；学生本轮消息文本',
  `result` JSON NULL DEFAULT NULL COMMENT '本轮响应与回执；本轮响应及业务预览回执（JSON）',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间；创建时间（UTC）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_assistant_turn_request` (`student_id`,`request_key`),
  KEY `idx_assistant_turn_session_owner` (`session_id`,`student_id`),
  KEY `idx_assistant_turn_history` (`session_id`,`created_at`,`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学生助手对话轮次、请求去重及结果回执';

ALTER TABLE `mental_health_profile` ADD CONSTRAINT `fk_joint_34` FOREIGN KEY (`student_id`) REFERENCES `student_profile` (`student_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `mental_warning` ADD CONSTRAINT `fk_joint_35` FOREIGN KEY (`student_id`) REFERENCES `student_profile` (`student_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `mental_warning` ADD CONSTRAINT `fk_joint_36` FOREIGN KEY (`follower_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `student_academic_event` ADD CONSTRAINT `fk_joint_37` FOREIGN KEY (`student_id`) REFERENCES `student_profile` (`student_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `student_application_progress` ADD CONSTRAINT `fk_joint_38` FOREIGN KEY (`student_id`) REFERENCES `student_profile` (`student_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `student_assistant_session` ADD CONSTRAINT `fk_joint_39` FOREIGN KEY (`student_id`) REFERENCES `student_profile` (`student_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `student_assistant_turn` ADD CONSTRAINT `fk_joint_40` FOREIGN KEY (`student_id`) REFERENCES `student_profile` (`student_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `mental_warning` ADD CONSTRAINT `fk_joint_41` FOREIGN KEY (`profile_id`,`student_id`) REFERENCES `mental_health_profile` (`id`,`student_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `student_academic_reminder` ADD CONSTRAINT `fk_joint_42` FOREIGN KEY (`academic_event_id`,`student_id`) REFERENCES `student_academic_event` (`id`,`student_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `student_assistant_turn` ADD CONSTRAINT `fk_joint_43` FOREIGN KEY (`session_id`,`student_id`) REFERENCES `student_assistant_session` (`session_id`,`student_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
