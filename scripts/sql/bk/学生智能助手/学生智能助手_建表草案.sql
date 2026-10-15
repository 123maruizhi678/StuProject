-- V3 2026-10-15：五张学生专属表 + 公共请假表。已有库请用初始化脚本预检，禁止重复执行DROP或重建。
-- 仅预览，不连接数据库；企业student_profile、employee须先存在。
-- 公共请假表，与企业模块共用同一张表。
CREATE TABLE `student_leave_request` (
  `leave_request_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '学生请假申请主键 ID。 主键（PK）。',
  `request_no` VARCHAR(32) NOT NULL COMMENT '请假申请唯一业务编号。',
  `student_id` BIGINT NOT NULL COMMENT '提交申请的学生 ID。 外键（FK）关联 student_profile.student_id。',
  `leave_type` VARCHAR(32) NOT NULL COMMENT '请假类型，如病假或事假。',
  `start_at` DATETIME(3) NOT NULL COMMENT '请假开始时间。',
  `end_at` DATETIME(3) NOT NULL COMMENT '请假结束时间，必须晚于开始时间。',
  `reason` TEXT NOT NULL COMMENT '学生填写的请假原因。',
  `attachment_key` VARCHAR(512) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '证明附件的受控对象存储定位。',
  `approver_employee_id` BIGINT NULL DEFAULT NULL COMMENT '当前审批员工 ID，分派异常时为空。 外键（FK）关联 employee.employee_id。',
  `status` VARCHAR(20) COLLATE utf8mb4_bin NOT NULL DEFAULT 'submitted' COMMENT 'submitted 待审批、approved 已批准、rejected 已驳回、withdrawn 已撤回。',
  `submitted_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '学生提交申请的时间。',
  `decision_employee_id` BIGINT NULL DEFAULT NULL COMMENT '实际批准或驳回申请的员工 ID。 外键（FK）关联 employee.employee_id。',
  `decision_at` DATETIME(3) NULL DEFAULT NULL COMMENT '形成审批结果的时间。',
  `decision_comment` TEXT NULL DEFAULT NULL COMMENT '审批意见，驳回时必填。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '记录最近更新时间，UTC',
  `row_version` INT NOT NULL DEFAULT 1 COMMENT '并发版本号；每次业务修改由硬编码后端递增',
  PRIMARY KEY (`leave_request_id`),
  UNIQUE KEY `uq_leave_request_no` (`request_no`),
  KEY `idx_leave_approver_status_time` (`approver_employee_id`, `status`, `submitted_at`),
  KEY `idx_leave_student_start` (`student_id`, `start_at`),
  KEY `idx_leave_decision_employee` (`decision_employee_id`),
  CONSTRAINT `fk_student_leave_request_student_id` FOREIGN KEY (`student_id`) REFERENCES `student_profile` (`student_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_student_leave_request_approver_employee_id` FOREIGN KEY (`approver_employee_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_student_leave_request_decision_employee_id` FOREIGN KEY (`decision_employee_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_leave_period` CHECK (`end_at` > `start_at`),
  CONSTRAINT `ck_leave_reason` CHECK (CHAR_LENGTH(TRIM(`reason`)) > 0),
  CONSTRAINT `ck_leave_status` CHECK (`status` IN ('submitted','approved','rejected','withdrawn')),
  CONSTRAINT `ck_leave_decision` CHECK ((`status` IN ('submitted','withdrawn') AND `decision_employee_id` IS NULL AND `decision_at` IS NULL) OR (`status` IN ('approved','rejected') AND `decision_employee_id` IS NOT NULL AND `decision_at` IS NOT NULL)),
  CONSTRAINT `ck_leave_reject_comment` CHECK (`status` <> 'rejected' OR (`decision_comment` IS NOT NULL AND CHAR_LENGTH(TRIM(`decision_comment`)) > 0)),
  CONSTRAINT `ck_student_leave_request_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学生请假表';
CREATE TABLE mental_health_profile (
	id BIGINT NOT NULL COMMENT '评估主键ID' AUTO_INCREMENT,
	student_id BIGINT NOT NULL COMMENT '学生ID，关联student_profile.student_id',
	emotion_tag VARCHAR(50) NOT NULL COMMENT '本次情绪标签',
	emotion_score NUMERIC(5, 2) NOT NULL COMMENT '分值0至100，越高表示情绪越平稳；不代表医学诊断',
	history_data JSON COMMENT '旧历史JSON兼容字段；新记录保持NULL',
	risk_level VARCHAR(20) NOT NULL COMMENT '评估风险：low/medium/high/critical',
	observed_at DATETIME(6) NOT NULL COMMENT '源消息发生时间，UTC；区别于入库时间',
	source_event_id VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '可信入口生成的源事件ID，重试时复用',
	workflow_run_id VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin COMMENT 'Dify工作流运行ID，仅用于追溯',
	analysis_version VARCHAR(64) NOT NULL COMMENT '心理分析配置版本，明确分值和风险口径',
	created_at DATETIME(6) NOT NULL COMMENT '创建时间，UTC' DEFAULT CURRENT_TIMESTAMP(6),
	PRIMARY KEY (id),
	CONSTRAINT uk_profile_source UNIQUE (student_id, source_event_id),
	CONSTRAINT uk_profile_owner UNIQUE (id, student_id),
	CONSTRAINT ck_profile_score CHECK (emotion_score >= 0 AND emotion_score <= 100),
	CONSTRAINT ck_profile_risk CHECK (risk_level IN ('low','medium','high','critical')),
	CONSTRAINT fk_profile_student FOREIGN KEY(student_id) REFERENCES student_profile (student_id)
)ENGINE=InnoDB COMMENT='学生心理评估历史表' CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE INDEX idx_profile_history ON mental_health_profile (student_id, observed_at);
CREATE INDEX idx_profile_report ON mental_health_profile (observed_at, risk_level);
CREATE TABLE mental_warning (
	id BIGINT NOT NULL COMMENT '预警主键ID' AUTO_INCREMENT,
	student_id BIGINT NOT NULL COMMENT '学生ID，关联student_profile.student_id',
	profile_id BIGINT NOT NULL COMMENT '触发评估ID，与student_id组成画像外键',
	trigger_reason TEXT NOT NULL COMMENT '必要的触发依据，仅授权处理人可见',
	risk_level VARCHAR(20) NOT NULL COMMENT '预警等级：high/critical',
	follower_status VARCHAR(20) NOT NULL COMMENT '人工处理状态：pending/processing/closed' DEFAULT 'pending',
	follower_id BIGINT COMMENT '处理员工ID，关联employee.employee_id；未分派可空',
	acknowledged_at DATETIME(6) COMMENT '真实人工接手时间，UTC',
	closed_at DATETIME(6) COMMENT '人工关闭时间，UTC',
	handling_result TEXT COMMENT '最终人工处置结果；关闭时不能为空',
	version INTEGER NOT NULL COMMENT '并发版本，业务更新时条件校验并递增' DEFAULT 1,
	updated_at DATETIME(6) NOT NULL COMMENT '最近修改时间，UTC' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
	created_at DATETIME(6) NOT NULL COMMENT '创建时间，UTC' DEFAULT CURRENT_TIMESTAMP(6),
	PRIMARY KEY (id),
	CONSTRAINT uk_warning_profile UNIQUE (profile_id),
	CONSTRAINT fk_warning_profile FOREIGN KEY(profile_id, student_id) REFERENCES mental_health_profile (id, student_id),
	CONSTRAINT ck_warning_risk CHECK (risk_level IN ('high','critical')),
	CONSTRAINT ck_warning_status CHECK (follower_status IN ('pending','processing','closed')),
	CONSTRAINT ck_warning_closed CHECK (follower_status <> 'closed' OR (follower_id IS NOT NULL AND acknowledged_at IS NOT NULL AND closed_at IS NOT NULL AND handling_result IS NOT NULL)),
	CONSTRAINT ck_warning_version CHECK (version >= 1),
	CONSTRAINT fk_warning_student FOREIGN KEY(student_id) REFERENCES student_profile (student_id),
	CONSTRAINT fk_warning_employee FOREIGN KEY(follower_id) REFERENCES employee (employee_id)
)ENGINE=InnoDB COMMENT='学生心理预警及人工处置表' CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE INDEX idx_warning_follower ON mental_warning (follower_id, follower_status, created_at);
CREATE INDEX idx_warning_student ON mental_warning (student_id, created_at);
CREATE TABLE student_academic_event (
	id BIGINT NOT NULL COMMENT '学业节点主键ID' AUTO_INCREMENT,
	student_id BIGINT NOT NULL COMMENT '学生ID，关联student_profile.student_id',
	source_system VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '教务来源编码，如education',
	external_event_id VARCHAR(128) COLLATE utf8mb4_bin NOT NULL COMMENT '源系统节点ID，与学生和来源组成同步唯一键',
	event_type VARCHAR(20) NOT NULL COMMENT '节点类型：ddl截止日期/exam考试',
	title VARCHAR(200) NOT NULL COMMENT '论文或考试标题',
	due_at DATETIME(6) NOT NULL COMMENT '准确截止或考试时点，UTC',
	source_timezone VARCHAR(64) NOT NULL COMMENT '来源IANA时区，如Asia/Shanghai',
	event_status VARCHAR(20) NOT NULL COMMENT '节点状态：active/cancelled' DEFAULT 'active',
	event_version INTEGER NOT NULL COMMENT '节点时间或有效状态改变时递增的提醒版本' DEFAULT 1,
	source_updated_at DATETIME(6) COMMENT '源系统更新时间，UTC；防止旧消息覆盖新节点',
	synced_at DATETIME(6) NOT NULL COMMENT '最后成功同步时间，UTC；用于展示数据新鲜度',
	updated_at DATETIME(6) NOT NULL COMMENT '最近修改时间，UTC' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
	created_at DATETIME(6) NOT NULL COMMENT '创建时间，UTC' DEFAULT CURRENT_TIMESTAMP(6),
	PRIMARY KEY (id),
	CONSTRAINT uk_academic_source UNIQUE (student_id, source_system, external_event_id),
	CONSTRAINT uk_academic_owner UNIQUE (id, student_id),
	CONSTRAINT ck_academic_type CHECK (event_type IN ('ddl','exam')),
	CONSTRAINT ck_academic_status CHECK (event_status IN ('active','cancelled')),
	CONSTRAINT ck_academic_version CHECK (event_version >= 1),
	CONSTRAINT fk_academic_student FOREIGN KEY(student_id) REFERENCES student_profile (student_id)
)ENGINE=InnoDB COMMENT='学生学业截止及考试节点镜像表' CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE INDEX idx_academic_student ON student_academic_event (student_id, event_status, due_at);
CREATE TABLE student_academic_reminder (
	id BIGINT NOT NULL COMMENT '提醒主键ID' AUTO_INCREMENT,
	student_id BIGINT NOT NULL COMMENT '节点所属学生，通过组合外键关联同一学生',
	academic_event_id BIGINT NOT NULL COMMENT '学业节点ID，组合关联student_academic_event',
	lead_minutes INTEGER NOT NULL COMMENT '提前分钟数；1440为一天，0为到点提醒',
	notify_at DATETIME(6) NOT NULL COMMENT '计划提醒时点，UTC；由节点时间减提前量计算',
	event_version INTEGER NOT NULL COMMENT '对应节点版本，发送前须检查仍一致',
	status VARCHAR(20) NOT NULL COMMENT 'pending待执行/queued已入队/sent已投递/cancelled已取消' DEFAULT 'pending',
	sent_at DATETIME(6) COMMENT '当前版本实际成功发送时间，UTC',
	updated_at DATETIME(6) NOT NULL COMMENT '最近修改时间，UTC' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
	created_at DATETIME(6) NOT NULL COMMENT '创建时间，UTC' DEFAULT CURRENT_TIMESTAMP(6),
	PRIMARY KEY (id),
	CONSTRAINT uk_reminder_setting UNIQUE (student_id, academic_event_id, lead_minutes),
	CONSTRAINT fk_reminder_event FOREIGN KEY(academic_event_id, student_id) REFERENCES student_academic_event (id, student_id),
	CONSTRAINT ck_reminder_lead CHECK (lead_minutes >= 0),
	CONSTRAINT ck_reminder_version CHECK (event_version >= 1),
	CONSTRAINT ck_reminder_status CHECK (status IN ('pending','queued','sent','cancelled')),
	CONSTRAINT ck_reminder_sent CHECK (status <> 'sent' OR sent_at IS NOT NULL)
)ENGINE=InnoDB COMMENT='学生学业提醒设置与执行状态表' CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE INDEX idx_reminder_due ON student_academic_reminder (status, notify_at);
CREATE TABLE student_application_progress (
	id BIGINT NOT NULL COMMENT '阶段进度主键ID' AUTO_INCREMENT,
	student_id BIGINT NOT NULL COMMENT '学生ID，关联student_profile.student_id',
	source_system VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'CRM或申请系统来源编码',
	external_application_id VARCHAR(128) COLLATE utf8mb4_bin NOT NULL COMMENT '源系统申请ID，用于区分不同院校和项目',
	application_name VARCHAR(200) NOT NULL COMMENT '院校或申请项目展示名称',
	stage_code VARCHAR(32) NOT NULL COMMENT 'document_review文书/school_application院校/visa_process签证',
	stage_status VARCHAR(64) NOT NULL COMMENT '外部契约映射的阶段状态，不由AI臆造',
	detail VARCHAR(500) COMMENT '必要进度说明，如需补充材料',
	source_updated_at DATETIME(6) COMMENT '源系统更新时间，UTC',
	synced_at DATETIME(6) NOT NULL COMMENT '最后成功同步时间，UTC；失败不刷新',
	updated_at DATETIME(6) NOT NULL COMMENT '最近修改时间，UTC' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
	created_at DATETIME(6) NOT NULL COMMENT '创建时间，UTC' DEFAULT CURRENT_TIMESTAMP(6),
	PRIMARY KEY (id),
	CONSTRAINT uk_progress_stage UNIQUE (student_id, source_system, external_application_id, stage_code),
	CONSTRAINT ck_progress_stage CHECK (stage_code IN ('document_review','school_application','visa_process')),
	CONSTRAINT fk_progress_student FOREIGN KEY(student_id) REFERENCES student_profile (student_id)
)ENGINE=InnoDB COMMENT='学生留学申请阶段最新进度镜像表' CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE INDEX idx_progress_student ON student_application_progress (student_id, synced_at);
