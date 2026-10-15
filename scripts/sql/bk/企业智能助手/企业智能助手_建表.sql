-- 企业智能助手建表脚本
-- 依据：企业智能助手_功能与数据库设计方案.md V2.2
-- 日期：2026-10-14
-- 验证：已在临时独立 MySQL 8.0.27 实例执行成功。
-- 验证结果：14 张表、31 项外键、63 项 CHECK、224 个字段（均有中文注释）；
-- 14 表合法样例及 11 项非法数据/外键/唯一键用例通过，验证数据已回滚。
-- 适用：MySQL 8.0.16+（建议 MySQL 8.0 或 8.4），不适用于 MySQL 5.7。
-- 参考：https://dev.mysql.com/doc/refman/8.0/en/create-table-check-constraints.html
-- 参考：https://dev.mysql.com/doc/refman/8.0/en/create-table-foreign-keys.html
--
-- 首次初始化使用：目标库内这 14 个表应尚不存在；本文件不是旧结构迁移脚本。
-- 可在 MySQL Workbench / Navicat 中打开本文件并整体执行。
-- mysql 客户端进入后可执行：SOURCE D:/pj/StuProject/业务文档/05数据库设计/企业智能助手_建表.sql;
-- 默认数据库为 education_agent，需要改库名时同时修改下面 CREATE DATABASE 和 USE。
-- 本文件不删除已有库/表，不插入业务数据，不创建数据库用户或配置密码。
-- UTF-8 编码，所有字段和表均有中文注释；创建 14 张表、31 项实际外键。
--
-- NL2SQL 只能通过另行配置的只读账号执行经校验的 SELECT；
-- 增删改通过硬编码业务接口执行，本脚本不会自动授予任何账号权限。
-- 稳定请求键、行级权限、跨行审批关系、完整状态流转、部门环路检查
-- 和历史记录/通知的事务写入由后端实现；CHECK 不能替代这些业务逻辑。
-- entity_type + entity_id 是受控逻辑引用，不能作为多表物理外键。
-- service_ticket_record 为追加记录，仅有 created_at；
-- 其余可变表有 created_at、updated_at、row_version，版本号不能靠默认值自动递增。
-- 每个应用连接都须使用 UTC；report_date 由后端按机构工作日计算。
-- 对状态、编码及外部身份键使用二进制排序规则，避免大小写身份混淆。

SET NAMES utf8mb4;
SET SESSION time_zone = '+00:00';
SET SESSION sql_mode = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

CREATE DATABASE IF NOT EXISTS `education_agent`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
USE `education_agent`;

