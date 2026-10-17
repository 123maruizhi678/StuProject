"""企业课程主数据与学生选课，固定服务唯一维护。"""
from datetime import datetime
from sqlalchemy import Table,Column,BigInteger,Integer,String,DateTime,UniqueConstraint,text
from app.database import Base
ID=BigInteger().with_variant(Integer(),'sqlite')
def timestamps():
    return [Column('row_version',Integer,nullable=False,server_default=text('1'),comment='并发版本号'),Column('created_at',DateTime,nullable=False,default=datetime.utcnow,comment='创建时间UTC'),Column('updated_at',DateTime,nullable=False,default=datetime.utcnow,comment='真实修改时间UTC')]
enterprise_course=Table('enterprise_course',Base.metadata,
    Column('course_id',ID,primary_key=True,autoincrement=True,comment='课程主键'),Column('course_code',String(64),nullable=False,comment='稳定课程编码'),Column('course_name',String(200),nullable=False,comment='课程名称'),Column('status',String(20),nullable=False,default='active',comment='有效状态'),*timestamps(),UniqueConstraint('course_code',name='uq_enterprise_course_code'),comment='企业本地课程主数据')
enterprise_student_course=Table('enterprise_student_course',Base.metadata,
    Column('enrollment_id',ID,primary_key=True,autoincrement=True,comment='学生选课主键'),Column('student_id',ID,nullable=False,comment='所属学生'),Column('course_code',String(64),nullable=False,comment='课程编码'),Column('term_code',String(32),nullable=False,comment='学期编码'),Column('status',String(20),nullable=False,default='active',comment='选课状态'),*timestamps(),UniqueConstraint('student_id','course_code','term_code',name='uq_enterprise_enrollment'),comment='学生本地选课事实')
