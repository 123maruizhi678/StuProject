"""学生与班主任、成绩人员、服务顾问的授权关系；公共唯一映射，复用 Base.metadata。"""
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Column, DateTime, FetchedValue, ForeignKey, Index, Integer, String, Table, func, text
)
from sqlalchemy.dialects.mysql import DATETIME, VARCHAR

from app.database import Base


student_staff_binding = Table(
    'student_staff_binding', Base.metadata,
    Column('binding_id', BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True, nullable=False, comment='PK；自增；学生员工关系记录主键 ID。 主键（PK）。'),
    Column('student_id', BigInteger().with_variant(Integer(), "sqlite"), ForeignKey('student_profile.student_id', name='fk_joint_15', ondelete='RESTRICT', onupdate='RESTRICT'), nullable=False, comment='被服务或管理的学生 ID。 外键（FK）关联 student_profile.student_id。'),
    Column('employee_id', BigInteger().with_variant(Integer(), "sqlite"), ForeignKey('employee.employee_id', name='fk_joint_16', ondelete='RESTRICT', onupdate='RESTRICT'), nullable=False, comment='承担对应职责的员工 ID。 外键（FK）关联 employee.employee_id。'),
    Column('relation_type', String(32).with_variant(VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, comment='关系类型：class_teacher 班主任、score_editor 成绩人员、service_advisor 服务顾问。'),
    Column('course_scope_code', String(64).with_variant(VARCHAR(64, collation="utf8mb4_bin"), "mysql"), nullable=True, comment='成绩权限限定的课程编码，空值需角色允许相应课程范围。'),
    Column('is_primary', Boolean, nullable=False, server_default=text('0'), comment='是否为此业务关系的主要负责人。'),
    Column('valid_from', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), comment='关系开始生效时间。'),
    Column('valid_to', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=True, comment='关系失效时间，临时代理需要截止时间。'),
    Column('status', String(32).with_variant(VARCHAR(32, collation="utf8mb4_bin"), "mysql"), nullable=False, server_default=text("'active'"), comment='关系状态：active 有效、disabled 停用。'),
    Column('created_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00'),
    Column('updated_at', DateTime().with_variant(DATETIME(fsp=3), "mysql"), nullable=False, server_default=func.now(), server_onupdate=FetchedValue(), comment='更新时自动刷新；记录最近更新时间，UTC'),
    Column('row_version', Integer, nullable=False, server_default=text('1'), comment='并发版本号；每次业务修改由后端递增'),
    Index('idx_binding_employee_type_status', 'employee_id', 'relation_type', 'status'),
    Index('idx_binding_student_type_status', 'student_id', 'relation_type', 'status'),
    CheckConstraint("relation_type IN ('class_teacher','score_editor','service_advisor')", name='ck_binding_type'),
    CheckConstraint("status IN ('active','disabled')", name='ck_binding_status'),
    CheckConstraint('valid_to IS NULL OR valid_to > valid_from', name='ck_binding_dates'),
    CheckConstraint('is_primary IN (0,1)', name='ck_binding_primary'),
    CheckConstraint('row_version >= 1', name='ck_student_staff_binding_row_version'),
    comment='学生与班主任、成绩人员、服务顾问的授权关系',
    mysql_engine="InnoDB",
    mysql_charset="utf8mb4",
    mysql_collate="utf8mb4_0900_ai_ci",
)
