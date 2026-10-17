"""学生与班主任、成绩人员、服务顾问的授权关系；复用唯一Base.metadata，建表由独立SQL负责。"""
from datetime import datetime
from sqlalchemy import Table, Column, BigInteger, Integer, String, Text, DateTime, Date, Boolean, JSON, Numeric, LargeBinary, UniqueConstraint, text
from app.database import Base

student_staff_binding = Table('student_staff_binding', Base.metadata,
    Column('binding_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='PK；自增；学生员工关系记录主键 ID。 主键（PK）。', primary_key=True, autoincrement=True),
    Column('student_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='被服务或管理的学生 ID。 外键（FK）关联 student_profile.student_id。'),
    Column('employee_id', BigInteger().with_variant(Integer(), "sqlite"), nullable=False, comment='承担对应职责的员工 ID。 外键（FK）关联 employee.employee_id。'),
    Column('relation_type', String(32), nullable=False, comment='关系类型：class_teacher 班主任、score_editor 成绩人员、service_advisor 服务顾问。'),
    Column('course_scope_code', String(64), nullable=True, comment='成绩权限限定的课程编码，空值需角色允许相应课程范围。'),
    Column('is_primary', Integer(), nullable=False, comment='是否为此业务关系的主要负责人。', server_default=text("'0'")),
    Column('valid_from', DateTime(), nullable=False, comment='关系开始生效时间。', default=datetime.utcnow),
    Column('valid_to', DateTime(), nullable=True, comment='关系失效时间，临时代理需要截止时间。'),
    Column('status', String(32), nullable=False, comment='关系状态：active 有效、disabled 停用。', server_default=text("'active'")),
    Column('created_at', DateTime(), nullable=False, comment='记录创建时间，UTC；连接必须设置 time_zone 为 +00:00', default=datetime.utcnow),
    Column('updated_at', DateTime(), nullable=False, comment='更新时自动刷新；记录最近更新时间，UTC', default=datetime.utcnow),
    Column('row_version', Integer(), nullable=False, comment='并发版本号；每次业务修改由后端递增', server_default=text("'1'")),
    comment='学生与班主任、成绩人员、服务顾问的授权关系',
)
