-- 公共登录及身份关联最小基线；只用于空库，不在启动时执行。

-- 已安装36表的现有数据库不要重跑，只执行经审核的公共增量。

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

SET SESSION time_zone = '+00:00';

CREATE TABLE `user_account` (
  `user_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT 'PK；自增；统一用户主键 ID。',
  `username` VARCHAR(64) COLLATE utf8mb4_bin NOT NULL COMMENT '登录用户名，唯一。',
  `password_hash` VARCHAR(255) COLLATE utf8mb4_bin NOT NULL COMMENT '密码哈希，不得存储明文密码。',
  `identity_type` VARCHAR(20) COLLATE utf8mb4_bin NOT NULL COMMENT '统一登录身份：admin平台管理员、employee员工、customer客户、student学生；与身份关联外键保持一致',
  `employee_id` BIGINT NULL DEFAULT NULL COMMENT '对应员工表 employee.employee_id；非员工身份时为空。',
  `customer_id` BIGINT NULL DEFAULT NULL COMMENT '对应客户表 customer_profile.customer_id；非客户身份时为空。',
  `student_id` BIGINT NULL DEFAULT NULL COMMENT '对应学生表 student_profile.student_id；非学生身份时为空。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '用户记录创建时间（UTC）。',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时自动刷新；用户记录最近更新时间（UTC）。',
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `uq_user_username` (`username`),
  UNIQUE KEY `uq_user_employee` (`employee_id`),
  UNIQUE KEY `uq_user_customer` (`customer_id`),
  UNIQUE KEY `uq_user_student` (`student_id`),
  CONSTRAINT `ck_user_identity_link` CHECK ((`identity_type` = 'admin' AND `employee_id` IS NULL AND `customer_id` IS NULL AND `student_id` IS NULL) OR (`identity_type` = 'employee' AND `employee_id` IS NOT NULL AND `customer_id` IS NULL AND `student_id` IS NULL) OR (`identity_type` = 'customer' AND `employee_id` IS NULL AND `customer_id` IS NOT NULL AND `student_id` IS NULL) OR (`identity_type` = 'student' AND `employee_id` IS NULL AND `customer_id` IS NULL AND `student_id` IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='统一登录账号、身份及业务主键映射';

CREATE TABLE `org_department` (
  `department_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT 'PK；自增；部门记录主键 ID，供员工、客户、学生及部门层级引用。 主键（PK）。',
  `department_code` VARCHAR(32) COLLATE utf8mb4_bin NOT NULL COMMENT '部门唯一业务编码。',
  `department_name` VARCHAR(100) NOT NULL COMMENT '部门名称。',
  `parent_department_id` BIGINT NULL DEFAULT NULL COMMENT '上级部门 ID，关联本表；顶级部门为空。 外键（FK）关联 org_department.department_id。',
  `function_description` TEXT NULL DEFAULT NULL COMMENT '部门职能与职责说明。',
  `employee_id` BIGINT NULL DEFAULT NULL COMMENT '部门主管员工 ID，关联 employee。 外键（FK）关联 employee.employee_id。',
  `status` VARCHAR(32) COLLATE utf8mb4_bin NOT NULL DEFAULT 'active' COMMENT '部门状态：active 启用、disabled 停用。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时自动刷新；记录最近更新时间，UTC',
  `row_version` INT NOT NULL DEFAULT 1 COMMENT '并发版本号；每次业务修改由后端递增',
  PRIMARY KEY (`department_id`),
  UNIQUE KEY `uq_department_code` (`department_code`),
  KEY `idx_department_parent` (`parent_department_id`),
  KEY `idx_department_manager` (`employee_id`),
  CONSTRAINT `ck_department_status` CHECK (`status` IN ('active','disabled')),
  CONSTRAINT `ck_org_department_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='部门层级、职能及主管';

CREATE TABLE `employee` (
  `employee_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT 'PK；自增；员工主键 ID，是所有员工业务关联的内部标识，不使用工号代替。 主键（PK）。',
  `employee_no` VARCHAR(32) NOT NULL COMMENT '员工唯一工号。',
  `full_name` VARCHAR(100) NOT NULL COMMENT '员工姓名，允许重名。',
  `department_id` BIGINT NOT NULL COMMENT '当前主部门 ID，关联 org_department。 外键（FK）关联 org_department.department_id。',
  `position_title` VARCHAR(100) NULL DEFAULT NULL COMMENT '员工岗位或职务名称。',
  `login_provider` VARCHAR(32) COLLATE utf8mb4_bin NOT NULL COMMENT '登录来源，如企业统一登录。',
  `login_subject` VARCHAR(128) COLLATE utf8mb4_bin NOT NULL COMMENT '登录来源提供的不可变账号标识。',
  `role_codes` JSON NOT NULL COMMENT '受控角色代码数组；权限由后端固定配置解释。',
  `work_phone_ciphertext` VARBINARY(512) NULL DEFAULT NULL COMMENT '加密保存的工作联系电话。',
  `work_email` VARCHAR(254) NULL DEFAULT NULL COMMENT '工作邮箱。',
  `status` VARCHAR(32) COLLATE utf8mb4_bin NOT NULL DEFAULT 'active' COMMENT '员工状态：active 启用、disabled 停用、left 离职。',
  `joined_date` DATE NOT NULL COMMENT '入职日期。',
  `left_date` DATE NULL DEFAULT NULL COMMENT '离职日期，未离职时为空。',
  `external_employee_id` VARCHAR(128) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '权威通讯录中的员工 ID。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时自动刷新；记录最近更新时间，UTC',
  `row_version` INT NOT NULL DEFAULT 1 COMMENT '并发版本号；每次业务修改由后端递增',
  PRIMARY KEY (`employee_id`),
  UNIQUE KEY `uq_employee_no` (`employee_no`),
  UNIQUE KEY `uq_employee_login` (`login_provider`, `login_subject`),
  UNIQUE KEY `uq_employee_external` (`external_employee_id`),
  KEY `idx_employee_department_status` (`department_id`, `status`),
  CONSTRAINT `ck_employee_status` CHECK (`status` IN ('active','disabled','left')),
  CONSTRAINT `ck_employee_roles` CHECK (JSON_TYPE(`role_codes`) = 'ARRAY' AND JSON_LENGTH(`role_codes`) > 0),
  CONSTRAINT `ck_employee_dates` CHECK (`left_date` IS NULL OR `left_date` >= `joined_date`),
  CONSTRAINT `ck_employee_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='员工资料、部门、业务角色及有效状态';

CREATE TABLE `customer_profile` (
  `customer_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT 'PK；自增；客户主键 ID，是跟进记录及关联学生使用的内部标识。 主键（PK）。',
  `customer_no` VARCHAR(32) NOT NULL COMMENT '客户唯一业务编号。',
  `full_name` VARCHAR(100) NOT NULL COMMENT '客户姓名，不作为唯一身份依据。',
  `phone_ciphertext` VARBINARY(512) NULL DEFAULT NULL COMMENT '加密保存的客户手机号。',
  `phone_lookup_token` CHAR(64) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '标准化手机号的带密钥匹配标记，用于提示重复候选。',
  `education_level` VARCHAR(32) NULL DEFAULT NULL COMMENT '客户学历层次。',
  `target_country_code` VARCHAR(8) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '意向留学国家编码。',
  `source_channel` VARCHAR(32) NOT NULL COMMENT '客户来源，如人工、客服留资或 CRM。',
  `source_reference` VARCHAR(128) NULL DEFAULT NULL COMMENT '来源留资或研判任务引用；固定服务核验实体及授权，不存明文联系方式',
  `employee_id` BIGINT NULL DEFAULT NULL COMMENT '当前顾问员工 ID，未分派时为空。 外键（FK）关联 employee.employee_id。',
  `department_id` BIGINT NOT NULL COMMENT '当前客户管理部门 ID。 外键（FK）关联 org_department.department_id。',
  `status` VARCHAR(32) COLLATE utf8mb4_bin NOT NULL DEFAULT 'new' COMMENT '客户状态：new、contacting、qualified、signed、lost。',
  `status_changed_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '当前客户状态开始生效的时间。',
  `lost_reason` TEXT NULL DEFAULT NULL COMMENT '流失原因，状态变为 lost 时必须填写。',
  `last_followup_at` DATETIME(3) NULL DEFAULT NULL COMMENT '最近一次有效跟进时间，由业务服务维护。',
  `authority_source` VARCHAR(20) NOT NULL DEFAULT 'local' COMMENT '数据权威来源：local 本平台、crm 外部 CRM。',
  `external_customer_id` VARCHAR(128) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT 'CRM 中的客户 ID。',
  `external_updated_at` DATETIME(3) NULL DEFAULT NULL COMMENT '最近确认的外部客户更新时间。',
  `is_archived` BOOLEAN NOT NULL DEFAULT 0 COMMENT '是否已归档，默认 false；保留销售状态和历史，归档后不进入默认客户列表。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时自动刷新；记录最近更新时间，UTC',
  `row_version` INT NOT NULL DEFAULT 1 COMMENT '并发版本号；每次业务修改由后端递增',
  PRIMARY KEY (`customer_id`),
  UNIQUE KEY `uq_customer_no` (`customer_no`),
  UNIQUE KEY `uq_customer_external` (`external_customer_id`),
  KEY `idx_customer_employee_status` (`employee_id`, `status`),
  KEY `idx_customer_department_status` (`department_id`, `status`),
  KEY `idx_customer_phone_token` (`phone_lookup_token`),
  CONSTRAINT `ck_customer_status` CHECK (`status` IN ('new','contacting','qualified','signed','lost')),
  CONSTRAINT `ck_customer_authority` CHECK (`authority_source` IN ('local','crm')),
  CONSTRAINT `ck_customer_lost_reason` CHECK (`status` <> 'lost' OR (`lost_reason` IS NOT NULL AND CHAR_LENGTH(TRIM(`lost_reason`)) > 0)),
  CONSTRAINT `ck_customer_archived` CHECK (`is_archived` IN (0,1)),
  CONSTRAINT `ck_customer_profile_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='统一客户主档、顾问归属及客户状态';

CREATE TABLE `student_profile` (
  `student_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT 'PK；自增；学生主键 ID，是成绩、请假、投诉及学生员工关系使用的内部标识。 主键（PK）。',
  `student_no` VARCHAR(32) NOT NULL COMMENT '学生唯一业务编号。',
  `full_name` VARCHAR(100) NOT NULL COMMENT '学生姓名，允许重名。',
  `phone_ciphertext` VARBINARY(512) NULL DEFAULT NULL COMMENT '加密保存的学生手机号。',
  `customer_id` BIGINT NULL DEFAULT NULL COMMENT '关联客户 ID，不自动授予客户账号访问学生数据的权限。 外键（FK）关联 customer_profile.customer_id。',
  `department_id` BIGINT NOT NULL COMMENT '学生教务或服务归属部门 ID。 外键（FK）关联 org_department.department_id。',
  `login_provider` VARCHAR(32) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '学生登录来源，尚未开通账号时为空。',
  `login_subject` VARCHAR(128) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '学生登录身份键，与登录来源同时填写。',
  `status` VARCHAR(32) COLLATE utf8mb4_bin NOT NULL COMMENT '学生服务或在读状态。',
  `external_student_id` VARCHAR(128) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '教务系统中的学生 ID。',
  `crm_student_id` VARCHAR(128) NULL DEFAULT NULL COMMENT 'CRM 学生独立标识；目标为非空值唯一，类型与学生文档一致；由后续统一迁移核对补齐。',
  `is_archived` BOOLEAN NOT NULL DEFAULT 0 COMMENT '是否已归档，默认 false；归档不删除已有成绩、请假和投诉关联。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时自动刷新；记录最近更新时间，UTC',
  `row_version` INT NOT NULL DEFAULT 1 COMMENT '并发版本号；每次业务修改由后端递增',
  PRIMARY KEY (`student_id`),
  UNIQUE KEY `uq_student_no` (`student_no`),
  UNIQUE KEY `uq_student_login` (`login_provider`, `login_subject`),
  UNIQUE KEY `uq_student_external` (`external_student_id`),
  KEY `idx_student_department_status` (`department_id`, `status`),
  KEY `idx_student_customer` (`customer_id`),
  CONSTRAINT `ck_student_login_pair` CHECK ((`login_provider` IS NULL AND `login_subject` IS NULL) OR (`login_provider` IS NOT NULL AND `login_subject` IS NOT NULL)),
  CONSTRAINT `ck_student_archived` CHECK (`is_archived` IN (0,1)),
  CONSTRAINT `ck_student_profile_row_version` CHECK (`row_version` >= 1),
  UNIQUE KEY `uq_student_crm` (`crm_student_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学生唯一主档及业务关联';

CREATE TABLE `operation_log` (
  `operation_log_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT 'PK；自增；业务操作记录主键 ID。 主键（PK）。',
  `operation_key` CHAR(64) COLLATE utf8mb4_bin NOT NULL COMMENT '操作唯一键，由真实操作者、动作和请求幂等键确定，与新建对象 ID 无关。',
  `employee_id` BIGINT NULL DEFAULT NULL COMMENT '真实操作员工 ID，外键关联 employee.employee_id。',
  `student_id` BIGINT NULL DEFAULT NULL COMMENT '真实操作学生 ID，外键关联 student_profile.student_id。',
  `service_code` VARCHAR(64) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '执行自动操作的受控服务编码，不伪装成员工或学生身份。',
  `action_code` VARCHAR(64) COLLATE utf8mb4_bin NOT NULL COMMENT '预先定义的业务动作编码。',
  `entity_type` VARCHAR(32) COLLATE utf8mb4_bin NOT NULL COMMENT '被操作业务实体类型。',
  `entity_id` BIGINT NULL DEFAULT NULL COMMENT '关联对象 ID，新建未完成或失败时可为空。',
  `request_key` VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '逻辑业务请求幂等键，同一提交重试保持不变。',
  `parameters_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '规范化业务参数摘要，用于识别相同幂等键下的参数冲突。',
  `before_data` JSON NULL DEFAULT NULL COMMENT '变更前必要业务快照，敏感字段按规则保护。',
  `after_data` JSON NULL DEFAULT NULL COMMENT '变更后必要业务快照，保留审批及修订结果。',
  `change_reason` TEXT NULL DEFAULT NULL COMMENT '人工更正、移交、驳回、删除等业务原因。',
  `operation_status` VARCHAR(32) COLLATE utf8mb4_bin NOT NULL DEFAULT 'processing' COMMENT '操作状态：processing 处理中、succeeded 成功、failed 失败、pending_external 等待外部结果、unknown_external 外部结果待核实。',
  `result_reference` JSON NULL DEFAULT NULL COMMENT '受控操作回执和对象标识，用于重复请求返回原结果。',
  `external_request_id` VARCHAR(128) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '外部系统请求标识，用于查询写回结果和对账。',
  `error_code` VARCHAR(64) COLLATE utf8mb4_bin NULL DEFAULT NULL COMMENT '操作失败、冲突或待核实的脱敏错误码。',
  `finished_at` DATETIME(3) NULL DEFAULT NULL COMMENT '操作形成明确成功或失败结果的时间。',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，UTC；连接必须设置 time_zone 为 +00:00',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时自动刷新；记录最近更新时间，UTC',
  `row_version` INT NOT NULL DEFAULT 1 COMMENT '并发版本号；每次业务修改由后端递增',
  PRIMARY KEY (`operation_log_id`),
  UNIQUE KEY `uq_operation_key` (`operation_key`),
  KEY `idx_operation_entity_time` (`entity_type`, `entity_id`, `created_at`),
  KEY `idx_operation_employee_time` (`employee_id`, `created_at`),
  KEY `idx_operation_student_time` (`student_id`, `created_at`),
  KEY `idx_operation_status_time` (`operation_status`, `created_at`),
  CONSTRAINT `ck_operation_actor` CHECK (((`employee_id` IS NOT NULL) + (`student_id` IS NOT NULL) + (`service_code` IS NOT NULL)) = 1),
  CONSTRAINT `ck_operation_service` CHECK (`service_code` IS NULL OR CHAR_LENGTH(TRIM(`service_code`)) > 0),
  CONSTRAINT `ck_operation_status` CHECK (`operation_status` IN ('processing','succeeded','failed','pending_external','unknown_external')),
  CONSTRAINT `ck_operation_log_row_version` CHECK (`row_version` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='真实操作者、业务审计、变更快照及幂等回执';

ALTER TABLE `user_account` ADD CONSTRAINT `fk_joint_01` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `user_account` ADD CONSTRAINT `fk_joint_02` FOREIGN KEY (`customer_id`) REFERENCES `customer_profile` (`customer_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `user_account` ADD CONSTRAINT `fk_joint_03` FOREIGN KEY (`student_id`) REFERENCES `student_profile` (`student_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `org_department` ADD CONSTRAINT `fk_joint_04` FOREIGN KEY (`parent_department_id`) REFERENCES `org_department` (`department_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `org_department` ADD CONSTRAINT `fk_joint_05` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `employee` ADD CONSTRAINT `fk_joint_06` FOREIGN KEY (`department_id`) REFERENCES `org_department` (`department_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `customer_profile` ADD CONSTRAINT `fk_joint_07` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `customer_profile` ADD CONSTRAINT `fk_joint_08` FOREIGN KEY (`department_id`) REFERENCES `org_department` (`department_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `student_profile` ADD CONSTRAINT `fk_joint_13` FOREIGN KEY (`customer_id`) REFERENCES `customer_profile` (`customer_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `student_profile` ADD CONSTRAINT `fk_joint_14` FOREIGN KEY (`department_id`) REFERENCES `org_department` (`department_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `operation_log` ADD CONSTRAINT `fk_joint_32` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `operation_log` ADD CONSTRAINT `fk_joint_33` FOREIGN KEY (`student_id`) REFERENCES `student_profile` (`student_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