-- 部门表
CREATE TABLE `org_department` (
  `department_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '部门记录主键 ID，供员工、客户、学生及部门层级引用。 主键（PK）。',
  `department_code` VARCHAR(32) COLLATE utf8mb4_bin NOT NULL COMMENT '部门唯一业务编码。',
  `department_name` VARCHAR(100) NOT NULL COMMENT '部门名称。',
  `parent_department_id` BIGINT NULL DEFAULT NULL COMMENT '上级部门 ID，关联本表；顶级部门为空。 外键（FK）关联 org_department.department_id。',
  `function_description` TEXT NULL DEFAULT NULL COMMENT '部门职能与职责说明。',
  `employee_id` BIGINT NULL DEFAULT NULL COMMENT '部门主管员工 ID，关联 employee。 外键（FK）关联 employee.employee_id。',
  `status` VARCHAR(20) COLLATE utf8mb4_bin NOT NULL DEFAULT 'active' COMMENT '部门状态：active 启用、disabled 停用。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '记录最近更新时间，UTC',
  `row_version` INT NOT NULL DEFAULT 1 COMMENT '并发版本号；每次业务修改由硬编码后端递增',
  PRIMARY KEY (`department_id`),
  UNIQUE KEY `uq_department_code` (`department_code`),
  KEY `idx_department_parent` (`parent_department_id`),
  KEY `idx_department_manager` (`employee_id`),
  CONSTRAINT `fk_org_department_parent_department_id` FOREIGN KEY (`parent_department_id`) REFERENCES `org_department` (`department_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_department_status` CHECK (`status` IN ('active','disabled')),
  CONSTRAINT `ck_org_department_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='部门表';

-- 员工表
CREATE TABLE `employee` (
  `employee_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '员工主键 ID，是所有员工业务关联的内部标识，不使用工号代替。 主键（PK）。',
  `employee_no` VARCHAR(32) NOT NULL COMMENT '员工唯一工号。',
  `full_name` VARCHAR(100) NOT NULL COMMENT '员工姓名，允许重名。',
  `department_id` BIGINT NOT NULL COMMENT '当前主部门 ID，关联 org_department。 外键（FK）关联 org_department.department_id。',
  `position_title` VARCHAR(100) NULL DEFAULT NULL COMMENT '员工岗位或职务名称。',
  `login_provider` VARCHAR(32) COLLATE utf8mb4_bin NOT NULL COMMENT '登录来源，如企业统一登录。',
  `login_subject` VARCHAR(128) COLLATE utf8mb4_bin NOT NULL COMMENT '登录来源提供的不可变账号标识。',
  `role_codes` JSON NOT NULL COMMENT '受控角色代码数组；权限由后端固定配置解释。',
  `work_phone_ciphertext` VARBINARY(512) NULL DEFAULT NULL COMMENT '加密保存的工作联系电话。',
  `work_email` VARCHAR(254) NULL DEFAULT NULL COMMENT '工作邮箱。',
  `status` VARCHAR(20) COLLATE utf8mb4_bin NOT NULL DEFAULT 'active' COMMENT '员工状态：active 启用、disabled 停用、left 离职。',
  `joined_date` DATE NOT NULL COMMENT '入职日期。',
  `left_date` DATE NULL DEFAULT NULL COMMENT '离职日期，未离职时为空。',
  `external_employee_id` VARCHAR(128) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '权威通讯录中的员工 ID。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '记录最近更新时间，UTC',
  `row_version` INT NOT NULL DEFAULT 1 COMMENT '并发版本号；每次业务修改由硬编码后端递增',
  PRIMARY KEY (`employee_id`),
  UNIQUE KEY `uq_employee_no` (`employee_no`),
  UNIQUE KEY `uq_employee_login` (`login_provider`, `login_subject`),
  UNIQUE KEY `uq_employee_external` (`external_employee_id`),
  KEY `idx_employee_department_status` (`department_id`, `status`),
  CONSTRAINT `fk_employee_department_id` FOREIGN KEY (`department_id`) REFERENCES `org_department` (`department_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_employee_status` CHECK (`status` IN ('active','disabled','left')),
  CONSTRAINT `ck_employee_roles` CHECK (JSON_TYPE(`role_codes`) = 'ARRAY' AND JSON_LENGTH(`role_codes`) > 0),
  CONSTRAINT `ck_employee_dates` CHECK (`left_date` IS NULL OR `left_date` >= `joined_date`),
  CONSTRAINT `ck_employee_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='员工表';

-- 部门与员工互相引用：两张表创建后补建部门主管外键。
ALTER TABLE `org_department` ADD CONSTRAINT `fk_org_department_employee_id` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;

-- 客户表
CREATE TABLE `customer_profile` (
  `customer_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '客户主键 ID，是跟进记录及关联学生使用的内部标识。 主键（PK）。',
  `customer_no` VARCHAR(32) NOT NULL COMMENT '客户唯一业务编号。',
  `full_name` VARCHAR(100) NOT NULL COMMENT '客户姓名，不作为唯一身份依据。',
  `phone_ciphertext` VARBINARY(512) NULL DEFAULT NULL COMMENT '加密保存的客户手机号。',
  `phone_lookup_token` CHAR(64) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '标准化手机号的带密钥匹配标记，用于提示重复候选。',
  `education_level` VARCHAR(32) NULL DEFAULT NULL COMMENT '客户学历层次。',
  `target_country_code` VARCHAR(8) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '意向留学国家编码。',
  `source_channel` VARCHAR(32) NOT NULL COMMENT '客户来源，如人工、客服留资或 CRM。',
  `source_reference` VARCHAR(128) NULL DEFAULT NULL COMMENT '来源留资或研判任务引用。',
  `employee_id` BIGINT NULL DEFAULT NULL COMMENT '当前顾问员工 ID，未分派时为空。 外键（FK）关联 employee.employee_id。',
  `department_id` BIGINT NOT NULL COMMENT '当前客户管理部门 ID。 外键（FK）关联 org_department.department_id。',
  `status` VARCHAR(20) COLLATE utf8mb4_bin NOT NULL DEFAULT 'new' COMMENT '客户状态：new、contacting、qualified、signed、lost。',
  `status_changed_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '当前客户状态开始生效的时间。',
  `lost_reason` TEXT NULL DEFAULT NULL COMMENT '流失原因，状态变为 lost 时必须填写。',
  `last_followup_at` DATETIME(3) NULL DEFAULT NULL COMMENT '最近一次有效跟进时间，由业务服务维护。',
  `authority_source` VARCHAR(20) NOT NULL DEFAULT 'local' COMMENT '数据权威来源：local 本平台、crm 外部 CRM。',
  `external_customer_id` VARCHAR(128) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT 'CRM 中的客户 ID。',
  `external_updated_at` DATETIME(3) NULL DEFAULT NULL COMMENT '最近确认的外部客户更新时间。',
  `is_archived` BOOLEAN NOT NULL DEFAULT 0 COMMENT '是否已归档，默认 false；保留销售状态和历史，归档后不进入默认客户列表。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '记录最近更新时间，UTC',
  `row_version` INT NOT NULL DEFAULT 1 COMMENT '并发版本号；每次业务修改由硬编码后端递增',
  PRIMARY KEY (`customer_id`),
  UNIQUE KEY `uq_customer_no` (`customer_no`),
  UNIQUE KEY `uq_customer_external` (`external_customer_id`),
  KEY `idx_customer_employee_status` (`employee_id`, `status`),
  KEY `idx_customer_department_status` (`department_id`, `status`),
  KEY `idx_customer_phone_token` (`phone_lookup_token`),
  CONSTRAINT `fk_customer_profile_employee_id` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_customer_profile_department_id` FOREIGN KEY (`department_id`) REFERENCES `org_department` (`department_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_customer_status` CHECK (`status` IN ('new','contacting','qualified','signed','lost')),
  CONSTRAINT `ck_customer_authority` CHECK (`authority_source` IN ('local','crm')),
  CONSTRAINT `ck_customer_lost_reason` CHECK (`status` <> 'lost' OR (`lost_reason` IS NOT NULL AND CHAR_LENGTH(TRIM(`lost_reason`)) > 0)),
  CONSTRAINT `ck_customer_archived` CHECK (`is_archived` IN (0,1)),
  CONSTRAINT `ck_customer_profile_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='客户表';

-- 客户跟进表
CREATE TABLE `customer_followup` (
  `followup_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '客户跟进记录主键 ID。 主键（PK）。',
  `customer_id` BIGINT NOT NULL COMMENT '本记录所属客户 ID。 外键（FK）关联 customer_profile.customer_id。',
  `employee_id` BIGINT NOT NULL COMMENT '实际执行跟进的员工 ID。 外键（FK）关联 employee.employee_id。',
  `followup_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '客户沟通实际发生时间。',
  `channel` VARCHAR(32) NOT NULL COMMENT '跟进方式，如电话、面谈或线上沟通。',
  `content` TEXT NOT NULL COMMENT '完整跟进内容。',
  `summary` TEXT NULL DEFAULT NULL COMMENT '经员工确认的跟进摘要。',
  `next_followup_at` DATETIME(3) NULL DEFAULT NULL COMMENT '计划下一次跟进的时间。',
  `followup_status` VARCHAR(20) COLLATE utf8mb4_bin NOT NULL DEFAULT 'none' COMMENT '下一次跟进安排状态：none 未安排、pending 待跟进、done 已完成、cancelled 已取消。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '记录最近更新时间，UTC',
  `row_version` INT NOT NULL DEFAULT 1 COMMENT '并发版本号；每次业务修改由硬编码后端递增',
  PRIMARY KEY (`followup_id`),
  KEY `idx_followup_customer_time` (`customer_id`, `followup_at`, `followup_id`),
  KEY `idx_followup_due` (`followup_status`, `next_followup_at`, `customer_id`),
  KEY `idx_followup_employee` (`employee_id`),
  CONSTRAINT `fk_customer_followup_customer_id` FOREIGN KEY (`customer_id`) REFERENCES `customer_profile` (`customer_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_customer_followup_employee_id` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_followup_status` CHECK (`followup_status` IN ('none','pending','done','cancelled')),
  CONSTRAINT `ck_followup_pending_time` CHECK (`followup_status` <> 'pending' OR `next_followup_at` IS NOT NULL),
  CONSTRAINT `ck_customer_followup_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='客户跟进表';

-- 员工日报表
CREATE TABLE `employee_daily_report` (
  `daily_report_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '员工日报记录主键 ID。 主键（PK）。',
  `employee_id` BIGINT NOT NULL COMMENT '日报所属员工 ID。 外键（FK）关联 employee.employee_id。',
  `report_date` DATE NOT NULL COMMENT '日报对应机构工作日日期。',
  `department_id_at_submit` BIGINT NOT NULL COMMENT '最近提交时的部门快照。 外键（FK）关联 org_department.department_id。',
  `submitted_content` TEXT NOT NULL COMMENT '最近一次员工确认提交的正式内容，必须填写。',
  `ai_summary` TEXT NULL DEFAULT NULL COMMENT '与最近提交内容对应的辅助摘要。',
  `status` VARCHAR(20) COLLATE utf8mb4_bin NOT NULL DEFAULT 'submitted' COMMENT '日报状态：submitted 已提交、void 已作废。',
  `submitted_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '最近正式提交时间。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '记录最近更新时间，UTC',
  `row_version` INT NOT NULL DEFAULT 1 COMMENT '并发版本号；每次业务修改由硬编码后端递增',
  PRIMARY KEY (`daily_report_id`),
  UNIQUE KEY `uq_daily_employee_date` (`employee_id`, `report_date`),
  KEY `idx_daily_department_date_status` (`department_id_at_submit`, `report_date`, `status`),
  CONSTRAINT `fk_employee_daily_report_employee_id` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_employee_daily_report_department_id_at_submit` FOREIGN KEY (`department_id_at_submit`) REFERENCES `org_department` (`department_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_daily_status` CHECK (`status` IN ('submitted','void')),
  CONSTRAINT `ck_daily_content` CHECK (CHAR_LENGTH(TRIM(`submitted_content`)) > 0),
  CONSTRAINT `ck_employee_daily_report_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='员工日报表';

-- 学生表
CREATE TABLE `student_profile` (
  `student_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '学生主键 ID，是成绩、请假、投诉及学生员工关系使用的内部标识。 主键（PK）。',
  `student_no` VARCHAR(32) NOT NULL COMMENT '学生唯一业务编号。',
  `full_name` VARCHAR(100) NOT NULL COMMENT '学生姓名，允许重名。',
  `customer_id` BIGINT NULL DEFAULT NULL COMMENT '关联客户 ID，不自动授予客户账号访问学生数据的权限。 外键（FK）关联 customer_profile.customer_id。',
  `department_id` BIGINT NOT NULL COMMENT '学生教务或服务归属部门 ID。 外键（FK）关联 org_department.department_id。',
  `login_provider` VARCHAR(32) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '学生登录来源，尚未开通账号时为空。',
  `login_subject` VARCHAR(128) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '学生登录身份键，与登录来源同时填写。',
  `status` VARCHAR(20) COLLATE utf8mb4_bin NOT NULL COMMENT '学生服务或在读状态。',
  `external_student_id` VARCHAR(128) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '教务系统中的学生 ID。',
  `is_archived` BOOLEAN NOT NULL DEFAULT 0 COMMENT '是否已归档，默认 false；归档不删除已有成绩、请假和投诉关联。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '记录最近更新时间，UTC',
  `row_version` INT NOT NULL DEFAULT 1 COMMENT '并发版本号；每次业务修改由硬编码后端递增',
  PRIMARY KEY (`student_id`),
  UNIQUE KEY `uq_student_no` (`student_no`),
  UNIQUE KEY `uq_student_login` (`login_provider`, `login_subject`),
  UNIQUE KEY `uq_student_external` (`external_student_id`),
  KEY `idx_student_department_status` (`department_id`, `status`),
  KEY `idx_student_customer` (`customer_id`),
  CONSTRAINT `fk_student_profile_customer_id` FOREIGN KEY (`customer_id`) REFERENCES `customer_profile` (`customer_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_student_profile_department_id` FOREIGN KEY (`department_id`) REFERENCES `org_department` (`department_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_student_login_pair` CHECK ((`login_provider` IS NULL AND `login_subject` IS NULL) OR (`login_provider` IS NOT NULL AND `login_subject` IS NOT NULL)),
  CONSTRAINT `ck_student_archived` CHECK (`is_archived` IN (0,1)),
  CONSTRAINT `ck_student_profile_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学生表';

-- 学生员工关系表
CREATE TABLE `student_staff_binding` (
  `binding_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '学生员工关系记录主键 ID。 主键（PK）。',
  `student_id` BIGINT NOT NULL COMMENT '被服务或管理的学生 ID。 外键（FK）关联 student_profile.student_id。',
  `employee_id` BIGINT NOT NULL COMMENT '承担对应职责的员工 ID。 外键（FK）关联 employee.employee_id。',
  `relation_type` VARCHAR(32) COLLATE utf8mb4_bin NOT NULL COMMENT '关系类型：class_teacher 班主任、score_editor 成绩人员、service_advisor 服务顾问。',
  `course_scope_code` VARCHAR(64) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '成绩权限限定的课程编码，空值需角色允许相应课程范围。',
  `is_primary` BOOLEAN NOT NULL DEFAULT 0 COMMENT '是否为此业务关系的主要负责人。',
  `valid_from` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '关系开始生效时间。',
  `valid_to` DATETIME(3) NULL DEFAULT NULL COMMENT '关系失效时间，临时代理需要截止时间。',
  `status` VARCHAR(20) COLLATE utf8mb4_bin NOT NULL DEFAULT 'active' COMMENT '关系状态：active 有效、disabled 停用。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '记录最近更新时间，UTC',
  `row_version` INT NOT NULL DEFAULT 1 COMMENT '并发版本号；每次业务修改由硬编码后端递增',
  PRIMARY KEY (`binding_id`),
  KEY `idx_binding_employee_type_status` (`employee_id`, `relation_type`, `status`),
  KEY `idx_binding_student_type_status` (`student_id`, `relation_type`, `status`),
  CONSTRAINT `fk_student_staff_binding_student_id` FOREIGN KEY (`student_id`) REFERENCES `student_profile` (`student_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_student_staff_binding_employee_id` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_binding_type` CHECK (`relation_type` IN ('class_teacher','score_editor','service_advisor')),
  CONSTRAINT `ck_binding_status` CHECK (`status` IN ('active','disabled')),
  CONSTRAINT `ck_binding_dates` CHECK (`valid_to` IS NULL OR `valid_to` > `valid_from`),
  CONSTRAINT `ck_binding_primary` CHECK (`is_primary` IN (0,1)),
  CONSTRAINT `ck_student_staff_binding_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学生员工关系表';

-- 学生成绩表
CREATE TABLE `student_score` (
  `score_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '学生成绩记录主键 ID。 主键（PK）。',
  `student_id` BIGINT NOT NULL COMMENT '成绩所属学生 ID。 外键（FK）关联 student_profile.student_id。',
  `course_code` VARCHAR(64) COLLATE utf8mb4_bin NOT NULL COMMENT '受控课程编码。',
  `term_code` VARCHAR(32) COLLATE utf8mb4_bin NOT NULL COMMENT '学期编码。',
  `assessment_code` VARCHAR(64) COLLATE utf8mb4_bin NOT NULL COMMENT '考试、作业或其他考核项目编码。',
  `attempt_no` INT NOT NULL DEFAULT 1 COMMENT '考核尝试次数，首次为 1，补考递增。',
  `score_value` DECIMAL(8,2) NOT NULL COMMENT '学生实际得分，统一采用数值制，必须填写。',
  `max_score` DECIMAL(8,2) NOT NULL COMMENT '本次考核满分，必须填写且大于零。',
  `employee_id` BIGINT NOT NULL COMMENT '最近录入或更正成绩的员工 ID。 外键（FK）关联 employee.employee_id。',
  `status` VARCHAR(20) COLLATE utf8mb4_bin NOT NULL DEFAULT 'valid' COMMENT '成绩状态：valid 有效、void 作废。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '记录最近更新时间，UTC',
  `row_version` INT NOT NULL DEFAULT 1 COMMENT '并发版本号；每次业务修改由硬编码后端递增',
  PRIMARY KEY (`score_id`),
  UNIQUE KEY `uq_score_assessment_attempt` (`student_id`, `course_code`, `term_code`, `assessment_code`, `attempt_no`),
  KEY `idx_score_student_term` (`student_id`, `term_code`),
  KEY `idx_score_employee` (`employee_id`),
  CONSTRAINT `fk_student_score_student_id` FOREIGN KEY (`student_id`) REFERENCES `student_profile` (`student_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_student_score_employee_id` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_score_range` CHECK (`max_score` > 0 AND `score_value` >= 0 AND `score_value` <= `max_score`),
  CONSTRAINT `ck_score_attempt` CHECK (`attempt_no` >= 1),
  CONSTRAINT `ck_score_status` CHECK (`status` IN ('valid','void')),
  CONSTRAINT `ck_student_score_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学生成绩表';

-- 学生请假表
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

-- 投诉反馈表
CREATE TABLE `service_ticket` (
  `ticket_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '投诉反馈工单主键 ID，供处理记录引用。 主键（PK）。',
  `ticket_no` VARCHAR(32) NOT NULL COMMENT '统一工单业务编号。',
  `student_id` BIGINT NOT NULL COMMENT '投诉或反馈对应学生 ID。 外键（FK）关联 student_profile.student_id。',
  `ticket_type` VARCHAR(20) COLLATE utf8mb4_bin NOT NULL DEFAULT 'complaint' COMMENT 'complaint 投诉或 suggestion 建议。',
  `category_code` VARCHAR(32) COLLATE utf8mb4_bin NOT NULL COMMENT '申请、签证、教学等受控分类编码。',
  `content` TEXT NOT NULL COMMENT '学生提交的原始内容。',
  `ai_summary` TEXT NULL DEFAULT NULL COMMENT '辅助摘要，不覆盖学生原文。',
  `priority` VARCHAR(20) NOT NULL DEFAULT 'normal' COMMENT '处理优先级。',
  `employee_id` BIGINT NULL DEFAULT NULL COMMENT '当前处理员工 ID，未分派时为空。 外键（FK）关联 employee.employee_id。',
  `handling_department_id` BIGINT NOT NULL COMMENT '当前处理部门 ID。 外键（FK）关联 org_department.department_id。',
  `status` VARCHAR(32) COLLATE utf8mb4_bin NOT NULL DEFAULT 'open' COMMENT '工单状态：open 待分派、assigned 已分派、processing 处理中、awaiting_student 待学生确认、closed 已关闭、reopened 已重开。',
  `first_response_at` DATETIME(3) NULL DEFAULT NULL COMMENT '首次有效人工回应时间，自动回执不计入。',
  `response_due_at` DATETIME(3) NOT NULL COMMENT '首次回应截止时间。',
  `resolution_due_at` DATETIME(3) NOT NULL COMMENT '当前轮次解决截止时间。',
  `solution` TEXT NULL DEFAULT NULL COMMENT '当前解决方案，进入待学生确认状态时必填。',
  `resolved_at` DATETIME(3) NULL DEFAULT NULL COMMENT '最近给出解决方案的时间。',
  `closed_at` DATETIME(3) NULL DEFAULT NULL COMMENT '当前有效关闭时间。',
  `reopen_count` INT NOT NULL DEFAULT 0 COMMENT '重新打开次数，默认 0。',
  `satisfaction_score` TINYINT NULL DEFAULT NULL COMMENT '学生实际评价分数，建议 1—5。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '记录最近更新时间，UTC',
  `row_version` INT NOT NULL DEFAULT 1 COMMENT '并发版本号；每次业务修改由硬编码后端递增',
  PRIMARY KEY (`ticket_id`),
  UNIQUE KEY `uq_ticket_no` (`ticket_no`),
  KEY `idx_ticket_employee_status_due` (`employee_id`, `status`, `resolution_due_at`),
  KEY `idx_ticket_student_created` (`student_id`, `created_at`),
  KEY `idx_ticket_department_status` (`handling_department_id`, `status`),
  CONSTRAINT `fk_service_ticket_student_id` FOREIGN KEY (`student_id`) REFERENCES `student_profile` (`student_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_service_ticket_employee_id` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_service_ticket_handling_department_id` FOREIGN KEY (`handling_department_id`) REFERENCES `org_department` (`department_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_svc_ticket_type` CHECK (`ticket_type` IN ('complaint','suggestion')),
  CONSTRAINT `ck_svc_ticket_status` CHECK (`status` IN ('open','assigned','processing','awaiting_student','closed','reopened')),
  CONSTRAINT `ck_ticket_satisfaction` CHECK (`satisfaction_score` IS NULL OR `satisfaction_score` BETWEEN 1 AND 5),
  CONSTRAINT `ck_ticket_reopen_count` CHECK (`reopen_count` >= 0),
  CONSTRAINT `ck_ticket_solution` CHECK (`status` NOT IN ('awaiting_student','closed') OR (`solution` IS NOT NULL AND CHAR_LENGTH(TRIM(`solution`)) > 0)),
  CONSTRAINT `ck_service_ticket_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='投诉反馈表';

-- 投诉处理记录表
CREATE TABLE `service_ticket_record` (
  `ticket_record_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '投诉处理记录主键 ID。 主键（PK）。',
  `ticket_id` BIGINT NOT NULL COMMENT '本条业务记录所属工单 ID。 外键（FK）关联 service_ticket.ticket_id。',
  `record_type` VARCHAR(32) NOT NULL COMMENT '记录类型：分派、人工回应、备注、解决、确认、重开或升级。',
  `employee_id` BIGINT NULL DEFAULT NULL COMMENT '操作员工 ID，外键关联 employee.employee_id；员工操作时填写。',
  `student_id` BIGINT NULL DEFAULT NULL COMMENT '操作学生 ID，外键关联 student_profile.student_id；学生反馈时填写。',
  `service_code` VARCHAR(64) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '自动处理的受控服务编码；系统操作时填写，不作为员工或学生 ID。',
  `content` TEXT NULL DEFAULT NULL COMMENT '本次沟通、反馈或处理说明。',
  `visibility` VARCHAR(20) COLLATE utf8mb4_bin NOT NULL DEFAULT 'internal' COMMENT 'internal 内部可见或 student_visible 学生可见。',
  `to_status` VARCHAR(32) NULL DEFAULT NULL COMMENT '本次处理后工单状态。',
  `cycle_no` INT NOT NULL DEFAULT 1 COMMENT '当前处理轮次，初次为 1，重开后递增。',
  `record_key` VARCHAR(160) COLLATE utf8mb4_bin NOT NULL COMMENT '唯一业务记录去重键。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  PRIMARY KEY (`ticket_record_id`),
  UNIQUE KEY `uq_ticket_record_key` (`record_key`),
  KEY `idx_ticket_record_time` (`ticket_id`, `created_at`, `ticket_record_id`),
  KEY `idx_ticket_record_employee` (`employee_id`),
  KEY `idx_ticket_record_student` (`student_id`),
  CONSTRAINT `fk_service_ticket_record_ticket_id` FOREIGN KEY (`ticket_id`) REFERENCES `service_ticket` (`ticket_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_service_ticket_record_employee_id` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_service_ticket_record_student_id` FOREIGN KEY (`student_id`) REFERENCES `student_profile` (`student_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_ticket_record_actor` CHECK (((`employee_id` IS NOT NULL) + (`student_id` IS NOT NULL) + (`service_code` IS NOT NULL)) = 1),
  CONSTRAINT `ck_ticket_record_service` CHECK (`service_code` IS NULL OR CHAR_LENGTH(TRIM(`service_code`)) > 0),
  CONSTRAINT `ck_ticket_record_visibility` CHECK (`visibility` IN ('internal','student_visible')),
  CONSTRAINT `ck_ticket_record_cycle` CHECK (`cycle_no` >= 1),
  CONSTRAINT `ck_ticket_record_to_status` CHECK (`to_status` IS NULL OR `to_status` IN ('open','assigned','processing','awaiting_student','closed','reopened'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='投诉处理记录表';

-- 新人指南与制度知识表
CREATE TABLE `knowledge_entry` (
  `knowledge_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '知识条目主键 ID。 主键（PK）。',
  `entry_code` VARCHAR(64) COLLATE utf8mb4_bin NOT NULL COMMENT '知识条目唯一编码。',
  `title` VARCHAR(200) NOT NULL COMMENT '知识标题。',
  `entry_type` VARCHAR(20) COLLATE utf8mb4_bin NOT NULL COMMENT 'faq 标准问答或 document 制度文档。',
  `category_code` VARCHAR(32) COLLATE utf8mb4_bin NOT NULL COMMENT '入职、制度或业务流程等分类编码。',
  `question` TEXT NULL DEFAULT NULL COMMENT 'FAQ 标准问题，faq 时必填。',
  `answer` TEXT NULL DEFAULT NULL COMMENT 'FAQ 标准答案，faq 时必填。',
  `content_text` LONGTEXT NULL DEFAULT NULL COMMENT '文档正文，document 时应有正文或受控来源。',
  `source_reference` VARCHAR(512) NULL DEFAULT NULL COMMENT '原文件、章节或受控资料来源定位。',
  `employee_id` BIGINT NOT NULL COMMENT '知识维护员工 ID。 外键（FK）关联 employee.employee_id。',
  `access_department_id` BIGINT NULL DEFAULT NULL COMMENT '限定访问部门；为空表示全体员工可见。 外键（FK）关联 org_department.department_id。',
  `version_no` INT NOT NULL DEFAULT 1 COMMENT '当前内容版本号，内容变更时递增。',
  `status` VARCHAR(20) COLLATE utf8mb4_bin NOT NULL DEFAULT 'draft' COMMENT 'draft 草稿、published 已发布、disabled 停用。',
  `reviewer_employee_id` BIGINT NULL DEFAULT NULL COMMENT '审核该版本的员工 ID。 外键（FK）关联 employee.employee_id。',
  `reviewed_at` DATETIME(3) NULL DEFAULT NULL COMMENT '审核完成时间。',
  `effective_from` DATETIME(3) NULL DEFAULT NULL COMMENT '已发布知识开始生效的时间。',
  `expires_at` DATETIME(3) NULL DEFAULT NULL COMMENT '知识失效时间。',
  `index_status` VARCHAR(20) COLLATE utf8mb4_bin NOT NULL DEFAULT 'pending' COMMENT '索引状态：pending 待更新、ready 可检索、failed 失败。',
  `external_document_id` VARCHAR(128) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT 'Dify 或外部索引中的文档 ID。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '记录最近更新时间，UTC',
  `row_version` INT NOT NULL DEFAULT 1 COMMENT '并发版本号；每次业务修改由硬编码后端递增',
  PRIMARY KEY (`knowledge_id`),
  UNIQUE KEY `uq_knowledge_entry_code` (`entry_code`),
  KEY `idx_knowledge_status_scope_expiry` (`status`, `access_department_id`, `expires_at`),
  KEY `idx_knowledge_owner` (`employee_id`),
  KEY `idx_knowledge_reviewer` (`reviewer_employee_id`),
  CONSTRAINT `fk_knowledge_entry_employee_id` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_knowledge_entry_reviewer_employee_id` FOREIGN KEY (`reviewer_employee_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_knowledge_entry_access_department_id` FOREIGN KEY (`access_department_id`) REFERENCES `org_department` (`department_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_knowledge_type` CHECK (`entry_type` IN ('faq','document')),
  CONSTRAINT `ck_knowledge_status` CHECK (`status` IN ('draft','published','disabled')),
  CONSTRAINT `ck_knowledge_index` CHECK (`index_status` IN ('pending','ready','failed')),
  CONSTRAINT `ck_knowledge_version` CHECK (`version_no` >= 1),
  CONSTRAINT `ck_knowledge_faq` CHECK (`entry_type` <> 'faq' OR (`question` IS NOT NULL AND CHAR_LENGTH(TRIM(`question`)) > 0 AND `answer` IS NOT NULL AND CHAR_LENGTH(TRIM(`answer`)) > 0)),
  CONSTRAINT `ck_knowledge_document` CHECK (`entry_type` <> 'document' OR ((`content_text` IS NOT NULL AND CHAR_LENGTH(TRIM(`content_text`)) > 0) OR (`source_reference` IS NOT NULL AND CHAR_LENGTH(TRIM(`source_reference`)) > 0))),
  CONSTRAINT `ck_knowledge_published` CHECK (`status` <> 'published' OR (`reviewer_employee_id` IS NOT NULL AND `reviewed_at` IS NOT NULL AND `effective_from` IS NOT NULL AND `index_status` = 'ready')),
  CONSTRAINT `ck_knowledge_period` CHECK (`expires_at` IS NULL OR `effective_from` IS NULL OR `expires_at` > `effective_from`),
  CONSTRAINT `ck_knowledge_entry_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='新人指南与制度知识表';

-- 业务通知表
CREATE TABLE `business_notification` (
  `notification_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '业务通知记录主键 ID。 主键（PK）。',
  `entity_type` VARCHAR(32) COLLATE utf8mb4_bin NOT NULL COMMENT '关联业务实体类型，如请假、投诉或跟进。',
  `entity_id` BIGINT NOT NULL COMMENT '关联业务记录 ID，由业务服务按实体类型校验。',
  `event_code` VARCHAR(64) COLLATE utf8mb4_bin NOT NULL COMMENT '业务通知原因，如待审批、审批结果或投诉解决。',
  `employee_id` BIGINT NULL DEFAULT NULL COMMENT '员工接收人 ID，与学生接收人二选一。 外键（FK）关联 employee.employee_id。',
  `student_id` BIGINT NULL DEFAULT NULL COMMENT '学生接收人 ID，与员工接收人二选一。 外键（FK）关联 student_profile.student_id。',
  `channel` VARCHAR(20) NOT NULL COMMENT '投递渠道，如站内或企业消息。',
  `title` VARCHAR(200) NOT NULL COMMENT '通知标题，只包含必要信息。',
  `content` TEXT NOT NULL COMMENT '通知内容，不包含敏感业务原文。',
  `dedupe_key` VARCHAR(160) COLLATE utf8mb4_bin NOT NULL COMMENT '包含业务事件、轮次、接收人及渠道的唯一通知键。',
  `delivery_status` VARCHAR(20) COLLATE utf8mb4_bin NOT NULL DEFAULT 'pending' COMMENT 'pending 待发送、sending 发送中、sent 已发送、failed 失败、dead_letter 终止重试。',
  `attempt_count` INT NOT NULL DEFAULT 0 COMMENT '已尝试发送次数，初值 0。',
  `next_retry_at` DATETIME(3) NULL DEFAULT NULL COMMENT '下一次允许重试时间。',
  `lease_until` DATETIME(3) NULL DEFAULT NULL COMMENT '发送任务租约截止时间，用于恢复中断任务。',
  `sent_at` DATETIME(3) NULL DEFAULT NULL COMMENT '对应渠道确认接收消息的时间。',
  `read_at` DATETIME(3) NULL DEFAULT NULL COMMENT '真实已读时间，不支持回执时为空。',
  `last_error_code` VARCHAR(64) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '最近一次发送失败的脱敏错误码。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '记录最近更新时间，UTC',
  `row_version` INT NOT NULL DEFAULT 1 COMMENT '并发版本号；每次业务修改由硬编码后端递增',
  PRIMARY KEY (`notification_id`),
  UNIQUE KEY `uq_notification_dedupe` (`dedupe_key`),
  KEY `idx_notification_retry` (`delivery_status`, `next_retry_at`),
  KEY `idx_notification_employee_read` (`employee_id`, `read_at`, `created_at`),
  KEY `idx_notification_student_read` (`student_id`, `read_at`, `created_at`),
  KEY `idx_notification_entity` (`entity_type`, `entity_id`),
  CONSTRAINT `fk_business_notification_employee_id` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_business_notification_student_id` FOREIGN KEY (`student_id`) REFERENCES `student_profile` (`student_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_svc_notification_recipient` CHECK (((`employee_id` IS NOT NULL) + (`student_id` IS NOT NULL)) = 1),
  CONSTRAINT `ck_svc_notification_status` CHECK (`delivery_status` IN ('pending','sending','sent','failed','dead_letter')),
  CONSTRAINT `ck_notification_attempt` CHECK (`attempt_count` >= 0),
  CONSTRAINT `ck_business_notification_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='业务通知表';

-- 业务操作记录表
CREATE TABLE `operation_log` (
  `operation_log_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '业务操作记录主键 ID。 主键（PK）。',
  `operation_key` CHAR(64) COLLATE utf8mb4_bin NOT NULL COMMENT '操作唯一键，由真实操作者、动作和请求幂等键确定，与新建对象 ID 无关。',
  `employee_id` BIGINT NULL DEFAULT NULL COMMENT '真实操作员工 ID，外键关联 employee.employee_id。',
  `student_id` BIGINT NULL DEFAULT NULL COMMENT '真实操作学生 ID，外键关联 student_profile.student_id。',
  `service_code` VARCHAR(64) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '执行自动操作的受控服务编码，不伪装成员工或学生身份。',
  `action_code` VARCHAR(64) COLLATE utf8mb4_bin NOT NULL COMMENT '预先定义的业务动作编码。',
  `entity_type` VARCHAR(32) COLLATE utf8mb4_bin NOT NULL COMMENT '被操作业务实体类型。',
  `entity_id` BIGINT NULL DEFAULT NULL COMMENT '关联对象 ID，新建未完成或失败时可为空。',
  `request_key` VARCHAR(128) COLLATE utf8mb4_bin NOT NULL COMMENT '逻辑业务请求幂等键，同一提交重试保持不变。',
  `parameters_hash` CHAR(64) COLLATE utf8mb4_bin NOT NULL COMMENT '规范化业务参数摘要，用于识别相同幂等键下的参数冲突。',
  `before_data` JSON NULL DEFAULT NULL COMMENT '变更前必要业务快照，敏感字段按规则保护。',
  `after_data` JSON NULL DEFAULT NULL COMMENT '变更后必要业务快照，保留审批及修订结果。',
  `change_reason` TEXT NULL DEFAULT NULL COMMENT '人工更正、移交、驳回、删除等业务原因。',
  `operation_status` VARCHAR(32) COLLATE utf8mb4_bin NOT NULL DEFAULT 'processing' COMMENT '操作状态：processing 处理中、succeeded 成功、failed 失败、pending_external 等待外部结果、unknown_external 外部结果待核实。',
  `result_reference` JSON NULL DEFAULT NULL COMMENT '受控操作回执和对象标识，用于重复请求返回原结果。',
  `external_request_id` VARCHAR(128) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '外部系统请求标识，用于查询写回结果和对账。',
  `error_code` VARCHAR(64) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '操作失败、冲突或待核实的脱敏错误码。',
  `finished_at` DATETIME(3) NULL DEFAULT NULL COMMENT '操作形成明确成功或失败结果的时间。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '记录最近更新时间，UTC',
  `row_version` INT NOT NULL DEFAULT 1 COMMENT '并发版本号；每次业务修改由硬编码后端递增',
  PRIMARY KEY (`operation_log_id`),
  UNIQUE KEY `uq_operation_key` (`operation_key`),
  KEY `idx_operation_entity_time` (`entity_type`, `entity_id`, `created_at`),
  KEY `idx_operation_employee_time` (`employee_id`, `created_at`),
  KEY `idx_operation_student_time` (`student_id`, `created_at`),
  KEY `idx_operation_status_time` (`operation_status`, `created_at`),
  CONSTRAINT `fk_operation_log_employee_id` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_operation_log_student_id` FOREIGN KEY (`student_id`) REFERENCES `student_profile` (`student_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_operation_actor` CHECK (((`employee_id` IS NOT NULL) + (`student_id` IS NOT NULL) + (`service_code` IS NOT NULL)) = 1),
  CONSTRAINT `ck_operation_service` CHECK (`service_code` IS NULL OR CHAR_LENGTH(TRIM(`service_code`)) > 0),
  CONSTRAINT `ck_operation_status` CHECK (`operation_status` IN ('processing','succeeded','failed','pending_external','unknown_external')),
  CONSTRAINT `ck_operation_log_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='业务操作记录表';
