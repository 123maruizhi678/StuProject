-- 学生智能助手建表方案 V1.0（2026-10-14）
-- 用途：供评审/空白测试库初始化；尚未连接或执行任何数据库。
-- 基线：MySQL >= 8.0.16，InnoDB，utf8mb4，应用和连接均使用 UTC。
-- shared student_identity / notification / action 如已有等价表，应先适配再执行。
-- 所有表须不存在；故意不使用 IF NOT EXISTS，避免把旧结构误当成新结构。
-- 不创建数据库、不选择数据库、不创建用户、不改写项目.env。
-- 已有表和数据须采用独立 ALTER/Alembic 迁移，不能用本文件自动升级。
-- MySQL DDL不构成可整体回滚事务；初始化中断后必须核对已创建结构。
SET NAMES utf8mb4;
SET time_zone = '+00:00';

-- 学生身份与责任老师映射；共享前置（无等价表时补建）
CREATE TABLE student_identity (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  student_no VARCHAR(64) COLLATE utf8mb4_bin NOT NULL COMMENT '统一学号/业务编号',
  student_name VARCHAR(100) NOT NULL COMMENT '学生显示姓名',
  teacher_id BIGINT NULL COMMENT '责任老师统一员工ID',
  edu_student_id VARCHAR(128) COLLATE utf8mb4_bin NULL COMMENT '教务系统学生ID',
  crm_student_id VARCHAR(128) COLLATE utf8mb4_bin NULL COMMENT 'CRM系统学生ID',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间（UTC）',
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最后更新时间（UTC）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_student_no (student_no),
  UNIQUE KEY uk_edu_student (edu_student_id),
  UNIQUE KEY uk_crm_student (crm_student_id),
  KEY idx_student_teacher (teacher_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学生身份与责任老师映射';

-- 学生行政服务；扩展原表
CREATE TABLE student_admin_service (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  student_id BIGINT NOT NULL COMMENT '统一学生ID',
  apply_type VARCHAR(20) NOT NULL COMMENT '申请类型 leave/academic',
  apply_content TEXT NOT NULL COMMENT '申请理由/内容',
  approval_status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '审批状态 pending/approved/rejected/cancelled',
  edu_related_data JSON NULL COMMENT '考务关联扩展信息',
  leave_start_at DATETIME(6) NULL COMMENT '请假开始时间（UTC）',
  leave_end_at DATETIME(6) NULL COMMENT '请假结束时间（UTC）',
  reviewer_id BIGINT NULL COMMENT '指定/实际审批老师ID',
  reviewed_at DATETIME(6) NULL COMMENT '审批发生时间（UTC）',
  approval_comment TEXT NULL COMMENT '审批意见/驳回原因',
  request_key VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '请求幂等键',
  request_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '规范化请求SHA-256',
  version INT NOT NULL DEFAULT 1 COMMENT '乐观锁版本',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间（UTC）',
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最后更新时间（UTC）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_admin_request (student_id, request_key),
  KEY idx_admin_student (student_id, created_at),
  KEY idx_admin_review (reviewer_id, approval_status, created_at),
  CONSTRAINT fk_admin_student FOREIGN KEY (student_id) REFERENCES student_identity(id),
  CONSTRAINT ck_admin_type CHECK (apply_type IN ('leave', 'academic')),
  CONSTRAINT ck_admin_status CHECK (approval_status IN ('pending', 'approved', 'rejected', 'cancelled')),
  CONSTRAINT ck_admin_leave CHECK (apply_type <> 'leave' OR (leave_start_at IS NOT NULL AND leave_end_at IS NOT NULL AND leave_end_at > leave_start_at)),
  CONSTRAINT ck_admin_decision CHECK (approval_status NOT IN ('approved', 'rejected') OR (reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL)),
  CONSTRAINT ck_admin_version CHECK (version >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学生行政服务';

-- 心理评估历史记录（沿用画像表名）；扩展原表并明确粒度
CREATE TABLE mental_health_profile (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  student_id BIGINT NOT NULL COMMENT '统一学生ID',
  emotion_tag VARCHAR(50) NOT NULL COMMENT '情绪标签',
  emotion_score DECIMAL(5,2) NOT NULL COMMENT '情绪分值0～100，越高表示状态越平稳',
  history_data JSON NULL COMMENT '旧历史JSON兼容字段',
  risk_level VARCHAR(20) NOT NULL COMMENT '本次风险 low/medium/high/critical',
  observed_at DATETIME(6) NOT NULL COMMENT '被评估消息发生时间（UTC）',
  source_event_id VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '本次源消息/事件ID',
  workflow_run_id VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NULL COMMENT 'Dify工作流运行ID',
  analysis_version VARCHAR(64) NOT NULL COMMENT '心理分析配置版本',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间（UTC）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_profile_source (student_id, source_event_id),
  UNIQUE KEY uk_profile_owner (id, student_id),
  KEY idx_profile_history (student_id, observed_at),
  KEY idx_profile_report (observed_at, risk_level),
  CONSTRAINT fk_profile_student FOREIGN KEY (student_id) REFERENCES student_identity(id),
  CONSTRAINT ck_profile_score CHECK (emotion_score >= 0 AND emotion_score <= 100),
  CONSTRAINT ck_profile_risk CHECK (risk_level IN ('low', 'medium', 'high', 'critical'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='心理评估历史记录（沿用画像表名）';

-- 心理预警与处置；扩展原表
CREATE TABLE mental_warning (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  student_id BIGINT NOT NULL COMMENT '统一学生ID',
  profile_id BIGINT NOT NULL COMMENT '触发预警的评估ID',
  trigger_reason TEXT NOT NULL COMMENT '必要的预警原因',
  risk_level VARCHAR(20) NOT NULL COMMENT '预警风险 high/critical',
  follower_status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '人工跟进状态 pending/processing/closed',
  follower_id BIGINT NULL COMMENT '负责老师统一员工ID',
  acknowledged_at DATETIME(6) NULL COMMENT '老师确认接手时间（UTC）',
  closed_at DATETIME(6) NULL COMMENT '人工关闭时间（UTC）',
  handling_result TEXT NULL COMMENT '人工处置结果',
  version INT NOT NULL DEFAULT 1 COMMENT '乐观锁版本',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间（UTC）',
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最后更新时间（UTC）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_warning_profile (profile_id),
  KEY idx_warning_student (student_id, created_at),
  KEY idx_warning_follower (follower_id, follower_status, created_at),
  CONSTRAINT fk_warning_student FOREIGN KEY (student_id) REFERENCES student_identity(id),
  CONSTRAINT fk_warning_profile FOREIGN KEY (profile_id, student_id) REFERENCES mental_health_profile(id, student_id),
  CONSTRAINT ck_warning_risk CHECK (risk_level IN ('high', 'critical')),
  CONSTRAINT ck_warning_status CHECK (follower_status IN ('pending', 'processing', 'closed')),
  CONSTRAINT ck_warning_closed CHECK (follower_status <> 'closed' OR (follower_id IS NOT NULL AND acknowledged_at IS NOT NULL AND closed_at IS NOT NULL AND handling_result IS NOT NULL)),
  CONSTRAINT ck_warning_version CHECK (version >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='心理预警与处置';

-- 投诉与建议统一工单；扩展原表、企业/学生共用
CREATE TABLE after_sales_ticket (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  student_id BIGINT NOT NULL COMMENT '统一学生ID',
  feedback_type VARCHAR(20) NOT NULL DEFAULT 'complaint' COMMENT '反馈类型 complaint/suggestion',
  complaint_content TEXT NOT NULL COMMENT '反馈原始内容',
  summary VARCHAR(500) NULL COMMENT 'Dify生成的工单摘要',
  category VARCHAR(32) NOT NULL DEFAULT 'other' COMMENT 'visa/application/life/other',
  process_status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '处理状态 pending/processing/resolved/cancelled',
  follower_id BIGINT NULL COMMENT '工单负责人统一员工ID',
  first_response_at DATETIME(6) NULL COMMENT '首次人工响应时间（UTC）',
  resolved_at DATETIME(6) NULL COMMENT '最终解决时间（UTC）',
  solution TEXT NULL COMMENT '最终解决方案',
  satisfaction_score TINYINT NULL COMMENT '学生自愿评分1～5',
  request_key VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '请求幂等键',
  request_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '规范化请求SHA-256',
  version INT NOT NULL DEFAULT 1 COMMENT '乐观锁版本',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间（UTC）',
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最后更新时间（UTC）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_ticket_request (student_id, request_key),
  KEY idx_ticket_student (student_id, created_at),
  KEY idx_ticket_follower (follower_id, process_status, created_at),
  KEY idx_ticket_report (created_at, category),
  CONSTRAINT fk_ticket_student FOREIGN KEY (student_id) REFERENCES student_identity(id),
  CONSTRAINT ck_ticket_type CHECK (feedback_type IN ('complaint', 'suggestion')),
  CONSTRAINT ck_ticket_category CHECK (category IN ('visa', 'application', 'life', 'other')),
  CONSTRAINT ck_ticket_status CHECK (process_status IN ('pending', 'processing', 'resolved', 'cancelled')),
  CONSTRAINT ck_ticket_resolved CHECK (process_status <> 'resolved' OR (follower_id IS NOT NULL AND first_response_at IS NOT NULL AND resolved_at IS NOT NULL AND solution IS NOT NULL)),
  CONSTRAINT ck_ticket_score CHECK (satisfaction_score IS NULL OR (satisfaction_score BETWEEN 1 AND 5 AND process_status = 'resolved')),
  CONSTRAINT ck_ticket_version CHECK (version >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='投诉与建议统一工单';

-- 学生学业节点镜像；新增功能表
CREATE TABLE student_academic_event (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  student_id BIGINT NOT NULL COMMENT '统一学生ID',
  source_system VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '教务来源编码',
  external_event_id VARCHAR(128) COLLATE utf8mb4_bin NOT NULL COMMENT '外部节点ID',
  event_type VARCHAR(20) NOT NULL COMMENT 'ddl/exam',
  title VARCHAR(200) NOT NULL COMMENT '论文/考试标题',
  due_at DATETIME(6) NOT NULL COMMENT '节点时间（UTC）',
  source_timezone VARCHAR(64) NOT NULL COMMENT '来源IANA时区',
  event_status VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT 'active/cancelled',
  event_version INT NOT NULL DEFAULT 1 COMMENT '影响提醒的节点版本',
  source_updated_at DATETIME(6) NULL COMMENT '源系统更新时间（UTC）',
  synced_at DATETIME(6) NOT NULL COMMENT '最后成功同步时间（UTC）',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间（UTC）',
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最后更新时间（UTC）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_academic_source (student_id, source_system, external_event_id),
  UNIQUE KEY uk_academic_owner (id, student_id),
  KEY idx_academic_student (student_id, event_status, due_at),
  CONSTRAINT fk_academic_student FOREIGN KEY (student_id) REFERENCES student_identity(id),
  CONSTRAINT ck_academic_type CHECK (event_type IN ('ddl', 'exam')),
  CONSTRAINT ck_academic_status CHECK (event_status IN ('active', 'cancelled')),
  CONSTRAINT ck_academic_version CHECK (event_version >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学生学业节点镜像';

-- 学生学业提醒订阅与执行状态；新增功能表
CREATE TABLE student_academic_reminder (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  student_id BIGINT NOT NULL COMMENT '统一学生ID',
  academic_event_id BIGINT NOT NULL COMMENT '对应学业节点ID',
  lead_minutes INT NOT NULL COMMENT '提前分钟数',
  notify_at DATETIME(6) NOT NULL COMMENT '计划提醒时点（UTC）',
  event_version INT NOT NULL COMMENT '对应节点版本',
  status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/queued/sent/cancelled',
  sent_at DATETIME(6) NULL COMMENT '当前版本成功通知时间（UTC）',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间（UTC）',
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最后更新时间（UTC）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_reminder_setting (student_id, academic_event_id, lead_minutes),
  KEY idx_reminder_due (status, notify_at),
  CONSTRAINT fk_reminder_event FOREIGN KEY (academic_event_id, student_id) REFERENCES student_academic_event(id, student_id),
  CONSTRAINT ck_reminder_lead CHECK (lead_minutes >= 0),
  CONSTRAINT ck_reminder_version CHECK (event_version >= 1),
  CONSTRAINT ck_reminder_status CHECK (status IN ('pending', 'queued', 'sent', 'cancelled')),
  CONSTRAINT ck_reminder_sent CHECK (status <> 'sent' OR sent_at IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学生学业提醒订阅与执行状态';

-- 留学申请阶段最新镜像；新增功能表
CREATE TABLE student_application_progress (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  student_id BIGINT NOT NULL COMMENT '统一学生ID',
  source_system VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'CRM/申请系统来源',
  external_application_id VARCHAR(128) COLLATE utf8mb4_bin NOT NULL COMMENT '外部申请单ID',
  application_name VARCHAR(200) NOT NULL COMMENT '申请院校/项目展示名',
  stage_code VARCHAR(32) NOT NULL COMMENT 'document_review/school_application/visa_process',
  stage_status VARCHAR(64) NOT NULL COMMENT '源系统映射后的阶段状态',
  detail VARCHAR(500) NULL COMMENT '必要进度说明',
  source_updated_at DATETIME(6) NULL COMMENT '源系统更新时间（UTC）',
  synced_at DATETIME(6) NOT NULL COMMENT '最后成功同步时间（UTC）',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间（UTC）',
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最后更新时间（UTC）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_progress_stage (student_id, source_system, external_application_id, stage_code),
  KEY idx_progress_student (student_id, synced_at),
  CONSTRAINT fk_progress_student FOREIGN KEY (student_id) REFERENCES student_identity(id),
  CONSTRAINT ck_progress_stage CHECK (stage_code IN ('document_review', 'school_application', 'visa_process'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='留学申请阶段最新镜像';

-- 通知任务与收件记录；新增共享基础设施（可复用）
CREATE TABLE student_notification (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  student_id BIGINT NOT NULL COMMENT '统一学生ID',
  business_type VARCHAR(32) NOT NULL COMMENT '关联业务类型',
  business_id BIGINT NOT NULL COMMENT '关联业务记录ID',
  event_key VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '通知事件稳定去重键',
  recipient_type VARCHAR(20) NOT NULL COMMENT 'student/employee',
  recipient_id BIGINT NULL COMMENT '统一收件人ID',
  channel VARCHAR(20) NOT NULL DEFAULT 'in_app' COMMENT 'in_app/enterprise',
  content VARCHAR(500) NOT NULL COMMENT '最小必要通知内容',
  status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/processing/sent/failed/cancelled',
  attempts INT NOT NULL DEFAULT 0 COMMENT '尝试次数',
  next_retry_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '下次可尝试时间（UTC）',
  locked_until DATETIME(6) NULL COMMENT '处理租约截止（UTC）',
  provider_message_id VARCHAR(128) COLLATE utf8mb4_bin NULL COMMENT '外部渠道回执ID',
  last_error VARCHAR(500) NULL COMMENT '脱敏失败摘要',
  sent_at DATETIME(6) NULL COMMENT '实际投递成功时间（UTC）',
  read_at DATETIME(6) NULL COMMENT '收件人阅读时间（UTC）',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间（UTC）',
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最后更新时间（UTC）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_notification_event (event_key),
  KEY idx_notification_due (status, next_retry_at),
  KEY idx_notification_lease (status, locked_until),
  KEY idx_notification_inbox (recipient_type, recipient_id, status, created_at),
  KEY idx_notification_business (business_type, business_id),
  CONSTRAINT fk_notification_student FOREIGN KEY (student_id) REFERENCES student_identity(id),
  CONSTRAINT ck_notification_business CHECK (business_type IN ('administration', 'mental_warning', 'ticket', 'academic_reminder')),
  CONSTRAINT ck_notification_recipient CHECK (recipient_type IN ('student', 'employee')),
  CONSTRAINT ck_notification_channel CHECK (channel IN ('in_app', 'enterprise')),
  CONSTRAINT ck_notification_status CHECK (status IN ('pending', 'processing', 'sent', 'failed', 'cancelled')),
  CONSTRAINT ck_notification_attempts CHECK (attempts >= 0),
  CONSTRAINT ck_notification_sent CHECK (status <> 'sent' OR (recipient_id IS NOT NULL AND sent_at IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='通知任务与收件记录';

-- 学生服务操作与多轮跟进记录；新增共享基础设施（可复用）
CREATE TABLE student_service_action (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  student_id BIGINT NOT NULL COMMENT '统一学生ID',
  business_type VARCHAR(32) NOT NULL COMMENT 'administration/mental_warning/ticket',
  business_id BIGINT NOT NULL COMMENT '关联主记录ID',
  action_type VARCHAR(32) NOT NULL COMMENT '动作 create/approve/reject/cancel/assign/follow/close/rate',
  from_status VARCHAR(20) NULL COMMENT '动作前状态',
  to_status VARCHAR(20) NULL COMMENT '动作后状态',
  operator_type VARCHAR(20) NOT NULL COMMENT 'student/employee/system',
  operator_id BIGINT NULL COMMENT '统一操作者ID',
  note TEXT NULL COMMENT '必要操作说明/人工跟进备注',
  event_key VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '操作事件幂等键',
  trace_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '日志链路ID',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间（UTC）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_action_event (event_key),
  KEY idx_action_business (business_type, business_id, created_at),
  KEY idx_action_student (student_id, created_at),
  CONSTRAINT fk_action_student FOREIGN KEY (student_id) REFERENCES student_identity(id),
  CONSTRAINT ck_action_business CHECK (business_type IN ('administration', 'mental_warning', 'ticket')),
  CONSTRAINT ck_action_operator CHECK (operator_type IN ('student', 'employee', 'system')),
  CONSTRAINT ck_action_actor CHECK (operator_type = 'system' OR operator_id IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学生服务操作与多轮跟进记录';
