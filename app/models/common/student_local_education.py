"""学业节点、提醒及申请进度共享唯一表映射；local来源不伪造同步时间。"""
from datetime import datetime
from sqlalchemy import Table,Column,BigInteger,Integer,String,DateTime,UniqueConstraint,ForeignKeyConstraint,CheckConstraint,text
from sqlalchemy.dialects.mysql import DATETIME
from app.database import Base
ID=BigInteger().with_variant(Integer(),'sqlite')
DateTime=DateTime().with_variant(DATETIME(fsp=6),'mysql')
def identity():return [Column('id',ID,primary_key=True,autoincrement=True,comment='记录主键'),Column('student_id',ID,nullable=False,comment='所属学生')]
def times():return [Column('created_at',DateTime,nullable=False,default=datetime.utcnow,comment='创建时间UTC'),Column('updated_at',DateTime,nullable=False,default=datetime.utcnow,comment='真实修改或提醒设置代次UTC')]
def version():return Column('row_version',Integer,nullable=False,server_default=text('1'),comment='并发版本号')
student_academic_event=Table('student_academic_event',Base.metadata,*identity(),
 Column('source_system',String(32),nullable=False,comment='来源系统，local为本地'),Column('external_event_id',String(128),nullable=False,comment='来源标识，本地使用local前缀UUID'),Column('event_type',String(20),nullable=False,comment='学业节点类型exam或ddl'),Column('title',String(200),nullable=False,comment='节点标题'),Column('due_at',DateTime,nullable=False,comment='考试或截止时点UTC'),Column('source_timezone',String(64),nullable=False,default='Asia/Shanghai',comment='来源时区'),Column('event_status',String(20),nullable=False,default='active',comment='节点状态'),Column('event_version',Integer,nullable=False,default=1,comment='提醒事件及并发版本'),Column('source_updated_at',DateTime,nullable=True,comment='源事实真实更新时间UTC'),Column('synced_at',DateTime,nullable=True,comment='外部同步时间，本地为空'),*times(),UniqueConstraint('student_id','source_system','external_event_id',name='uk_academic_source'),comment='共享学生学业节点')
student_academic_reminder=Table('student_academic_reminder',Base.metadata,*identity(),
 Column('academic_event_id',ID,nullable=False,comment='学业节点'),Column('lead_minutes',Integer,nullable=False,comment='提前分钟'),Column('notify_at',DateTime,nullable=False,comment='计划提醒时间UTC'),Column('event_version',Integer,nullable=False,comment='节点版本'),Column('status',String(20),nullable=False,default='pending',comment='提醒状态'),Column('sent_at',DateTime,nullable=True,comment='成功投递时点UTC'),*times(),UniqueConstraint('student_id','academic_event_id','lead_minutes',name='uk_reminder_setting'),comment='共享学业提醒，不由企业任务投递')
student_application_progress=Table('student_application_progress',Base.metadata,*identity(),
 Column('source_system',String(32),nullable=False,comment='来源系统'),Column('external_application_id',String(128),nullable=False,comment='申请稳定标识，本地local前缀UUID'),Column('application_name',String(200),nullable=False,comment='申请项目名称'),Column('stage_code',String(32),nullable=False,comment='申请阶段'),Column('stage_status',String(64),nullable=False,comment='阶段受控状态'),Column('detail',String(500),nullable=True,comment='进度说明'),Column('source_updated_at',DateTime,nullable=True,comment='真实事实更新时间UTC'),Column('synced_at',DateTime,nullable=True,comment='外部同步时间，本地为空'),*times(),version(),UniqueConstraint('student_id','source_system','external_application_id','stage_code',name='uk_progress_stage'),comment='共享学生申请进度')

# 两个业务模块使用同一组外键和约束，避免重复注册同名表。
for table in (student_academic_event, student_application_progress):
    table.append_constraint(ForeignKeyConstraint(['student_id'], ['student_profile.student_id']))
student_academic_event.append_constraint(UniqueConstraint('id', 'student_id', name='uk_academic_owner'))
student_academic_event.append_constraint(CheckConstraint("event_type IN ('ddl','exam')", name='ck_academic_type'))
student_academic_event.append_constraint(CheckConstraint("event_status IN ('active','cancelled')", name='ck_academic_status'))
student_academic_event.append_constraint(CheckConstraint('event_version >= 1', name='ck_academic_version'))
student_academic_reminder.append_constraint(ForeignKeyConstraint(['academic_event_id', 'student_id'], ['student_academic_event.id', 'student_academic_event.student_id']))
student_academic_reminder.append_constraint(CheckConstraint('lead_minutes >= 0', name='ck_reminder_lead'))
student_academic_reminder.append_constraint(CheckConstraint("status IN ('pending','queued','sent','cancelled')", name='ck_reminder_status'))
student_application_progress.append_constraint(CheckConstraint("stage_code IN ('document_review','school_application','visa_process')", name='ck_progress_stage'))
