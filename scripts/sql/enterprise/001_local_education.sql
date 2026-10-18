-- 企业本地课程事实；不使用招生项目或已有成绩冒充选课。
CREATE TABLE enterprise_course (
 course_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '课程主键',
 course_code VARCHAR(64) NOT NULL COMMENT '稳定课程编码',
 course_name VARCHAR(200) NOT NULL COMMENT '课程中文名称',
 status VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '有效状态：active有效、disabled停用',
 row_version INTEGER NOT NULL DEFAULT 1 COMMENT '并发版本号',
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间，UTC',
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '真实修改时间，UTC',
 PRIMARY KEY(course_id), UNIQUE KEY uq_enterprise_course_code(course_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='企业维护的本地课程主数据';
CREATE TABLE enterprise_student_course (
 enrollment_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '学生选课主键',
 student_id BIGINT NOT NULL COMMENT '所属学生主键',
 course_code VARCHAR(64) NOT NULL COMMENT '课程稳定编码',
 term_code VARCHAR(32) NOT NULL COMMENT '学期稳定编码',
 status VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '选课状态：active有效、disabled停用',
 row_version INTEGER NOT NULL DEFAULT 1 COMMENT '并发版本号',
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间，UTC',
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '真实修改时间，UTC',
 PRIMARY KEY(enrollment_id), UNIQUE KEY uq_enterprise_enrollment(student_id,course_code,term_code),
 CONSTRAINT fk_enterprise_enrollment_student FOREIGN KEY(student_id) REFERENCES student_profile(student_id),
 CONSTRAINT fk_enterprise_enrollment_course FOREIGN KEY(course_code) REFERENCES enterprise_course(course_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='企业维护的学生本地选课事实';
